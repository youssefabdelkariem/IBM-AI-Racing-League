"""Submission driver: loads the accepted settings and plan and exposes drive(client) for the TORCS SCR client loop.

* controller_c3.py, c3_geom.py, c3_model.py, plan_y2_4.npz, line_4.4.npz and settings.json are byte-identical to the accepted package
  (best_c7_launch_66_284); c1_plan.py differs only in how the stock track XML path is found.
* GC protection: Python's cyclic garbage collector can pause for tens of milliseconds, which makes TORCS (SCR server) report
  'Timeout for client answer' and each such timeout adds one step of latency for the rest of the race. The first call of drive()
  therefore runs gc.collect(), gc.freeze() and gc.disable() once, before the race starts moving. The controller allocates only a few
  short-lived floats/dicts per step (3,331 steps per lap), so memory growth without collection is negligible.
"""
import gc, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
import controller_c3 as _ctl

_SETTINGS = json.loads((HERE / 'settings.json').read_text(encoding='utf-8-sig'))
_ctl.configure(_SETTINGS)
_gc_ready = False


def protect_gc():
    global _gc_ready
    if not _gc_ready:
        gc.collect(); gc.freeze(); gc.disable(); _gc_ready = True


def drive(client):
    """client.S.d = server state dict, client.R.d = action dict (starter snakeoil3_gym.Client interface)."""
    protect_gc()
    return _ctl.drive(client)
