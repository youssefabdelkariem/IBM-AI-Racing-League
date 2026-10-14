"""Offline planner for the Claude-developed controller (independent code).

Geometry : read from the installed Corkscrew XML (eligibility of map use is unresolved).
Line     : minimum-curvature path inside the road, Gauss-Newton on discretised curvature.
Speed    : point-mass friction-circle model with speed-dependent (aero) grip.
"""
import math, json, os
import numpy as np
import xml.etree.ElementTree as ET

def _find_track_xml():
    """Portable lookup of the stock, unmodified Corkscrew track XML (read only). Order: TORCS_TRACK_XML (file) ->
    TORCS_DIR (install folder) -> an install folder found by walking up from this file (Windows: <...>\\torcs\\tracks\\...,
    next to the submission) -> the usual container/Linux install -> the copy bundled in ./data. The path is only
    resolved here; nothing is written and the file is never modified."""
    here = os.path.dirname(os.path.abspath(__file__))
    rel = os.path.join('tracks', 'road', 'corkscrew', 'corkscrew.xml')
    cands = []
    if os.environ.get('TORCS_TRACK_XML'): cands.append(os.environ['TORCS_TRACK_XML'])
    if os.environ.get('TORCS_DIR'): cands.append(os.path.join(os.environ['TORCS_DIR'], rel))
    d = here
    for _ in range(7):
        cands.append(os.path.join(d, 'torcs', rel)); cands.append(os.path.join(d, rel))
        d = os.path.dirname(d)
    cands += ['/usr/local/share/games/torcs/' + rel.replace(os.sep, '/'), '/usr/share/games/torcs/' + rel.replace(os.sep, '/'),
              os.path.join(here, 'data', 'corkscrew.xml')]
    for c in cands:
        if os.path.isfile(c): return c
    raise FileNotFoundError('corkscrew.xml not found; set TORCS_TRACK_XML or TORCS_DIR. Tried: ' + '; '.join(cands))


XML = _find_track_xml()
HALF_W = 6.0

def load_centerline(ds_fine=1.0):
    doc = ET.fromstring(open(XML).read().replace('&default-surfaces;', ''))
    segs = []; L = 0.
    for s in doc.findall('./section[@name="Main Track"]/section[@name="Track Segments"]/section'):
        a = {e.get('name'): e.get('val') for e in s if e.tag in ('attnum', 'attstr')}
        kind = a['type']; r = float(a.get('radius', 0)); re_ = float(a.get('end radius', r))
        arc = math.radians(float(a.get('arc', 0)))
        sl = float(a['lg']) if kind == 'str' else (r + re_) / 2 * arc
        steps = int(float(a.get('profil steps', 1)))
        if a.get('profil', 'spline') != 'spline': steps = 1
        elif steps == 1:
            st = float(a.get('profil steps length', 8)); steps = int(sl / st) + 1 if st else 1
        if r != re_ and steps > 1:
            sl = steps * arc / sum(1 / (r + (re_ - r) * i / (steps - 1)) for i in range(steps))
        for j in range(steps):
            rad = r + (re_ - r) * j / (steps - 1) if steps > 1 else r
            size = sl / steps
            k = 0. if kind == 'str' else (1 if kind == 'lft' else -1) / max(rad, 1.)
            segs.append((L, L + size, k)); L += size
    return segs, L

def grade_array(N):
    """Road grade (rise/run, uphill +) at N equal arc-length samples, from the XML 'grade' attribute."""
    doc = ET.fromstring(open(XML).read().replace('&default-surfaces;', ''))
    segs = []; L = 0.
    for s in doc.findall('./section[@name="Main Track"]/section[@name="Track Segments"]/section'):
        a = {e.get('name'): e.get('val') for e in s if e.tag in ('attnum', 'attstr')}
        kind = a['type']; r = float(a.get('radius', 0)); re_ = float(a.get('end radius', r))
        arc = math.radians(float(a.get('arc', 0)))
        sl = float(a['lg']) if kind == 'str' else (r + re_) / 2 * arc
        steps = int(float(a.get('profil steps', 1)))
        if a.get('profil', 'spline') != 'spline': steps = 1
        elif steps == 1:
            st = float(a.get('profil steps length', 8)); steps = int(sl / st) + 1 if st else 1
        if r != re_ and steps > 1:
            sl = steps * arc / sum(1 / (r + (re_ - r) * i / (steps - 1)) for i in range(steps))
        segs.append((L, L + sl, float(a.get('grade', 0.0)) / 100.0)); L += sl
    s = (np.arange(N) + 0.5) * (L / N)
    g = np.zeros(N)
    for a, b, gg in segs:
        g[(s >= a) & (s < b)] = gg
    # light smoothing so the step changes between segments are not abrupt
    k = np.ones(9) / 9
    return np.convolve(np.concatenate([g[-4:], g, g[:4]]), k, mode='valid')

