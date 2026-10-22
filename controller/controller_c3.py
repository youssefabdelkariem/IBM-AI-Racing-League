"""controller_c1 - independent stock-car Corkscrew controller (Claude Code development line).

Architecture: min-curvature line (c1_plan) + friction-circle speed plan + curvature-command
path follower (feed-forward + slip-aware pure-pursuit correction) + rpm-limit gear rule.
Uses the installed track XML at import time; eligibility of that map use is UNRESOLVED.
No competitor code or tables are used.
"""
import math, os, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import c1_plan as P
import c3_geom as G3

params = dict(
    a0=15.0, a1=0.0, c2=0.0085, ell_b=2.0, ell_a=2.0, seg_f=[], use_env=0, slide_on=9.9, slide_rng=0.1, slide_brk=0.7, grade_k=1.0, cl_launch=0.0, cl_vend=25.0, jmax=0.0, tight_k0=0.012, tight_rng=0.02, tight_drop=0.0, asat=1e9,
    nmax=4.9, S=1.0, S_b=0.7, vmax_kmh=300.0,
    acc_up=0.05, acc_dn=0.25, brk_up=0.35, brk_dn=0.25,
    k_beta=0.5, beta_cap=0.15, rec_on=0.15, rec_rng=0.15, mis_on=1000.0, mis_rng=10.0, start_blend=250.0, bar_pos=0.8, k_bar=0.1, g_cap=0.12, S_live=0.95, live_k=1.0,
    tc_on=4.5, tc_corner=1.5, tc_range=3.0, abs_on=0.12,
    p_cl=2.5, tau=0.3, c_scale=0.0, kv=0.8, eb=2.0, edge_pos=0.88, edge_k=0.5,
    L_eff=4.1, K_us=0.00166, steer_rate=0.20, ki=4.0, kp_k=0.15, ex_scale=1.0, k_filter=0.25, di_max=0.12,
    brake_gain=0.12, brake_lead=0.18, thr_gain=0.45,
    guard_err=1.8, guard_k=0.5, line_file='',
    up_rpm=17900., sel_rpm=17500., down_rpm=16800., dwell=0.30,
    caps=[],  # [(d0,d1,kmh)]
    c3_file='', c3_kv=0.0, c3_lead=0.0, sh_d=0.0, sh_a=3200.0, sh_b=3320.0, sh_taper=15.0, hs_dk=0.0, hs_a=3235.0, hs_b=3295.0, hb_a=3245.0, hb_b=3292.0, hb_kb=0.3, hb_rec=0.0, ln_nods=0.0, ln_slip=0.0, ln_v=160.0, kv_lo=0.0, hp0=3130.0, hp1=0.0, hp_fade=4.0, hp_kv=1.5, bump_dp=0.0, bump_a=0.0, bump_d0=395.0, bump_d1=560.0, bump_nmax=4.5, rc_on=0.0, rc_a=790.0, rc_b=840.0, xt2_a=0.0, xt2_b=0.0, xt_kv=0.0, xt_a=2715.0, xt_b=2815.0, ls_f=0.0, ls_a=1840.0, ls_b=1935.0, pb2_m=0.0, pb2_a=1850.0, pb2_b=1970.0, pb2_dec=12.0, pb_m=0.0, pb_a=1400.0, pb_b=1570.0, pb_h=140.0, pb_dec=20.0, lf_m=0.0, lf_a=1485.0, lf_b=1580.0, hp_cap=0.0, hp_a0=3240.0, hp_a1=3285.0, hp_pre=0.0, hp_p0=3218.0, hp_p1=3243.0, hp_prev=0.0, hp_s0=3195.0, hp_s1=3262.0, hp_vap=0.0, hp_dap=3268.0, hp_a=10.0, cl_slip=0.0, cl_top=17000.0, cl_k=60.0, cl_shift_n=3, min_gear=1, tc_vs=0.0, tc_x=0.0,
)
L = 3608.45
N = 1203
_line = None; _vplan = None; _nref = None; _kref = None; _ds = None

