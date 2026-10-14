"""c3_geom - exact centre-line geometry and banking from the track segments (read-only; eligibility unresolved).

c1_plan.centerline() assigns each grid point (ds = 3 m) the curvature of the segment it falls in and integrates on that
grid, so every arc starts/ends up to 1.5 m away from where it really does: the grid model turns 347.2 deg per lap
instead of 360 (hairpin -6.9 deg, 1,931 m -2.9 deg). Here heading and position are integrated analytically per
segment and only then sampled, so the model closes exactly.
"""
import bisect, math, sys
import xml.etree.ElementTree as ET
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import c1_plan as P

SEGS, LTRK = P.load_centerline()

# per-segment start state (heading, x, y) for analytic evaluation
_S0 = []; _ST = []
_th = 0.0; _x = 0.0; _y = 0.0
for _a, _b, _k in SEGS:
    _S0.append(_a); _ST.append((_a, _b, _k, _th, _x, _y))
    if abs(_k) < 1e-12:
        _x += (_b - _a) * math.cos(_th); _y += (_b - _a) * math.sin(_th)
    else:
        _t1 = _th + _k * (_b - _a)
        _x += (math.sin(_t1) - math.sin(_th)) / _k; _y -= (math.cos(_t1) - math.cos(_th)) / _k; _th = _t1
CLOSURE = (_th, _x, _y)


def th_at(s):
    """exact track heading (rad, unwrapped over one lap) at arc length s"""
    s = s % LTRK
    a, b, k, th0, x0, y0 = _ST[max(bisect.bisect_right(_S0, s) - 1, 0)]
    return th0 + k * (s - a)


def k_at(s):
    s = s % LTRK
    return _ST[max(bisect.bisect_right(_S0, s) - 1, 0)][2]


def exact(s_query):
    """heading, x, y, curvature at arc lengths s_query (array)"""
    s_query = np.asarray(s_query, float) % LTRK
    th = np.zeros(len(s_query)); x = np.zeros(len(s_query)); y = np.zeros(len(s_query)); kk = np.zeros(len(s_query))
    for a, b, k, th0, x0, y0 in _ST:
        m = (s_query >= a) & (s_query < b)
        if not m.any(): continue
        u = s_query[m] - a
        if abs(k) < 1e-12:
            th[m] = th0; x[m] = x0 + u * math.cos(th0); y[m] = y0 + u * math.sin(th0)
        else:
            th[m] = th0 + k * u
            x[m] = x0 + (np.sin(th0 + k * u) - math.sin(th0)) / k; y[m] = y0 - (np.cos(th0 + k * u) - math.cos(th0)) / k
        kk[m] = k
    return th, x, y, kk


def banking(s_query):
    """banking angle (rad, TORCS sign: negative on banked left-handers) at arc lengths s_query, linear per XML segment"""
    doc = ET.fromstring(open(P.XML).read().replace('&default-surfaces;', ''))
    segs = []; L = 0.0; prev_end = 0.0   # a segment without banking attributes continues the previous segment's end banking
    for sct in doc.findall('./section[@name="Main Track"]/section[@name="Track Segments"]/section'):
        a = {e.get('name'): e.get('val') for e in sct if e.tag in ('attnum', 'attstr')}
        kind = a['type']; r = float(a.get('radius', 0)); re_ = float(a.get('end radius', r)); arc = math.radians(float(a.get('arc', 0)))
        sl = float(a['lg']) if kind == 'str' else (r + re_) / 2 * arc
        steps = int(float(a.get('profil steps', 1)))
        if a.get('profil', 'spline') != 'spline': steps = 1
        elif steps == 1:
            st = float(a.get('profil steps length', 8)); steps = int(sl / st) + 1 if st else 1
        if r != re_ and steps > 1:
            sl = steps * arc / sum(1 / (r + (re_ - r) * i / (steps - 1)) for i in range(steps))
        b0 = float(a.get('banking start', prev_end)); b1 = float(a.get('banking end', b0)); prev_end = b1
        segs.append((L, L + sl, b0, b1)); L += sl
    s_query = np.asarray(s_query, float) % L
    out = np.zeros(len(s_query))
    for a, b, b0, b1 in segs:
        m = (s_query >= a) & (s_query < b)
        out[m] = np.radians(b0 + (b1 - b0) * (s_query[m] - a) / max(b - a, 1e-9))
    return out


if __name__ == '__main__':
    N = 1203
    s, kc, thp, cxp, cyp, L = P.centerline(N)
    the, xe, ye, ke = exact(s)
    print('exact closure: heading %.2f deg, end (%.2f, %.2f) m ; grid model closure %.2f deg' % (math.degrees(CLOSURE[0]), CLOSURE[1], CLOSURE[2], math.degrees(thp[-1] + kc[-1] * L / N)))
    bk = banking(s)
    for d in (446, 500, 770, 1042, 1528, 1600, 1931, 1960, 2520, 2730, 3000, 3270):
        print('  banking at %d m: %+.1f deg' % (d, math.degrees(bk[int(d / (L / N))])))
