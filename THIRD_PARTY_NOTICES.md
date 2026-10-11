# Third-party code and simulator

`src/snakeoil3_gym.py` is the SCR protocol client from the gym-torcs project, adapted locally before the recorded run. `licenses/gym-torcs-MIT.txt` preserves the license shipped with that project. The source file credits Chris X Edwards for the earlier Snake Oil client. `src/controller_v3_4.py` imports the protocol classes from that file.

TORCS itself, including its executable, track and car assets, is **not** bundled here. Install it separately under its own license terms. The controller reads the installed Corkscrew track XML at runtime; this repository does not redistribute that track. The recorded car XMLs are omitted because they contain simulator material. `car-setup.json` describes only the seven changed setup values and hashes for comparison.

The IBM Bob and Codex-developed controller, race runner and documentation are presented for inspection and reproduction. Publication does not imply organizer approval of the car setup or track-map use, or grant a broader license to third-party simulator assets.
