# Running the controller on Windows (native TORCS)

Result of this exact folder through the starter client loop: **66.284 s, damage 0, 0 SCR timeouts** (five runs, see [`../evidence/native_windows_validation/`](../evidence/native_windows_validation/)).

## Get the code and verify it
```powershell
git clone -c core.autocrlf=false https://github.com/youssefabdelkariem/IBM-AI-Racing-League.git
cd IBM-AI-Racing-League\controller
Get-Content SHA256SUMS.txt | ForEach-Object { $h, $f = $_ -split '\s+', 2; if ((Get-FileHash $f -Algorithm SHA256).Hash.ToLower() -eq $h) { "OK    $f" } else { "DIFF  $f" } }
```
All 11 lines must print `OK`. Git for Windows converts text files to CRLF by default (`core.autocrlf=true`), which would change five `.py` checksums; `-c core.autocrlf=false` and the repository's `.gitattributes` prevent that. If you already cloned with the default, run `git config core.autocrlf false`, then `git rm -rf --cached . ; git reset --hard` inside the clone to re-checkout.

## What you need
- The league's Windows TORCS install (the folder that contains `wtorcs.exe`, with the SCR server driver, the Corkscrew track and the `car1-ow1` car). This repository neither installs nor modifies TORCS and contains no TORCS assets.
- Python 3.9 or newer with numpy (tested: Python 3.9.13, numpy 2.0.2): `python -m pip install -r requirements.txt`
- A stock, unmodified Corkscrew track XML in that install: `<TORCS folder>\tracks\road\corkscrew\corkscrew.xml` (read-only; reference SHA-256 in [`../tools/reference_hashes.json`](../tools/reference_hashes.json)).
- The race in TORCS uses the league's original livery texture (`drivers\scr_server\0\car1-ow1.rgb`, SHA-256 in the reference file). `../livery/car1-ow1.rgb` is that same original file.

## Tell the controller where TORCS is
The controller reads the track geometry from your installed track XML when it starts. Set the TORCS folder in the same PowerShell window you will use to start the controller:

```powershell
$env:TORCS_DIR = 'C:\path\to\torcs'      # the folder containing wtorcs.exe and tracks\
```
Alternatives: `$env:TORCS_TRACK_XML = 'C:\...\corkscrew.xml'` (the file itself), or keep this repository inside a folder tree that contains `...\torcs\tracks\road\corkscrew\corkscrew.xml` (it is found by walking up from the `controller` folder).

## Race steps (order matters: TORCS first, then the client)
1. **Start TORCS** (window 1): `cd 'C:\path\to\torcs'; .\wtorcs.exe`
2. Menu: **Race -> Quick Race -> Configure Race**. Category **Road**, track **Corkscrew**, drivers: **only `scr_server 1`** (car `car1-ow1`), **1 lap**, standing start (the stock setting). Accept, return to the Quick Race screen and click **New Race**. TORCS shows its blue waiting screen for the SCR client on UDP port 3001.
3. **Start the controller** (window 2, no extra arguments; the starter client parses the command line):
   ```powershell
   $env:TORCS_DIR = 'C:\path\to\torcs'
   cd <repository>\controller
   python -B run_controller.py
   ```
4. Expected console output: `Client connected on 3001..............`, then silence for about 66 s, then `Server has stopped the race on 3001. You were in 1 place.` and `Race terminated or 100000 steps elapsed. Shutting down 3001.`
5. Official result: the TORCS results screen, and the newest `results\quickrace\results-<date-time>.xml` in the TORCS folder (`time` / `best lap time` and `dammages`). Expected: **66.284** with damage **0**. A result with a server timeout (the simulator console prints `Timeout for client answer`) or damage is not a valid reproduction.

## One-command check (optional)
`python tools/validate_windows.py my_run` (with `TORCS_DIR` set) starts TORCS from the saved Quick Race configuration, starts the controller afterwards, and writes the official result XML, simulator and client logs, the measured timeout count and a verdict to `validation_runs/my_run/report.json`. Verdicts: `REPRODUCED` (valid run, 66.284 s, exit code 0), `VALID_RUN_DIFFERENT_TIME` (valid but another time, exit code 2), `INVALID_RUN` (timeout, damage, no result or client error, exit code 1). `python tools/validate_windows.py --check-only` verifies `TORCS_DIR` and the track XML without starting anything; `--selftest` re-evaluates the published evidence offline. It starts the same race as steps 1-4, from the TORCS Quick Race configuration saved in `config\raceman\quickrace.xml`, so configure the race once in the menu (step 2) first.

## Stop and restart safely
- Cancel with **Ctrl+C** in the controller window; a lap cancelled mid-race is not a valid result. Leave the race in TORCS (Esc) and close TORCS.
- Close TORCS completely before each new attempt; never run two clients (one UDP port 3001).
- **Always start TORCS first.** If the client waits for a server for about 7 s it prints `relaunch torcs` and the starter client then executes `pkill torcs`, `torcs -nofuel -nodamage -nolaptime &` and `sh autostart.sh`. On a plain Windows machine those commands do not exist and nothing happens, but where they exist they would kill or restart TORCS with fuel and damage switched off.

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| `Superflous input? ...` | Do not pass arguments to `run_controller.py`. |
| `corkscrew.xml not found` | Set `TORCS_DIR` (or `TORCS_TRACK_XML`) as above. |
| `ModuleNotFoundError: numpy` | `python -m pip install -r requirements.txt`. |
| Time slower than 66.284 or a `Timeout for client answer` line | Close other heavy programs and repeat; any timeout invalidates the run (a single timeout costs about 0.4 s). |
| `DIFF` lines in the checksum check | The files were converted to CRLF: clone with `-c core.autocrlf=false` (see above). |
| Different stock files | Compare with `tools/reference_hashes.json`; lap times are exact only with the reference files. |
