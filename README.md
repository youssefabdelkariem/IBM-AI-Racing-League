# IBM AI Racing League — Autonomous TORCS Racing Controller

An autonomous Python controller developed for IBM AI Racing League work in Mechatronics Engineering at Egypt University of Informatics (EUI). A retained TORCS Quick Race result records one **67.064-second Corkscrew lap with zero damage** from a standing start. The 67.064-second result belongs to the **unmodified local winning snapshot** identified in `evidence/SHA256.md`. This repository's controller and launcher are portability-adjusted copies; they have not independently reproduced that time.

## What the controller does

The controller uses the installed Corkscrew segment geometry to build a distance-indexed circuit profile. It combines local curvature and a recorded line-offset profile to set corner speed targets. Backward braking and forward acceleration passes make the speed target anticipate upcoming corners and the standing start. During the race it interpolates that profile, tracks the target path with steering feed-forward and heading/position feedback, manages throttle and braking, limits wheel slip, and chooses gears with shift guards. It retains sensor checks, recovery handling, and emergency speed caps from the V3.4 foundation. This is a deterministic controller, not a trained neural-network model.

IBM Bob developed the earlier V2–V5 experiments and the retained V3.4 control and safety foundation. ChatGPT Codex contributed subsequent high-speed controller optimization, track-line tuning, tests, review, and this packaging. IBM Bob did **not** independently produce the final 67.064-second controller. Development included multiple separate configurations and clean races; the fastest result is one measured run and its repeatability is not established. See `evidence/RESULT.md` for the limits of the available evidence.

## Race conditions and compliance disclosure

The recorded run used Corkscrew, one lap, standing start, `scr_server 1`, normal damage, and 5 L starting fuel. The car had **50° front wing, 30° rear wing, 115 mm front ride height, and 125 mm rear ride height**. Engine, tyres, mass, and track geometry were unchanged from the retained local original. This was **not** an unmodified stock car setup. The Python controller reads the installed Corkscrew track XML. Permission under the competition rules for that setup and for reading track geometry has **not been established**; this repository does not claim organizer approval.

## Files and prerequisites

- `src/controller_fastest_clean.py`: portability-adjusted controller. `src/fastest-clean.json` contains the unchanged recorded tuning values.
- `src/controller_v3_4.py`: IBM Bob's required V3.4 base. `src/snakeoil3_gym.py`: SCR sensor/action protocol classes.
- `src/race_runner.py`: UDP client, telemetry writer and race summary. `src/preflight_fastest.py`: read-only race and file check.
- `car-setup.json`: exact setup differences and local hashes; no TORCS car asset is redistributed.
- `evidence/RESULT.md` and `evidence/SHA256.md`: measured result, provenance and hashes. `licenses/gym-torcs-MIT.txt` and `THIRD_PARTY_NOTICES.md`: upstream attribution.

Python **3.12** was used for the packaging checks. The included race scripts use only Python's standard library, so `requirements.txt` has no pip dependencies. Install a Windows TORCS build with the SCR `scr_server` driver, Corkscrew, and `car1-ow1` separately. The tested SCR connection is UDP `127.0.0.1:3001`. The simulator executable and assets are not included.

## Run on Windows

Set `TORCS_HOME` to the directory containing `wtorcs.exe`. The current installation's exact car and track hashes are checked by preflight, so a different TORCS version or setup may fail. On a separate copy of TORCS, configure the seven car setup values in `car-setup.json`; preserve a backup of that installation's original car XML. The published package intentionally does not install or change vehicle files automatically.

Open TORCS and select **Race → Quick Race → Configure Race**: Corkscrew, only `scr_server 1`, one lap, and standing start. Return to the Quick Race screen without clicking **New Race**. In PowerShell, from this repository root:

```powershell
$env:TORCS_HOME = 'C:\path\to\torcs'
python .\src\preflight_fastest.py
```

Continue **only if preflight passes**. Then run:

```powershell
python -u .\src\race_runner.py --controller .\src\controller_fastest_clean.py --label fastest-clean --settings-file .\src\fastest-clean.json
```

Wait for `RUN` in the console, then click **New Race** in TORCS. The client should print `CONNECTED`. It writes new local output under `src/runs/`; that directory is excluded from Git. Press **Ctrl+C** in PowerShell to cancel or stop it after a race. Do not run a second client on port 3001 at the same time.

## Reproducibility limits

The source files in `src/` were changed only to replace one computer's absolute paths with `TORCS_HOME` and local source-file lookup. The control policy and unchanged JSON values were not deliberately changed. Because these copies have not completed an independently verified TORCS lap, **67.064 seconds is not claimed for the portable copy**. Preflight checks local hashes and configuration; it cannot prove lap-time repeatability, normal-damage enforcement, or competition eligibility. Exact reproduction also requires a compatible TORCS/SCR installation, the specified car XML and track XML, and the same race settings. Later local attempts with the unmodified winning controller did not reliably repeat its original launch behavior.

No winning-race screenshot, video link, or custom livery was found in the retained material. None is claimed here. The original result XML and 6.4 MB telemetry remain private local evidence because the XML embeds a personal machine path and the telemetry was unnecessary for this source package. Their hashes are recorded for independent comparison; the XML has not been rewritten.

## Licensing and acknowledgments

The MIT license supplied with the gym-torcs dependency is retained under `licenses/`. See `THIRD_PARTY_NOTICES.md` for upstream credits and TORCS asset exclusions. No license for the original TORCS distribution or assets is granted by this repository. The IBM Bob/Codex project-specific files have no additional open-source license declaration in this submission.
