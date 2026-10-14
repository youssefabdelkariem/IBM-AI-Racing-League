# Third-party notices

## Included code
- **`controller/snakeoil3_gym.py`** - the unmodified SCR (Simulated Car Racing) UDP client supplied with the league starter kit. It is the Snake Oil client by Chris X Edwards as adapted in **gym_torcs** by Naoto Yoshida (MIT License; the licence text is kept in [`licenses/gym-torcs-MIT.txt`](licenses/gym-torcs-MIT.txt)). SHA-256 `6fe87efcd6c772152f8910476c4bfe9ce682f8b71adaf640072e292c0075bdcc`.

## Not included
- **TORCS** (The Open Racing Car Simulator), its executable, the SCR server driver, the `car1-ow1` car and the Corkscrew track are **not** part of this repository and no licence to them is granted here. Install them from the league materials or the TORCS project under their own licences.
- At start-up the controller reads the stock Corkscrew track XML from your own TORCS installation (read-only). The track XML, car XML and results from your machine are never uploaded or modified by this project.

## Project code
The files in `controller/` other than `snakeoil3_gym.py`, and everything in `tools/`, `docs/` and `assets/`, are the project's own work. No open-source licence has been selected for them yet.