def centerline(N):
    """Centre line sampled at N equal arc-length points (N multiple of 3)."""
    segs, L = load_centerline()
    s = np.arange(N) * (L / N)
    k = np.zeros(N)
    for a, b, kk in segs:
        k[(s >= a) & (s < b)] = kk
    ds = L / N
    th = np.concatenate([[0], np.cumsum(k[:-1]) * ds])  # heading at s_i (approx)
    th = th + 0.5 * k * ds
    x = np.concatenate([[0], np.cumsum(np.cos(th[:-1]) * ds)])
    y = np.concatenate([[0], np.cumsum(np.sin(th[:-1]) * ds)])
    return s, k, th, x, y, L

def path_curv(P):
    a = P - np.roll(P, 1, 0); b = np.roll(P, -1, 0) - P
    cr = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    na = np.hypot(*a.T); nb = np.hypot(*b.T); nc = np.hypot(*(a + b).T)
    return 2 * cr / (na * nb * nc), na

def make_points(n, cx, cy, th):
    return np.stack([cx - n * np.sin(th), cy + n * np.cos(th)], 1)

def optimise_line(N=1203, nmax=4.9, iters=150, smooth=0.0, weights=None, n0=None, verbose=False, power=2.0):
    """Levenberg-Marquardt on sum w*k^2 with box constraints (projected steps, accept/reject)."""
    s, kc, th, cx, cy, L = centerline(N)
    n = np.zeros(N) if n0 is None else n0.copy()
    w = np.ones(N) if weights is None else weights.copy()
    w[[0, 1, N - 2, N - 1]] = 0.0  # open-path seam: reconstructed loop does not close
    h = 1e-3
    def cost_of(nn):
        k, _ = path_curv(make_points(nn, cx, cy, th))
        return float(np.sum(w * k ** 2)), k
    cost, k0 = cost_of(n)
    lam = 1e-2
    for it in range(iters):
        J = np.zeros((N, N))
        for c in range(3):
            n2 = n.copy(); n2[c::3] += h
            k1, _ = path_curv(make_points(n2, cx, cy, th))
            dk = (k1 - k0) / h
            for j in range(c, N, 3):
                for i in ((j - 1) % N, j, (j + 1) % N):
                    J[i, j] = dk[i]
        Wd = np.sqrt(w)[:, None]
        A = (Wd * J).T @ (Wd * J)
        g = (Wd * J).T @ (np.sqrt(w) * k0)
        free = ~(((n >= nmax - 1e-9) & (g < 0)) | ((n <= -nmax + 1e-9) & (g > 0)))
        improved = False
        for _try in range(8):
            Af = A[np.ix_(free, free)] + lam * (np.diag(np.diag(A)[free]) + 1e-6 * np.eye(free.sum()))
            step = np.zeros(N); step[free] = -np.linalg.solve(Af, g[free])
            n_new = np.clip(n + np.clip(step, -2.0, 2.0), -nmax, nmax)
            c_new, k_new = cost_of(n_new)
            if c_new < cost:
                improved = True; break
            lam *= 4
        if not improved: break
        rel = (cost - c_new) / cost
        n, cost, k0 = n_new, c_new, k_new
        lam = max(lam / 3, 1e-6)
        if verbose and it % 10 == 0: print(it, 'cost', cost, 'lam', lam)
        if rel < 1e-6: break
    return s, n, kc, th, cx, cy, L
# ---------------------------------------------------------------- speed model
MODEL = dict(a0=15.0, a1=0.0, c2=0.0085, asat=1e9)

def ay_max(v, S=1.0):
    return S * min(MODEL['a0'] + MODEL['a1'] * v + MODEL['c2'] * v * v, MODEL['asat'])