def _build():
    global _line, _vplan, _nref, _kref, _ds, L
    cache = params['line_file'] or str(HERE / f"line_{params['nmax']}.npz")
    out = P.plan(nmax=params['nmax'], S=params['S'], S_b=params['S_b'], cache=cache)
    L = float(out['L']); n = out['n']; k = np.array(out['k']); dsp = np.array(out['dsp'])
    # the reconstructed centre line does not close at the start/finish seam: remove the artefact
    k[[0, 1]] = k[2]; k[[-2, -1]] = k[-3]; dsp[-1] = dsp[-2]
    if params['bump_a'] != 0.0:
        # local trajectory change: smooth lateral offset (m, + = left) over [bump_d0, bump_d1], road clearance limited;
        # path curvature and length recomputed from the shifted points
        _s, _kc, _th, _cx, _cy, _L = P.centerline(len(n))
        _x = np.arange(len(n)) * (L / len(n))
        _d0, _d1 = params['bump_d0'], params['bump_d1']
        _dp = params['bump_dp'] if params['bump_dp'] > 0.0 else 0.5 * (_d0 + _d1)   # peak position (asymmetric window)
        _w = np.where((_x > _d0) & (_x <= _dp), np.sin(0.5 * math.pi * (_x - _d0) / (_dp - _d0)) ** 2,
                      np.where((_x > _dp) & (_x < _d1), np.cos(0.5 * math.pi * (_x - _dp) / (_d1 - _dp)) ** 2, 0.0))
        n = np.clip(np.asarray(n) + params['bump_a'] * _w, -params['bump_nmax'], params['bump_nmax'])
        _P = P.make_points(n, _cx, _cy, _th)
        k, _ = P.path_curv(_P)
        k = np.array(k); k[[0, 1]] = k[2]; k[[-2, -1]] = k[-3]
        dsp = np.hypot(*(np.roll(_P, -1, 0) - _P).T); dsp[-1] = dsp[-2]
    ds = L / len(n)
    caps = np.full(len(n), params['vmax_kmh'] / 3.6)
    for d0, d1, kmh in params['caps']:
        idx = np.arange(len(n)) * ds
        caps[(idx >= d0) & (idx <= d1)] = np.minimum(caps[(idx >= d0) & (idx <= d1)], kmh / 3.6)
    if params['jmax'] > 0:   # lateral-jerk limit: the car cannot build yaw rate instantly in S-bends
        dk = np.abs(np.gradient(k, ds))
        dk = np.maximum.reduce([dk, np.roll(dk, 1), np.roll(dk, -1), np.roll(dk, 2), np.roll(dk, -2)])
        caps = np.minimum(caps, (params['jmax'] / np.maximum(dk, 1e-6)) ** (1.0 / 3.0))
    if params['sh_d'] != 0.0:
        # hairpin entry: bring the line's turn-in earlier by warping the offset profile n(s) -> n(s + sh_d) inside a tapered window
        _s, _kc, _th, _cx, _cy, _L = P.centerline(len(n))
        _x = np.arange(len(n)) * (L / len(n))
        n0 = np.asarray(n, float)
        n_sh = np.interp(_x + params['sh_d'], _x, n0)
        tp_ = params['sh_taper']
        _w = np.clip((_x - params['sh_a']) / tp_, 0.0, 1.0) * np.clip((params['sh_b'] - _x) / tp_, 0.0, 1.0)
        _w = _w * _w * (3 - 2 * _w)
        n = n0 + _w * (n_sh - n0)
        _P = P.make_points(n, _cx, _cy, _th)
        k, _ = P.path_curv(_P)
        k = np.array(k); k[[0, 1]] = k[2]; k[[-2, -1]] = k[-3]
        dsp = np.hypot(*(np.roll(_P, -1, 0) - _P).T); dsp[-1] = dsp[-2]
    S_arr = params['S'] * (1.0 - params['tight_drop'] * np.clip((np.abs(k) - params['tight_k0']) / params['tight_rng'], 0.0, 1.0))
    global _WIN
    _WIN = _corner_windows(k, ds)
    sf = params['seg_f']
    if sf:
        scale = np.ones(len(n)); xs = np.arange(len(n)) * ds
        for (a, b), f in zip(_WIN, sf):
            m = (xs >= a) & (xs <= b)
            scale[m] = f
        # smooth the steps so the plan stays continuous
        kern = np.ones(11) / 11.0
        scale = np.convolve(np.concatenate([scale[-5:], scale, scale[:5]]), kern, mode='valid')
        S_arr = S_arr * scale
    global _GR
    _GR = P.grade_array(len(n)) * params['grade_k']
    v, T = P.speed_profile(k, dsp, S_arr, params['S_b'], caps=caps, pb=params['ell_b'], pa=params['ell_a'], grade=_GR)
    if params['use_env']:   # braking envelope only: brake points follow the car's real speed, not an optimistic accel model
        v_env, _ = P.speed_profile(k, dsp, S_arr, params['S_b'], caps=caps, pb=params['ell_b'], pa=params['ell_a'], grade=_GR, forward=False)
        v_env = np.minimum(v_env, params['vmax_kmh'] / 3.6)
        env = v_env
    else:
        env = None
    # standing start: the car begins 10 m before the line at rest (cyclic profile assumes a flying lap)
    v = v.copy(); v[0] = min(v[0], math.sqrt(2 * 12.0 * 10.0))
    for i in range(1, len(v)):
        ax_ = float(P.a_drive(v[i - 1]))
        v[i] = min(v[i], math.sqrt(v[i - 1] ** 2 + 2 * ax_ * dsp[i - 1]))
    global _TH
    _nref, _kref, _vplan, _ds = n, k, (env if env is not None else v), ds
    _TH = P.centerline(len(n))[2]
    _line = dict(T=T)
    # c3 unified local plan: inside its windows the path, its curvature, the speed plan and the feed-forward lead all
    # come from one trajectory built with the telemetry-calibrated response model (c3_build.py). w = 0 elsewhere.
    global _LEADT, _LEADV, _WG, _WS, _PSIW
    _LEADT = None; _LEADV = None; _WG = None; _WS = None; _PSIW = None
    if params['c3_file']:
        z = np.load(HERE / params['c3_file'])
        wg = np.asarray(z['wg'], float); ws = np.asarray(z['ws'], float)
        _nref = np.asarray(z['n'], float); _kref = np.asarray(z['k'], float)
        _vplan = (1.0 - ws) * np.asarray(_vplan, float) + ws * np.minimum(np.asarray(z['v'], float), params['vmax_kmh'] / 3.6)
        lt = params['c3_lead'] if params['c3_lead'] > 0.0 else float(z['tau_s'])
        _LEADT = params['tau'] * (1.0 - wg) + lt * wg                       # steering lead = identified response delay
        _LEADV = params['brake_lead'] * (1.0 - ws) + float(z['tau_b']) * ws   # speed lead = brake actuation delay
        _WG = wg; _WS = ws; _PSIW = np.asarray(z['psiw'], float)

