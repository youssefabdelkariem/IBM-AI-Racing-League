# Proposed public file inventory

Only these files are intended for GitHub publication:

1. `.gitignore` — excludes local runs, caches, and private references.
2. `README.md` — project, installation, race conditions, evidence limits and credits.
3. `requirements.txt` — confirms no third-party Python package requirement.
4. `car-setup.json` — seven tested setup values and car-file hashes, without TORCS asset redistribution.
5. `THIRD_PARTY_NOTICES.md` — upstream and simulator licensing notes.
6. `PUBLISH_MANIFEST.md` — this exact inventory.
7. `licenses/gym-torcs-MIT.txt` — license supplied with the required protocol client.
8. `src/controller_fastest_clean.py` — path-adjusted winning controller copy.
9. `src/controller_v3_4.py` — unchanged foundation controller.
10. `src/snakeoil3_gym.py` — unchanged local SCR protocol client.
11. `src/race_runner.py` — path-adjusted UDP race client.
12. `src/preflight_fastest.py` — path-adjusted configuration check.
13. `src/fastest-clean.json` — unchanged winning controller settings.
14. `evidence/RESULT.md` — measured result and explanation of withheld original artifacts.
15. `evidence/SHA256.md` — original and published source hashes.

`private_reference/` is local-only and ignored by Git. It holds untouched copies of the original result XML and original/tested car XMLs for audit. It must not be uploaded. No simulator executables, assets, development archive, telemetry, screenshots, video, or livery are included.