def vcap(k, S, vmax=95.0):
    """largest v with v^2 k <= S (a0 + a1 v + c2 v^2); k may be an array"""
    a0, a1, c2 = MODEL['a0'], MODEL['a1'], MODEL['c2']
    A = k - S * c2
    B = S * a1; C = S * a0
    Asafe = np.where(A > 1e-9, A, 1.0)
    v = (B + np.sqrt(B * B + 4 * Asafe * C)) / (2 * Asafe)
    v = np.minimum(np.where(A > 1e-9, v, vmax), vmax)
    return np.minimum(v, np.sqrt(S * MODEL['asat'] / np.maximum(k, 1e-9)))

def a_drive(v):
    kmh = np.asarray(v) * 3.6
    return np.interp(kmh, [0, 40, 80, 120, 160, 190, 210, 230, 250, 270, 290, 310, 330], [14., 13.5, 12.5, 11.8, 11.3, 11.0, 8.8, 7.0, 5.7, 4.4, 3.0, 1.6, 0.])

def a_brake_max(v, S_b=0.7):
    return S_b * (15.0 + 0.0085 * v * v) + 0.0016 * v * v  # tyre grip share + aero drag

def speed_profile(kappa, ds_path, S=1.0, S_b=0.7, vmax=95.0, caps=None, pb=2.0, pa=2.0, grade=None, forward=True):
    """kappa/ds_path per point (closed loop); returns speed (m/s) per point and lap time."""
    N = len(kappa); k = np.abs(kappa) + 1e-5
    S = np.broadcast_to(np.asarray(S, float), (N,)).copy()   # S may vary along the lap
    G = np.zeros(N) if grade is None else np.asarray(grade, float)
    v = np.full(N, vmax)
    # corner cap: v^2 k <= ay_max(v)  -> v^2 (k - 0.0085 S) <= 15 S
    cap = vcap(k, S, vmax)
    v = np.minimum(v, cap)
    if caps is not None: v = np.minimum(v, caps)
    for rep in range(3):  # loop twice for closure
        for i in range(2 * N - 1, -1, -1):
            j = i % N; nx = (i + 1) % N
            vn = v[nx]
            lat = min(vn * vn * k[nx] / ay_max(vn, S[nx]), 0.98)
            dec = a_brake_max(vn, S_b) * max(1 - lat ** pb, 0.0) ** (1.0 / pb) + 9.81 * G[nx]
            v[j] = min(v[j], math.sqrt(vn * vn + 2 * dec * ds_path[j]))
        for i in range(0, 2 * N if forward else 0):
            j = i % N; pv = v[(j - 1) % N]
            lat = min(pv * pv * k[(j - 1) % N] / ay_max(pv, S[(j - 1) % N]), 0.98)
            acc = max(float(a_drive(pv)) * max(1 - lat ** pa, 0.0) ** (1.0 / pa) - 9.81 * G[(j - 1) % N], 0.3)
            v[j] = min(v[j], math.sqrt(pv * pv + 2 * acc * ds_path[(j - 1) % N]))
    T = float(np.sum(ds_path / np.maximum(v, 1.0)))
    return v, T

def plan(nmax=4.9, S=1.0, S_b=0.7, N=1203, cache=None, **kw):
    if cache and os.path.exists(cache):
        z = np.load(cache); return {k: z[k] for k in z.files}
    s, n, kc, th, cx, cy, L = optimise_line(N=N, nmax=nmax, **kw)
    P = make_points(n, cx, cy, th)
    k, dsp = path_curv(P)
    dsp = np.hypot(*(np.roll(P, -1, 0) - P).T)
    v, T = speed_profile(k, dsp, S, S_b)
    out = dict(s=s, n=n, kc=kc, k=k, dsp=dsp, v=v, T=T, L=L)
    if cache: np.savez(cache, **out)
    return out

if __name__ == '__main__':
    import sys, time
    t0 = time.time()
    s, kc, th, cx, cy, L = centerline(1203)
    print('L', L, 'heading total (deg)', math.degrees(th[-1] + kc[-1] * L / 1203), 'closure gap (m)', math.hypot(cx[-1] - cx[0], cy[-1] - cy[0]))
    dsc = np.full(1203, L / 1203)
    for S in (0.8, 1.0):
        v, T = speed_profile(kc, dsc, S); print('centre line S', S, 'T', round(T, 2))
    for nm in (2.0, 3.5, 4.9):
        out = plan(nmax=nm, S=1.0)
        print('minK nmax', nm, 'T(S=1)', round(out['T'], 2), 'max|n|', np.abs(out['n']).max().round(2), 'time', round(time.time() - t0, 1))