_LEADT = None; _LEADV = None; _WG = None; _WS = None; _PSIW = None

def _psi_line(d):
    """world heading of the planned path at d (seam-safe: the exact road closes at 2*pi)"""
    x = (d % L) / _ds
    i = int(x); f = x - i; m = len(_PSIW)
    a = _PSIW[i % m]; b_ = _PSIW[i + 1] if i + 1 < m else _PSIW[0] + 2.0 * math.pi
    return a * (1 - f) + b_ * f

_WIN = []
def _corner_windows(k, ds, k_on=0.006, gap=40.0, pad=35.0):
    """Corner windows (start,end metres): contiguous regions with |path curvature| > k_on, merged and padded."""
    xs = np.arange(len(k)) * ds
    on = np.abs(k) > k_on
    wins = []; i = 0; N = len(k)
    while i < N:
        if on[i]:
            j = i
            while j + 1 < N and on[j + 1]: j += 1
            wins.append([xs[i], xs[j]]); i = j + 1
        else:
            i += 1
    merged = []
    for w in wins:
        if merged and w[0] - merged[-1][1] < gap: merged[-1][1] = w[1]
        else: merged.append(list(w))
    return [(max(0.0, a - pad), min(xs[-1], b + pad)) for a, b in merged]

def configure(values):
    params.update(values)
    P.MODEL.update(a0=params['a0'], a1=params['a1'], c2=params['c2'], asat=params['asat'])
    _build()

