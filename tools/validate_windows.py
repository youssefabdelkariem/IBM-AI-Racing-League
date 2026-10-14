"""One-command Windows validation: starts the TORCS Quick Race that is saved in <TORCS_DIR>/config/raceman/quickrace.xml (configure it once in the menu:
Road, Corkscrew, scr_server 1 only, 1 lap), then starts controller/run_controller.py, and records the official result XML, simulator log, client log,
the measured number of SCR timeouts and the SHA-256 of the stock files (compared with tools/reference_hashes.json).

    $env:TORCS_DIR = 'C:\\path\\to\\torcs'
    python tools/validate_windows.py my_run
Output: validation_runs/<label>/ (ignored by git).
"""
import hashlib, json, os, shutil, subprocess, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TORCS = Path(os.environ.get('TORCS_DIR', ''))
if not (TORCS / 'wtorcs.exe').is_file():
    sys.exit('Set TORCS_DIR to the TORCS folder that contains wtorcs.exe')
label = sys.argv[1] if len(sys.argv) > 1 else time.strftime('run_%Y%m%d_%H%M%S')
out = REPO / 'validation_runs' / label; out.mkdir(parents=True, exist_ok=False)
ref = json.loads((REPO / 'tools' / 'reference_hashes.json').read_text())['files']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
hashes = {rel: (sha(TORCS / rel) if (TORCS / rel).is_file() else None) for rel in ref}
start = time.time()
env = dict(os.environ, TORCS_DIR=str(TORCS))
with (out / 'client_stdout.txt').open('w') as co, (out / 'client_stderr.txt').open('w') as ce, (out / 'simulator_log.txt').open('w') as so:
    sim = subprocess.Popen([str(TORCS / 'wtorcs.exe'), '-r', 'config/raceman/quickrace.xml'], cwd=str(TORCS), stdout=so, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    time.sleep(8)                                    # TORCS first (waiting on UDP 3001), then the client
    client = subprocess.Popen([sys.executable, '-B', '-u', str(REPO / 'controller' / 'run_controller.py')], cwd=str(REPO / 'controller'), stdout=co, stderr=ce, env=env)
    try: client.wait(timeout=180)
    except subprocess.TimeoutExpired: client.terminate()
    try: sim.wait(timeout=10)
    except subprocess.TimeoutExpired: sim.terminate()
report = dict(label=label, python=sys.version.split()[0], client_exit=client.returncode,
              timeouts_measured=(out / 'simulator_log.txt').read_text(errors='ignore').count('Timeout for client answer'),
              stock_files_match_reference={rel: (hashes[rel] == ref[rel]) for rel in ref})
res = sorted([p for p in (TORCS / 'results' / 'quickrace').glob('results-*.xml') if p.stat().st_mtime >= start - 1], key=lambda p: p.stat().st_mtime)
if res:
    shutil.copy2(res[-1], out / 'official_result.xml')
    vals = {e.get('name'): e.get('val') for e in ET.parse(res[-1]).iter('attnum') if e.get('name') in ('time', 'best lap time', 'dammages', 'laps')}
    report['official'] = vals
    report['valid_reproduction'] = (vals.get('best lap time') == '66.284' and vals.get('dammages') == '0' and report['timeouts_measured'] == 0)
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
