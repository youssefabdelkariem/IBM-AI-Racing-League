# Previous release evidence (66.284 s)

This folder is the validation evidence of the previous release (66.284 s, damage 0, 0 timeouts), which `main` published before release P1. It is kept unchanged for history. The files were moved here from `evidence/` without edits.

- `native_windows_validation/`: five native Windows runs at 66.284 s. In `native_run1` and `native_run2` the client was started before TORCS; see the note in that release's README in the git history.
- `fresh_clone_validation/`: fresh-clone checks of that release:
  - `fresh_clone_test`: one server timeout, 67.058 s, not a valid reproduction;
  - `fresh_clone_test2` and `fresh_clone_test3`: 66.284 s.
- `lap_speed_profile.json`: measured speed along the 66.284 s lap.

`tools/validate_windows.py --selftest` re-evaluates these runs against the current reference. The clean runs are reported as `VALID_RUN_DIFFERENT_TIME` and `fresh_clone_test` as `INVALID_RUN`.

The controller files of that release are in the git history (`main` at `22ff95e`).