def _at(arr, d):
    x = (d % L) / _ds
    i = int(x); f = x - i; m = len(arr)
    return arr[i % m] * (1 - f) + arr[(i + 1) % m] * f

_state = dict(accel=0.0, brk=0.0, steer=0.0, gear=1, shift_t=-10.0, t=0.0, brake=0.0, yaw=None, clock=None, kmeas=0.0, di=0.0)
_TH = None
_GR = None
G = [0.0, 3.9, 2.9, 2.3, 1.87, 1.68, 1.54]; FD = 4.5; RR = 0.3151; RF = 0.3024
def _rpm(v, g):
    return v / RR * G[g] * FD * 60.0 / (2 * math.pi)

def _clip(x, a, b): return max(a, min(b, x))

def drive(client):
    s = client.S.d; r = client.R.d
    try:
        d = float(s['distFromStart']); vx = float(s['speedX']) / 3.6; vy = float(s['speedY']) / 3.6
        ang = float(s['angle']); pos = float(s['trackPos']); clock = float(s['curLapTime'])
        wsv = s['wheelSpinVel']; rpm = float(s['rpm']) / (math.pi / 3.0); gear = int(s['gear'])
    except (KeyError, TypeError, ValueError):
        r['accel'] = 0.0; r['brake'] = 0.3; return {'mode': 'invalid'}
    v = max(vx, 0.0)
    n_car = pos * 6.0
    course = -ang + math.atan2(vy, max(vx, 3.0))

    # ---- lateral: curvature command -> steering -------------------------------------------
    n_0 = _at(_nref, d)
    slope = (_at(_nref, d + 2.0) - _at(_nref, d - 2.0)) / 4.0
    sd = d - (L - 10.0) if d > L - 30.0 else d + 10.0     # distance travelled since the grid
    if sd < params['start_blend']:
        b = max(0.0, sd) / params['start_blend']; b = b * b * (3 - 2 * b)
        n_0 = 2.0 * (1 - b) + n_0 * b; slope *= b
    ey = n_car - n_0
    e_psi = course - math.atan(slope)
    wg_ = _at(_WG, d) if _WG is not None else 0.0
    ws_ = _at(_WS, d) if _WS is not None else 0.0
    if wg_ > 0.0 and sd >= params['start_blend'] and d < L - 15.0:   # (the stored line is not constrained at the lap seam)
        # exact road: heading error in the world frame (car course vs the planned path's world heading)
        e_w = (G3.th_at(d) + course) - _psi_line(d)
        e_w = (e_w + math.pi) % (2.0 * math.pi) - math.pi
        e_psi = (1.0 - wg_) * e_psi + wg_ * e_w
    # Frenet error dynamics with a first-order curvature lag (tau): triple-pole placement at -p.
    p_cl = params['p_cl']; tau = params['tau']; vv = max(v, 10.0)
    ga = p_cl ** 3 * tau / (vv * vv); gb = 3 * p_cl ** 2 * tau / vv; gc = max(3 * p_cl * tau - 1.0, 0.0) * params['c_scale']
    ek = _state['kmeas'] - _at(_kref, d)
    pv_la = (tau if _LEADT is None else _at(_LEADT, d)) * v
    if params['hp_prev'] > 0.0 and params['hp_s0'] <= d < params['hp_s1']:
        pv_la = max(pv_la, params['hp_prev'])   # hairpin: longer curvature preview so turn-in starts progressively
    if params['ls_f'] > 0.0 and params['ls_a'] <= d < params['ls_b']:
        pv_la = tau * v * params['ls_f']   # 1,931 m approach: curvature is ramping up, a full preview turns in early
    k_ff = _at(_kref, d + pv_la)
    if sd < params['start_blend']: k_ff *= b
    k_cmd = k_ff - (ga * ey + gb * e_psi + gc * ek)
    if abs(pos) > params['bar_pos']:
        k_cmd -= math.copysign(params['k_bar'] * (abs(pos) - params['bar_pos']), pos)
    e_la = ey
    st = _state
    if params['hs_dk'] > 0.0 and params['hs_a'] <= d < params['hs_b']:
        # hairpin turn-in: slew-limit the curvature command so the yaw builds progressively instead of stepping
        kp_ = st.get('kc_prev', k_cmd)
        k_cmd = _clip(k_cmd, kp_ - params['hs_dk'], kp_ + params['hs_dk'])
    st['kc_prev'] = k_cmd
    # measured path curvature from yaw rate (yaw = track heading - angle)
    yaw = _at(_TH, d) - ang
    yaw_e = (G3.th_at(d) - ang) if _WG is not None else yaw      # exact track heading (no 3 m grid artefacts at arc ends)
    if st['yaw'] is not None and st['clock'] is not None and clock > st['clock'] and abs(yaw - st['yaw']) < 0.5:
        yr = (yaw - st['yaw']) / (clock - st['clock'])
        if wg_ > 0.0 and st.get('yaw_e') is not None and abs(yaw_e - st['yaw_e']) < 0.5:
            yr = (1.0 - wg_) * yr + wg_ * (yaw_e - st['yaw_e']) / (clock - st['clock'])
        km = yr / max(v, 5.0)
        st['kmeas'] += params['k_filter'] * (km - st['kmeas'])
    st['yaw'] = yaw; st['yaw_e'] = yaw_e; st['clock'] = clock
    gain = params['L_eff'] + params['K_us'] * v * v
    ay_c = v * v * abs(k_cmd)
    es = params['ex_scale']
    u_c = ay_c / P.ay_max(v, 1.0)
    g_ex = float(np.interp(u_c, [0, 0.5, 0.62, 0.78, 0.95, 1.1], [0, 0, 0.03, 0.085 * es, 0.095 * es, 0.12 * es]))
    delta_ff = params['L_eff'] * k_cmd + math.copysign(g_ex, k_cmd)
    act = v > 8.0 and clock > 1.0
    if act:
        st['di'] = _clip(st['di'] + params['ki'] * (k_cmd - st['kmeas']) * params['L_eff'] * 0.02, -params['di_max'], params['di_max'])
    else:
        st['di'] = 0.0
    delta = delta_ff + st['di'] + (params['kp_k'] * params['L_eff'] * (k_cmd - st['kmeas']) if act else 0.0)
    d_cap = params['L_eff'] * max(abs(k_ff), abs(st['kmeas'])) + params['g_cap']
    delta = _clip(delta, -d_cap, d_cap)
    hb = params['hb_rec'] > 0.0 and params['hb_a'] <= d < params['hb_b']   # hairpin apex: keep rotating, less slide-recovery
    if v > 8.0 and clock > 1.0:   # counter-steer: front wheels toward the velocity vector
        delta += _clip((params['hb_kb'] if hb else params['k_beta']) * math.atan2(vy, max(vx, 3.0)), -params['beta_cap'], params['beta_cap'])
    beta = math.atan2(vy, max(vx, 3.0))
    rec_on = params['rc_on'] if (params['rc_on'] > 0.0 and params['rc_a'] <= d < params['rc_b']) else params['rec_on']
    if hb: rec_on = params['hb_rec']
    w_rec = _clip((abs(beta) - rec_on) / params['rec_rng'], 0.0, 1.0) if v > 4.0 else 0.0
    if w_rec > 0.0:   # spin recovery: point the front wheels along the velocity vector
        delta = (1 - w_rec) * delta + w_rec * _clip(beta, -0.3665, 0.3665)
    steer = _clip(delta / 0.3665, -1.0, 1.0)
    if params['hp_pre'] != 0.0 and params['hp_p0'] <= d < params['hp_p1'] + 7.0:
        # hairpin pre-rotation: progressive turn-in while still trail-braking, handed over to the line follower at hp_p1
        w = _clip((d - params['hp_p0']) / (params['hp_p1'] - params['hp_p0']), 0.0, 1.0) * _clip((params['hp_p1'] + 7.0 - d) / 7.0, 0.0, 1.0)
        steer = _clip(steer + params['hp_pre'] * w, -1.0, 1.0)
    st = _state
    hp_ap = params['hp_cap'] > 0.0 and params['hp_a0'] <= d < params['hp_a1']
    if hp_ap:   # hairpin apex: beyond this lock the fronts only scrub speed
        steer = _clip(steer, -params['hp_cap'], params['hp_cap'])
    steer = _clip(steer, st['steer'] - params['steer_rate'], st['steer'] + params['steer_rate'])
    st['steer'] = steer

    # ---- longitudinal -----------------------------------------------------------------------
    lead = params['brake_lead'] if _LEADV is None else _at(_LEADV, d)
    # end of lap: clamp the look-ahead at the last plan sample - interpolating past it wraps into index 0, which holds the
    # standing-start speed cap (lap one only), and made the car brake for the finish line
    dl = min(d + v * lead, L - _ds) if d > 0.5 * L else d + v * lead
    v_t = _at(_vplan, dl); v_raw = v_t; lim = 0
    n_now = _at(_nref, d)
    err = abs(n_car - n_now)
    if err > params['guard_err']:
        v_t = max(v_t - params['guard_k'] * (err - params['guard_err']) * 3.0, 15.0); lim |= 1
    ap = abs(pos)
    if ap > params['edge_pos']:
        v_t = max(v_t - params['edge_k'] * (ap - params['edge_pos']) * 100.0 / 3.6, 15.0); lim |= 2
    # live limiter: if the curvature being demanded exceeds what the tyres can give, slow down
    v_a = _at(_vplan, min(dl + 8.0, L - _ds) if d > 0.5 * L else dl + 8.0)
    for _m, _za, _zb, _dec in ((params['pb_m'], params['pb_a'], params['pb_b'], params['pb_dec']),
                               (params['pb2_m'], params['pb2_a'], params['pb2_b'], params['pb2_dec'])):
        if _m > 0.0 and _za <= d < _zb:
            # predictive braking: speed from which the planned path's upcoming curvature (not the live steering
            # demand) is reachable at a feasible deceleration (zone 1: 1,528 m corner, zone 2: 1,931 m corner)
            def _pb_env(x, _m=_m, _dec=_dec):
                best = 1e9
                for sx in range(0, int(params['pb_h']) + 1, 8):
                    kk = abs(_at(_kref, x + sx)) * _m
                    if kk > 1e-6:
                        vc = float(P.vcap(kk, params['S_live']))
                        best = min(best, math.sqrt(vc * vc + 2.0 * _dec * sx))
                return best
            v_t = min(v_t, _pb_env(d)); v_a = min(v_a, _pb_env(d + 8.0)); lim |= 8
    if params['hp_vap'] > 0.0 and 3190.0 <= d < params['hp_dap']:
        # hairpin apex envelope: speed from which the apex speed is reachable at a lateral-load-limited deceleration,
        # so braking continues through turn-in (trail braking) instead of ending at the plan's optimistic apex speed
        va = params['hp_vap'] / 3.6
        env = lambda x: math.sqrt(va * va + 2.0 * params['hp_a'] * max(params['hp_dap'] - x, 0.0))
        v_t = min(v_t, env(d)); v_a = min(v_a, env(d + 8.0))
    a_plan = (v_a * v_a - v_t * v_t) / 16.0
    kd = abs(k_cmd) * params['live_k']
    if params['lf_m'] > 0.0 and params['lf_a'] <= d < params['lf_b']:
        # 1,528 m corner: the slide-recovery feedback inflates k_cmd and the limiter then slows the car further;
        # limit on the line's own curvature (with margin) instead
        kd = min(kd, abs(k_ff) * params['lf_m'] * params['live_k'])
    if kd > 1e-6:
        v_lim = float(P.vcap(kd, params['S_live']))
        if v_lim < v_t:
            v_t = v_lim; a_plan = min(a_plan, 0.0); lim |= 4
    e = v - v_t
    if params['hp1'] > 0.0 and params['hp0'] <= d < params['hp1'] and e < 0.0:
        # hairpin entry: the plan's braking feed-forward fades out as the car falls below the plan (progressive release)
        a_plan *= _clip(1.0 + e / params['hp_fade'], 0.0, 1.0)
        a_cmd = a_plan - params['hp_kv'] * e
    elif params['xt_kv'] > 0.0 and e < 0.0 and (params['xt_a'] <= d < params['xt_b'] or params['xt2_a'] <= d < params['xt2_b']):
        a_cmd = a_plan - params['xt_kv'] * e   # exit window: below the target speed, ask for full acceleration sooner
    else:
        a_cmd = a_plan - (params['kv'] if (e >= 0.0 or params['kv_lo'] <= 0.0) else params['kv_lo']) * e
        if ws_ > 0.0 and e < 0.0 and params['c3_kv'] > 0.0:
            # inside a c3 speed window the plan is the feasible speed: hold it (no coasting below it on engine braking)
            a_cmd = a_plan - (params['kv'] + ws_ * (params['c3_kv'] - params['kv'])) * e
    gr = 9.81 * _at(_GR, d)
    drag = 0.002 * v * v + gr
    accel = 0.0; brake = 0.0
    if a_cmd >= 0.0:
        full = float(P.a_drive(v)) + drag
        accel = _clip((a_cmd + drag) / max(full, 1.0), 0.0, 1.0)
    else:
        need = -a_cmd - (drag + params['eb'])
        if need > 0.0:
            brake = _clip(need / max(P.a_brake_max(v, params['S_b']), 10.0), 0.0, 1.0)
    # stability gate: lateral acceleration mismatch between commanded and measured curvature
    if v > 12.0 and clock > 3.0:
        mis = abs(st['kmeas'] - k_cmd) * v * v
        if mis > params['mis_on']:
            accel *= max(0.0, 1.0 - (mis - params['mis_on']) / params['mis_rng'])
    if v > 10.0:   # ESC-like slide limiter: relieve throttle (and partly brake) when side-slip grows
        s_sl = _clip((abs(beta) - params['slide_on']) / params['slide_rng'], 0.0, 1.0)
        accel *= (1 - s_sl); brake *= (1 - params['slide_brk'] * s_sl)
    if w_rec > 0.0:
        accel *= (1 - w_rec); brake *= (1 - w_rec)
    if hp_ap:   # no braking on top of high steering lock
        brake *= 1.0 - _clip((abs(steer) - 0.45) / 0.25, 0.0, 1.0)
    if d > L - 30.0 and clock < 6.0:   # standing start, grid is 10 m before the line
        accel, brake = 1.0, 0.0
    # traction control (rear), linear
    try:
        wr = (float(wsv[2]) + float(wsv[3])) * 0.5 * RR
        wf = (float(wsv[0]) + float(wsv[1])) * 0.5 * RF
    except Exception:
        wr = v; wf = v
    if 'launch' not in st: st['launch'] = True
    if st['launch'] and (v > params['ln_v'] / 3.6 or clock > 9.0): st['launch'] = False
    ln = params['ln_slip'] > 0.0 and st['launch'] and abs(st['steer']) < 0.3   # standing-start launch phase
    vg = max(v, wr) if ln else v   # gear choice follows the driven wheels while they spin
    if v > 3.0:
        slip = wr - v
        lat_u = min(1.0, (v * v * abs(st['kmeas'])) / P.ay_max(v, 1.0))
        on = params['tc_on'] - (params['tc_on'] - params['tc_corner']) * min(1.0, max(0.0, (lat_u - 0.4) / 0.4))
        if params['tc_vs'] > 0: on *= max(1.0, v / params['tc_vs'])   # slip limit grows with speed (force depends on slip ratio)
        if params['tc_x'] > 0 and v < 36.0 and abs(st['steer']) < 0.3: on += params['tc_x'] * (1 - abs(st['steer']) / 0.3)
        if ln: on += params['ln_slip']
        if slip > on: accel *= max(0.0, 1.0 - (slip - on) / params['tc_range'])
        if brake > 0 and v > 8.0:
            fs = 1.0 - wf / max(v, 1.0)
            if fs > params['abs_on']: brake *= max(0.3, 1.0 - (fs - params['abs_on']) * 6.0)
    # ---- gear rule: lowest gear that stays below the rev limit ------------------------------
    t = clock
    g = gear if 1 <= gear <= 6 else 1
    want = 6
    for gg in range(1, 7):
        if _rpm(vg, gg) < params['sel_rpm']:
            want = gg; break
    if v < 1.0: want = 1
    if v > 8.0 and want < params['min_gear']: want = params['min_gear']
    if v > 8.0 and g < params['min_gear'] and t - st['shift_t'] >= 0.1: g = params['min_gear']; st['shift_t'] = t
    if t < st['shift_t']: st['shift_t'] = -10.0
    if t - st['shift_t'] >= params['dwell']:
        if want > g and (_rpm(vg, g) > params['up_rpm'] or want - g > 1):
            g += 1; st['shift_t'] = t
        elif want < g and not (ln and params['ln_nods'] > 0) and _rpm(vg, g - 1) < params['down_rpm']:
            g -= 1; st['shift_t'] = t
    if g != gear and t - st['shift_t'] < 0.05 and brake == 0.0:
        pass
    accel = _clip(accel, st['accel'] - params['acc_dn'], st['accel'] + params['acc_up'])
    brake = _clip(brake, st['brk'] - params['brk_dn'], st['brk'] + params['brk_up'])
    st['accel'] = accel; st['brk'] = brake
    cl = 0.0
    if params['cl_launch'] > 0 and clock < 6.0 and (d > L - 30.0 or d < 400.0):
        cl = params['cl_launch'] * (1.0 - _clip(v / params['cl_vend'], 0.0, 1.0))
    # Drivetrain-inertia relief (c2): TORCS passes full engine torque for clutch transfer >= 1/3 while the
    # wheels only carry the (free) gearbox inertia scaled by the open share, so a part-open clutch accelerates
    # the wheels faster in low gears. Ease the pedal shut as driven-wheel rpm nears cl_top (engine limiter).
    if g != gear: st['up_n'] = 0
    else: st['up_n'] = st.get('up_n', 99) + 1
    if params['cl_slip'] > 0 and brake == 0.0 and accel > 0.0 and v > 1.0:
        axle = (float(wsv[2]) + float(wsv[3])) * 0.5 * G[g] * FD * 60.0 / (2 * math.pi)
        if axle < params['cl_top']:
            cl = min(params['cl_slip'], 1.0 - (params['cl_k'] / (params['cl_top'] - axle + params['cl_k'])) ** 0.25)
        if st['up_n'] < params['cl_shift_n']:
            cl = params['cl_slip']
    r['steer'] = steer; r['accel'] = accel; r['brake'] = brake; r['gear'] = g; r['clutch'] = cl
    return {'mode': 'DRIVE', 'vt': round(v_t * 3.6, 1), 'vp': round(v_raw * 3.6, 1), 'lim': lim, 'e': round(e, 2), 'ela': round(e_la, 2), 'kcmd': round(k_cmd, 5), 'km': round(st['kmeas'], 5), 'di': round(st['di'], 3), 'g': g}

_build()
