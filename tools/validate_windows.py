"""One-command Windows validation of the controller against a native TORCS install.

    $env:TORCS_DIR = 'C:\\path\\to\\torcs'          # folder that contains wtorcs.exe
    python tools/validate_windows.py my_run          # starts TORCS, then the controller; writes validation_runs/my_run/
    python tools/validate_windows.py --check-only    # only resolve and check paths, start nothing
    python tools/validate_windows.py --selftest      # offline: run the acceptance logic over the published evidence, no race

The race that is started is the Quick Race saved in <TORCS_DIR>/config/raceman/quickrace.xml (configure it once in the TORCS menu:
Road, Corkscrew, scr_server 1 only, 1 lap). TORCS is started first, then the controller (the official order).

Verdict (exit code):
  REPRODUCED                (0)  valid run AND best lap time equals the reference 66.284 s
  VALID_RUN_DIFFERENT_TIME  (2)  valid run (see checks) but another lap time
  INVALID_RUN               (1)  any check failed (timeout, damage, no result, client error, ...)
Stock-file hash differences (for example a modified livery) are reported as warnings; they do not make a run invalid.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REFERENCE_TIME = 66.284
TIME_TOLERANCE = 0.0005


def clean_path(raw):
    raw = (raw or '').strip().strip('"').strip("'")
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve() if raw else None


def resolve_environment():
    """Return (torcs_dir, track_xml) or raise SystemExit with a clear message."""
    torcs = clean_path(os.environ.get('TORCS_DIR'))
    if torcs is None:
        sys.exit("TORCS_DIR is not set. Set it to the TORCS folder that contains wtorcs.exe, e.g.  $env:TORCS_DIR = 'C:\\path\\to\\torcs'")
    if not torcs.is_dir():
        sys.exit('TORCS_DIR is not a folder: %s' % torcs)
    for rel in ('wtorcs.exe', 'config/raceman/quickrace.xml'):
        if not (torcs / rel).is_file():
            sys.exit('%s not found in TORCS_DIR (%s)' % (rel, torcs))
    xml_override = clean_path(os.environ.get('TORCS_TRACK_XML'))
    track = xml_override if xml_override else torcs / 'tracks' / 'road' / 'corkscrew' / 'corkscrew.xml'
    if not track.is_file():
        sys.exit('Corkscrew track XML not found: %s (set TORCS_TRACK_XML to the file if it lives elsewhere)' % track)
    return torcs, track


def parse_result(path):
    """Winning entry (Rank/1) of a TORCS results XML -> dict, or None."""
    root = ET.parse(path).getroot()
    for sec in root.iter('section'):
        if sec.get('name') == 'Rank':
            first = sec.find('section')
            if first is None: return None
            d = {}
            for e in first:
                if e.tag in ('attnum', 'attstr'): d[e.get('name')] = e.get('val')
            return d
    return None


def evaluate(entry, timeouts, client_exit, client_log):
    """Acceptance logic. entry = parse_result() dict or None. Returns (verdict, checks, lap_time)."""
    def num(key):
        try: return float(entry.get(key))
        except (TypeError, ValueError, AttributeError): return None
    t = num('best lap time'); laps = num('laps'); dmg = num('dammages')
    checks = {
        'official_result_found': entry is not None,
        'one_lap_completed': laps == 1,
        'lap_time_present': t is not None and t > 0 and num('time') is not None,
        'damage_is_zero': dmg == 0,
        'no_scr_timeouts': timeouts == 0,
        'client_exit_zero': client_exit == 0,
        'race_ended_by_server': 'Server has stopped the race' in (client_log or ''),
        'driver_and_car': bool(entry) and entry.get('name') == 'scr_server 1' and entry.get('car') == 'car1-ow1',
    }
    valid = all(checks.values())
    if not valid: return 'INVALID_RUN', checks, t
    return ('REPRODUCED' if abs(t - REFERENCE_TIME) <= TIME_TOLERANCE else 'VALID_RUN_DIFFERENT_TIME'), checks, t


EXIT = {'REPRODUCED': 0, 'VALID_RUN_DIFFERENT_TIME': 2, 'INVALID_RUN': 1}


def selftest():
    """Offline: re-evaluate the published evidence (no TORCS needed) and check the verdicts are the expected ones."""
    ev = REPO / 'evidence'; expected = []
    for run in sorted((ev / 'native_windows_validation').glob('native_run*')): expected.append((run, 'REPRODUCED'))
    expected += [(ev / 'fresh_clone_validation' / 'fresh_clone_test', 'INVALID_RUN'), (ev / 'fresh_clone_validation' / 'fresh_clone_test2', 'REPRODUCED'), (ev / 'fresh_clone_validation' / 'fresh_clone_test3', 'REPRODUCED')]
    ok = True
    for run, want in expected:
        rep = json.loads((run / 'report.json').read_text()); entry = parse_result(run / 'official_result.xml')
        log = (run / 'client_stdout.txt').read_text(errors='ignore')
        got, checks, t = evaluate(entry, rep.get('timeouts_measured'), rep.get('client_exit'), log)
        print('%-28s time %-7s timeouts %s -> %-24s (expected %s)%s' % (run.name, t, rep.get('timeouts_measured'), got, want, '' if got == want else '   <-- MISMATCH'))
        ok &= (got == want)
    synth = dict(name='scr_server 1', car='car1-ow1', laps='1', time='66.284', **{'best lap time': '66.284', 'dammages': '120'})
    got = evaluate(synth, 0, 0, 'Server has stopped the race')[0]; print('%-28s synthetic damage 120 -> %s (expected INVALID_RUN)' % ('synthetic', got)); ok &= got == 'INVALID_RUN'
    synth['dammages'] = '0'; synth['best lap time'] = '66.9'; got = evaluate(synth, 0, 0, 'Server has stopped the race')[0]
    print('%-28s synthetic 66.9 s clean -> %s (expected VALID_RUN_DIFFERENT_TIME)' % ('synthetic', got)); ok &= got == 'VALID_RUN_DIFFERENT_TIME'
    print('SELFTEST', 'PASSED' if ok else 'FAILED'); return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('label', nargs='?', default=None); ap.add_argument('--check-only', action='store_true'); ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--startup-wait', type=float, default=8.0, help='seconds TORCS gets to reach its waiting screen before the controller starts (default 8)')
    ap.add_argument('--timeout', type=float, default=180.0, help='maximum seconds for the race (default 180)')
    a = ap.parse_args()
    if a.selftest: return selftest()
    torcs, track = resolve_environment()
    ref = json.loads((REPO / 'tools' / 'reference_hashes.json').read_text())['files']
    print('TORCS_DIR   :', torcs); print('track XML   :', track); print('controller  :', REPO / 'controller' / 'run_controller.py')
    if a.check_only: print('check-only: paths OK, nothing started.'); return 0
    label = a.label or time.strftime('run_%Y%m%d_%H%M%S')
    out = REPO / 'validation_runs' / label; out.mkdir(parents=True, exist_ok=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    hashes = {rel: (sha(torcs / rel) if (torcs / rel).is_file() else None) for rel in ref}
    start = time.time(); env = dict(os.environ, TORCS_DIR=str(torcs))
    if os.environ.get('TORCS_TRACK_XML'): env['TORCS_TRACK_XML'] = str(track)
    sim = client = None
    try:
        with (out / 'client_stdout.txt').open('w') as co, (out / 'client_stderr.txt').open('w') as ce, (out / 'simulator_log.txt').open('w') as so:
            sim = subprocess.Popen([str(torcs / 'wtorcs.exe'), '-r', 'config/raceman/quickrace.xml'], cwd=str(torcs), stdout=so, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            time.sleep(a.startup_wait)                                  # TORCS first (waiting on UDP 3001), then the controller
            client = subprocess.Popen([sys.executable, '-B', '-u', str(REPO / 'controller' / 'run_controller.py')], cwd=str(REPO / 'controller'), stdout=co, stderr=ce, env=env)
            try: client.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired: client.terminate()
            try: sim.wait(timeout=15)
            except subprocess.TimeoutExpired: sim.terminate()
    finally:
        for p in (client, sim):
            if p is not None and p.poll() is None: p.kill()
    timeouts = (out / 'simulator_log.txt').read_text(errors='ignore').count('Timeout for client answer')
    client_log = (out / 'client_stdout.txt').read_text(errors='ignore')
    res = sorted([p for p in (torcs / 'results' / 'quickrace').glob('results-*.xml') if p.stat().st_mtime >= start - 1], key=lambda p: p.stat().st_mtime)
    entry = None
    if res:
        shutil.copy2(res[-1], out / 'official_result.xml'); entry = parse_result(res[-1])
    verdict, checks, lap = evaluate(entry, timeouts, client.returncode if client else None, client_log)
    report = dict(label=label, python=sys.version.split()[0], verdict=verdict, lap_time=lap, reference_time=REFERENCE_TIME, damage=(entry or {}).get('dammages'), timeouts_measured=timeouts,
                  client_exit=client.returncode if client else None, checks=checks,
                  stock_files_match_reference={rel: (hashes[rel] == ref[rel]) for rel in ref}, official=entry)
    warn = [rel for rel in ref if hashes[rel] != ref[rel]]
    if warn: report['warnings'] = ['stock file differs from the reference (informational, lap time may differ): ' + ', '.join(warn)]
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2)); print('VERDICT:', verdict)
    return EXIT[verdict]


if __name__ == '__main__':
    sys.exit(main())
