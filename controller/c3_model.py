"""c3_model - compact stock-car response model (no third-party data).

Structure from the stock car file (read-only): front static weight 45 %, CG height / wheelbase = 0.20 / 2.95,
front share of the downforce ~29 % (ground effect 0.2 / 0.7, wing positions), front share of the brake torque ~66 %.
Fitted on our own telemetry (exact-heading lateral acceleration): MU = 1.99, total downforce CT = 0.00281 v^2 per kg.

  axle loads (per unit mass)   Nf = WF g - ax HL + FA CT v^2        Nr = (1-WF) g + ax HL + (1-FA) CT v^2
  tyre longitudinal force      ax + DRAG v^2 : braking split BF / (1-BF), driving on the rear axle only
  lateral capacity             front sqrt((MU Nf)^2 - Fxf^2) / WF ,  rear sqrt((MU Nr)^2 - Fxr^2) / (1-WF)   -> min
  banking b (into the turn)    ay = [mu_e (g cos b + CT v^2) + g sin b] / (cos b - mu_e sin b),  mu_e = flat limit / (g + CT v^2)
  drive / brake caps           a_acc(v), a_brk(v): measured tables (brake table = decelerations the car has demonstrated)
  response                     steering -> path curvature delay TAU_S ~ 0.07 s ; brake actuation TAU_B
"""
import math
import numpy as np

MU, CT, G = 1.99, 0.00281, 9.81
WF, HL, FA, BF, DRAG = 0.45, 0.20 / 2.95, 0.29, 0.66, 0.0016
ETA = 1.0
TAU_S, TAU_B, L_S = 0.07, 0.06, 5.4
_AV = [0.0, 60.0, 105.0, 135.0, 165.0, 195.0, 225.0, 255.0, 285.0, 310.0, 330.0]
_AA = [14.0, 14.5, 14.9, 13.5, 12.3, 10.8, 7.4, 5.2, 2.7, 1.0, 0.0]
_BV = [0.0, 80.0, 140.0, 180.0, 220.0, 260.0, 300.0]
_BA = [20.0, 22.0, 27.0, 31.6, 34.0, 35.0, 36.0]


def _tab(xs, ys, x):
    if x <= xs[0]: return ys[0]
    if x >= xs[-1]: return ys[-1]
    for i in range(1, len(xs)):
        if x < xs[i]:
            f = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + f * (ys[i] - ys[i - 1])
    return ys[-1]


def a_acc(v): return _tab(_AV, _AA, v * 3.6)


def a_brk(v): return _tab(_BV, _BA, v * 3.6)


def ay_max(v, ax=0.0, bank=0.0, eta=None):
    """lateral acceleration limit (m/s^2) at speed v with longitudinal acceleration ax and banking into the turn"""
    e = ETA if eta is None else eta
    v2 = v * v
    nf = WF * G - ax * HL + FA * CT * v2
    nr = (1.0 - WF) * G + ax * HL + (1.0 - FA) * CT * v2
    fx = ax + DRAG * v2                       # tyre force needed (drag decelerates for free)
    if fx < 0.0: fxf, fxr = BF * (-fx), (1.0 - BF) * (-fx)
    else: fxf, fxr = 0.0, fx
    cf = (MU * nf) ** 2 - fxf * fxf; cr = (MU * nr) ** 2 - fxr * fxr
    if nf <= 0.0 or nr <= 0.0 or cf <= 0.0 or cr <= 0.0: return 0.0
    flat = min(math.sqrt(cf) / WF, math.sqrt(cr) / (1.0 - WF))
    if bank != 0.0:
        mu_e = flat / (G + CT * v2); cb, sb = math.cos(bank), math.sin(bank)
        flat = (mu_e * (G * cb + CT * v2) + G * sb) / max(cb - mu_e * sb, 0.3)
    return e * flat


def feasible(v, k, ax, bank=0.0, eta=None):
    return v * v * abs(k) <= ay_max(v, ax, bank, eta)


def ax_range(v, k, bank=0.0, eta=None, grade=0.0):
    """(strongest feasible deceleration <= 0, strongest feasible acceleration) at speed v on curvature k; None if infeasible"""
    lo_cap = -a_brk(v); hi_cap = a_acc(v)
    ay = v * v * abs(k)
    f = lambda a: ay <= ay_max(v, a, bank, eta)
    best = None                                   # most favourable ax for lateral grip lies under light braking
    for a in (0.0, -2.0, -4.0, -6.0, -9.0, -12.0, -16.0, -20.0, -25.0, -30.0, 2.0, 4.0):
        if lo_cap <= a <= hi_cap and f(a): best = a; break
    if best is None: return None
    lo, hi = lo_cap, best                         # deceleration limit
    if f(lo_cap): amin = lo_cap
    else:
        for _ in range(18):
            m = 0.5 * (lo, hi)[0] + 0.5 * (lo, hi)[1]
            if f(m): hi = m
            else: lo = m
        amin = hi
    lo, hi = best, hi_cap                         # acceleration limit
    if f(hi_cap): amax = hi_cap
    else:
        for _ in range(18):
            m = 0.5 * (lo + hi)
            if f(m): lo = m
            else: hi = m
        amax = lo
    return amin - G * grade * 0.0, amax


def v_cap(k, bank=0.0, eta=None, vmax=95.0):
    """largest speed at which curvature k can be held for some feasible ax (light trail braking allowed)"""
    if ax_range(vmax, k, bank, eta) is not None: return vmax
    lo, hi = 1.0, vmax
    for _ in range(22):
        m = 0.5 * (lo + hi)
        if ax_range(m, k, bank, eta) is not None: lo = m
        else: hi = m
    return lo


def speed_profile(k, ds, v_in=None, v_out=None, eta=None, grade=None, bank=None, vmax=95.0):
    """Quasi-steady-state profile on an open path with the axle-load g-g model. Arrays k, ds (, grade, bank into turn)."""
    n = len(k); k = [abs(float(x)) for x in k]; ds = [float(x) for x in ds]
    gr = [0.0] * n if grade is None else [float(x) for x in grade]
    bk = [0.0] * n if bank is None else [float(x) for x in bank]
    v = [v_cap(k[i], bk[i], eta, vmax) for i in range(n)]
    if v_in is not None: v[0] = min(v[0], v_in)
    if v_out is not None: v[-1] = min(v[-1], v_out)
    for _pass in range(2):
        for i in range(n - 2, -1, -1):            # backward: can the car slow from v[i] to v[i+1] over ds[i]?
            vn = v[i + 1]
            if v[i] <= vn: continue
            def ok(vi):
                ax = (vn * vn - vi * vi) / (2.0 * ds[i]) + G * gr[i]      # tyre/drag deceleration needed (uphill helps)
                r = ax_range(vi, k[i], bk[i], eta)
                return r is not None and ax >= r[0]
            if ok(v[i]): continue
            lo, hi = vn, v[i]
            for _ in range(18):
                m = 0.5 * (lo + hi)
                if ok(m): lo = m
                else: hi = m
            v[i] = lo
        for i in range(1, n):                     # forward: acceleration (or forced deceleration) from the previous point
            pv = v[i - 1]
            r = ax_range(pv, k[i - 1], bk[i - 1], eta)
            amax = (r[1] if r is not None else -a_brk(pv)) - G * gr[i - 1]
            lim = math.sqrt(max(pv * pv + 2.0 * amax * ds[i - 1], 1.0))
            if lim < v[i]: v[i] = lim
    return np.array(v)


def lap_time(v, ds):
    return float(np.sum(np.asarray(ds) / np.maximum(np.asarray(v), 1.0)))
