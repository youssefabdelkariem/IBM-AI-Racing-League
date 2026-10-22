# Release P1 validation evidence (65.968 s)

These are local validation runs on native Windows TORCS (`wtorcs.exe -r config/raceman/quickrace.xml`, results-only mode). They are not official league results.

## Runs of this repository's `controller/` folder
Each run was made with `python tools/validate_windows.py repo_runN`, with `TORCS_DIR` set and TORCS started before the controller.

| Run | Official lap | Laps | Damage | Server timeouts | Client exit | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `repo_run1` | 65.968 | 1 | 0 | 0 | 0 | REPRODUCED |
| `repo_run2` | 65.968 | 1 | 0 | 0 | 0 | REPRODUCED |
| `repo_run3` | 65.968 | 1 | 0 | 0 | 0 | REPRODUCED |
| `repo_run4` | 65.968 | 1 | 0 | 0 | 0 | REPRODUCED |
| `repo_run5` | 65.968 | 1 | 0 | 0 | 0 | REPRODUCED |

### Files in each run folder
- `official_result.xml`: the TORCS result file;
- `report.json`: the checks and verdict;
- `simulator_log.txt`: the TORCS console;
- `client_stdout.txt` and `client_stderr.txt`: the controller console.

### Result XML sanitisation
The published `official_result.xml` files differ from TORCS's originals only in header lines 2-3, which contained local file paths. They now read `params.dtd` and `results.xsl`. The originals' hashes are in [`ORIGINAL_RESULT_XML_SHA256.txt`](ORIGINAL_RESULT_XML_SHA256.txt).

### Stock-file checks
[`stock_hash_checks.json`](stock_hash_checks.json) records a SHA-256 check of nine stock files before and after every race. The files were unchanged in all five runs:
- `cars/car1-ow1/car1-ow1.xml`
- `drivers/scr_server/0/car1-ow1.rgb`
- `tracks/road/corkscrew/corkscrew.xml`
- `config/raceman/quickrace.xml`
- `categories/ow1.xml`
- `config/raceengine.xml`
- `modules/simu/simuv2.dll`
- `drivers/scr_server/scr_server.dll`
- `wtorcs.exe`

The first four are listed with their hashes in [`../../tools/reference_hashes.json`](../../tools/reference_hashes.json).

## Earlier validation of the same files (summary, raw logs not published)
- **Sealed release package** (byte-identical to `controller/`): 6 native races at 65.968 s, 5 of them through `run_controller.py`, plus 1 graphics-mode race recorded with OBS at 65.968 s. Damage 0 and 0 timeouts in all.
- **Logged run track limits:**
  - max |trackPos| 0.967;
  - 446 complex 0.721 (limit 0.73);
  - 1,931 m kerb entry 271.7 km/h (guard 272.5), kerb top speed 276.9 km/h (guard 278.0);
  - peak sideslip 13.6°.
- **Replay identity:** all 3,241 logged states of a P1 reference lap were fed to `controller/submission_driver.py`. Steer, throttle, brake, gear and clutch commands were identical (0 mismatches).
- **Before packaging, P1 itself:** 10 identical laps in the Corkscrew line study (4 in graphics/OBS mode) and 12 in the 770 m corner study.

The raw qualifying-lap recording (MP4) and the full telemetry are kept outside this repository.
