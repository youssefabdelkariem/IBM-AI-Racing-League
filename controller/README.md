# IBM AI Racing League — Corkscrew controller (release P1, 65.968 s)

Python controller for TORCS's SCR client interface (car1-ow1, Corkscrew, 1 lap, standing start).

**Validated result on this release:**
- 65.968 s (TORCS result screen `01:05:96`), damage 0, 0 server timeouts;
- every run identical, native Windows TORCS, stock car, track and physics files.

## Files
| File | Role |
|---|---|
| `run_controller.py` | entry point: the starter loop of `snakeoil3_gym.py` (`Client(p=3001)` → `get_servers_input` → `drive` → `respond_to_server`) |
| `snakeoil3_gym.py` | unmodified starter SCR client supplied with the competition kit |
| `submission_driver.py` | loads `settings.json`, configures the controller, disables Python's garbage collector during the race (prevents server timeouts) |
| `controller_c3.py` | the controller (steering, speed, traction control, ABS, gears, clutch) |
| `c1_plan.py`, `c3_geom.py` | read the stock Corkscrew track geometry (read-only) and build the reference at start-up |
| `settings.json` | controller parameters |
| `plan_cand.npz` | precomputed racing line and speed plan for Corkscrew |
| `line_4.4.npz`, `line_4.9.npz` | precomputed minimum-curvature line caches (4.4 m is used; 4.9 m is the import-time default and prevents the package writing a cache file) |
| `requirements.txt` | numpy |
| `SHA256SUMS.txt` | checksums of every file |

## Run (Windows)
1. Install Python 3.9+ with numpy (tested: Python 3.9.13, numpy 2.0.2): `python -m pip install -r requirements.txt`.
2. The controller reads the **installed, unmodified** `tracks/road/corkscrew/corkscrew.xml`. It is found automatically when this folder sits inside or next to the TORCS folder; otherwise set `TORCS_DIR` to the TORCS install folder, or `TORCS_TRACK_XML` to the file.
3. Start TORCS and select **Race → Quick Race → New Race**. The saved Quick Race is Corkscrew, `scr_server 1`, 1 lap. TORCS then waits for the client on port 3001.
4. Then start the client with **no arguments**: `python -B run_controller.py`.

Start TORCS (and New Race) before the client. If the client is started earlier, the starter script repeatedly tries `pkill torcs` / `torcs` / `sh autostart.sh` (harmless on Windows, where those commands do not exist).

Command-line alternative used for validation: `wtorcs.exe -r config/raceman/quickrace.xml` from the TORCS folder (results-only mode), then the client.

## Notes
- No TORCS file is modified or shipped. The controller only reads the stock track XML.
- Run nothing CPU-heavy while racing: a stalled client reply makes the server reuse the previous command ("Timeout for client answer"), which changes the lap.
