"""controller_v3_4.py — IBM AI Racing League Stage D (Predictive Braking)

BASE: controller_v3_3_1.py (accepted SHA-256
      ca154ce3035109b89b6a3e073e26e9e7e263bc6cc01a182fd1546e14ce210e5a)

PROVENANCE: Source authored by Bob (IBM AI assistant).  Predictive braking
envelope added at the Corkscrew chicane based on telemetry extracted from
the V3.3.1 official race by Codex (v331-chicane-comparison.csv).

══════════════════════════════════════════════════════════════════════════════
STAGE D SCOPE — PREDICTIVE BRAKING ENVELOPE ONLY
══════════════════════════════════════════════════════════════════════════════
TARGET_MAX_KMH = 100 is UNCHANGED.
TC formula (onset 0.5 m/s, range 3.0 m/s), steering, gearing, recovery,
emergency caps, and all other V3.3.1 behaviour are UNCHANGED.

One new function _predictive_corner_cap() is added.
One new step 2b is inserted in drive_v3_4() between the existing safety-cap
pipeline (step 2) and the target_spd = min(TARGET_MAX_KMH, safe_target) line.

══════════════════════════════════════════════════════════════════════════════
MOTIVATION — TELEMETRY EVIDENCE
══════════════════════════════════════════════════════════════════════════════
V3.3.1 official race (SHA ca154ce..., distRaced ≈ distFromStart + 10 m):

  distRaced 2485.13 (distFromStart ~2475): speed 55.72, slip 2.58, TC active
  distRaced 2490.13 (distFromStart ~2480): speed 62.19, angle -0.176, TC blank
  distRaced 2494.81 (distFromStart ~2485): speed 64.78, angle -0.273, emerg 30
  distRaced 2500.03 (distFromStart ~2490): speed 34.23, angle -0.469

  Peak angle -0.505 rad at distRaced 2500.87 (distFromStart ~2491),
  speed 29.95 km/h, emergency_angle, TC blank.

V3.2.1 reference (same zone): emergency at distFromStart ~2484, speed 43.4
  lower entry but reactive angle cap already firing sooner.

The TC-restored traction in V3.3.1 allowed higher speed at the chicane entry,
but the reactive heading cap (triggered at angle > ANGLE_HARD = 0.26 rad)
cannot anticipate the upcoming tight geometry.  The car enters the tight
section at ~64 km/h when it needs to be at ~40 km/h, then brakes hard and
overshoots heading.

══════════════════════════════════════════════════════════════════════════════
SOLUTION — STATIC PREDICTIVE BRAKING PROFILE
══════════════════════════════════════════════════════════════════════════════
A single chicane zone is defined by a measured distFromStart window
(2470–2500 m on the Corkscrew circuit).  Outside the zone but within a
150 m preview window, a predictive approach cap is computed from kinematics:

  v_cap_ms  = sqrt(v_zone_ms² + 2 × PLAN_DECEL × max(d_to_zone − PLAN_MARGIN, 0))
  cap_km/h  = v_cap_ms × 3.6

where:
  v_zone_ms = PLAN_ZONE_SPEED / 3.6 = 40.0 / 3.6 = 11.111 m/s
  PLAN_DECEL = 5.0 m/s²   (braking deceleration assumed available)
  PLAN_MARGIN = 5.0 m      (anticipation margin; cap = zone speed at d = margin)
  PLAN_PREVIEW = 150.0 m   (beyond this, cap > 100 km/h → no effect)

Cap values at selected distances to zone entry (2470 m):
  d_to_zone = 150 m → cap = 142.8 km/h  → clamped to 100 (no effect)
  d_to_zone =  50 m → cap =  86.2 km/h
  d_to_zone =  25 m → cap =  64.8 km/h  (matches observed V3.3.1 speed at ~2485)
  d_to_zone =   5 m → cap =  40.0 km/h  (exactly at margin)
  inside zone (d ≤ 0)  → cap =  40.0 km/h

This cap is applied as:
  safe_target = min(safe_target, planned_cap)
AFTER all existing emergency/sensor/scalar caps.  It can never raise a target
already lowered by emergency logic (min is monotone).

40 km/h is a conservative initial hypothesis derived from the trajectory
evidence, not an established optimal grip limit.  This is a stability
improvement candidate; speed gains may require subsequent tuning.

══════════════════════════════════════════════════════════════════════════════
COMPETITION MAP ASSUMPTION — PROVENANCE AND STATUS
══════════════════════════════════════════════════════════════════════════════
The zone definition (distFromStart 2470–2500 m, track length 3608.45 m)
is derived exclusively from SCR telemetry collected during official and
practice races on this TORCS installation.  No car XML, track XML, or
simulator-internal files are read at runtime.

The IBM AI Racing League competition rules permit AI code changes.  Whether
static in-code circuit maps derived from practice telemetry are permitted
under the specific competition rules has NOT been independently certified.
This is flagged as an assumption; if the rules prohibit telemetry-derived
circuit maps, this approach requires revision.

══════════════════════════════════════════════════════════════════════════════
DISTANCE VALIDITY AND RANGE VALIDATION
══════════════════════════════════════════════════════════════════════════════
distFromStart is read from the SCR sensor.  It can be:
  - Valid and in range [0, TRACK_LENGTH): normal racing, use raw value
  - Valid near-end-of-lap: e.g. ~3598 m on final approach (this is correct;
    distance to zone is ~480 m, no cap fires)
  - Negative or >= TRACK_LENGTH: treated as invalid, fallback cap fires
  - Non-finite, None, or non-parseable (sensor fault): invalid, fallback fires

distFromStart is a within-lap distance (not cumulative odometer).  Valid
values are strictly in [0, TRACK_LENGTH).  Any value outside this range
is rejected with PLAN_INVALID_CAP — no modulo wrapping is applied.

  d < 0                  → PLAN_INVALID_CAP (pre-grid / sensor glitch)
  d >= TRACK_LENGTH      → PLAN_INVALID_CAP (wrap-around glitch / bad read)
  d == TRACK_LENGTH      → invalid (would silently become 0 if wrapped)
  0 <= d < TRACK_LENGTH  → use raw value directly

Invalid/non-finite distFromStart: fallback cap = PLAN_INVALID_CAP = 30.0
km/h (conservative; same as EMERGENCY_KMH).  This ensures a sensor-faulted
distance does not silently place the car at a "safe" map position.

══════════════════════════════════════════════════════════════════════════════
WHAT IS UNCHANGED FROM V3.3.1
══════════════════════════════════════════════════════════════════════════════
  - All TC: onset 0.5, range 3.0, wsv_tc_valid launch gate
  - All steering, curvature, lookahead, boundary caps, emergency logic
  - All transmission: _select_gear_v321, anti-hunting guards
  - All recovery logic, stuck/reverse counters, lap-clock rollback
  - All vehicle constants, torque curve, gear ratios, wheel radii
  - TARGET_MAX_KMH = 100, all ACCEL/BRAKE/STEER parameters
  - Command bounds: steer [-1,1], accel [0,1], brake [0,1], gear {-1..6}
"""

import csv
import hashlib
import importlib.util
import json
import math
import socket
import sys
import time
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent
ORIGINAL = ROOT / "snakeoil3_gym.py"
OUTPUT   = ROOT

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("snakeoil_base", ORIGINAL)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

_MISSING = object()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TUNABLE PARAMETERS — unchanged from V3.3.1 except the new PLAN_* block
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TARGET_MAX_KMH        = 100.0
TARGET_MIN_KMH        =  40.0
EMERGENCY_KMH         =  30.0

STEER_ANGLE_GAIN      = 1.75
STEER_CENTER_GAIN     = 0.38
STEER_SPEED_DAMP      = 2.5

ACCEL_MAX             = 0.85
BRAKE_MAX             = 0.75
ACCEL_RAMP_DIV        = 14.0
BRAKE_RAMP_DIV        = 14.0
BRAKE_ACCEL_THRESHOLD = 0.04

FORWARD_STRAIGHT      = 150.0
ASYM_SCALE            = 0.70
FWD_SCALE             = 0.30
CURVATURE_SHARPNESS   = 1.4

LOOKAHEAD_DECAY_WEIGHT = 0.40

TC_LINEAR_ONSET       = 0.5
TC_LINEAR_RANGE       = 3.0

BOUNDARY_SOFT         = 0.60
BOUNDARY_HARD         = 0.85
ANGLE_HARD            = 0.26

STUCK_SPEED_KMH       = 3.0
STUCK_STEPS           = 100
REVERSE_STEPS         = 150

# ── Vehicle constants ──────────────────────────────────────────────────────────
REAR_RADIUS        = 0.3151
FRONT_RADIUS       = 0.3024
FINAL_DRIVE        = 4.5
GEAR_RATIOS        = [0.0, 3.9, 2.9, 2.3, 1.87, 1.68, 1.54]
RPM_SCALE          = math.pi / 3.0
IDLE_PHYS          = 5000.0
LIMITER_PHYS       = 18700.0
LIMITER_REP        = LIMITER_PHYS * RPM_SCALE
ENGINE_BRAKE_COEFF = 0.33
RPM_MAX_PHYS       = 20000.0

_TORQUE_CURVE = [
    (    0, 100), ( 1000, 100), ( 2000, 120), ( 3000, 140),
    ( 4000, 160), ( 5000, 180), ( 6000, 220), ( 7000, 260),
    ( 8000, 300), ( 9000, 340), (10000, 340), (11000, 340),
    (12000, 340), (13000, 345), (14000, 350), (15000, 355),
    (16000, 360), (17000, 360), (18000, 360), (19000, 330),
    (20000, 300),
]

# ── Stage B/B.1 transmission parameters (unchanged) ───────────────────────────
UPSHIFT_TQ_RATIO    = 1.02
DOWNSHIFT_TQ_RATIO  = 1.05
SHIFT_BRAKE_GATE    = 0.05
LIMITER_MARGIN      = 800.0
LIMITER_RELIEF_FRAC = 0.97
SHIFT_DWELL_S       = 0.5
LAT_SPEED_GATE      = 3.0
ANGLE_STABILITY_FACTOR = 0.8
SHIFT_SLIP_GATE     = 2.0
LAUNCH_SPEED_KMH    = 10.0
COUPLING_RATIO      = 1.35
SHIFT_ACCEL_MIN     = 0.15
DIR_HOLD_S          = 1.5

# ── Stage D: predictive braking parameters (NEW) ──────────────────────────────
# SOURCE: Corkscrew distFromStart values derived exclusively from SCR
# telemetry of V3.3.1 official race (SHA ca154ce...) and V3.2.1 races.
# No car/track XML or simulator-internal files are read at runtime.
# Competition-map assumption: see module docstring provenance section.

TRACK_LENGTH      = 3608.45  # m — measured lap length from SCR distFromStart
                              # (final distFromStart at lastLapTime > 0)

# Chicane braking zone — distFromStart coordinates on Corkscrew
PLAN_ZONE_START   = 2470.0   # m — begin applying zone cap
PLAN_ZONE_END     = 2500.0   # m — resume normal target after this point
PLAN_ZONE_SPEED   =   40.0   # km/h — conservative zone speed (initial hypothesis)
PLAN_PREVIEW      =  150.0   # m — begin computing approach cap this far before zone
PLAN_DECEL        =    5.0   # m/s² — assumed available braking deceleration
PLAN_MARGIN       =    5.0   # m — anticipation margin: cap equals zone speed
                              # when exactly PLAN_MARGIN before zone

# Fallback when distFromStart sensor is invalid/non-finite
PLAN_INVALID_CAP  =   30.0   # km/h — same as EMERGENCY_KMH; conservative


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WINDOWS SCR CLIENT — identical to V3.3.1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class WindowsClient(_base.Client):
    def setup_connection(self):
        self.so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.so.settimeout(1)
        angles   = "-45 -19 -12 -7 -4 -2.5 -1.7 -1 -.5 0 .5 1 1.7 2.5 4 7 12 19 45"
        deadline = time.monotonic() + 90
        print(f"[V3.4] Waiting for SCR at {self.host}:{self.port} - select New Race in TORCS.",
              flush=True)
        while time.monotonic() < deadline:
            self.so.sendto(f"{self.sid}(init {angles})".encode(), (self.host, self.port))
            try:
                packet, _ = self.so.recvfrom(_base.data_size)
            except (socket.timeout, ConnectionResetError):
                continue
            if b"***identified***" in packet:
                print(f"[V3.4] Client connected on port {self.port}", flush=True)
                return
        self.so.close()
        self.so = None
        raise TimeoutError(
            "SCR did not answer in 90 s. Ensure scr_server 1 is selected and New Race was clicked."
        )

    def get_servers_input(self):
        deadline = time.monotonic() + 60
        while self.so and time.monotonic() < deadline:
            try:
                packet, _ = self.so.recvfrom(_base.data_size)
            except (socket.timeout, ConnectionResetError):
                continue
            message = packet.decode("utf-8").rstrip("\0")
            if "***identified***" in message:
                continue
            if "***shutdown***" in message or "***restart***" in message:
                self.shutdown()
                return False
            if message:
                self.S.parse_server_str(message + "\0")
                return True
        raise TimeoutError("No telemetry packet for 60 s.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONTROLLER STATE — identical to V3.3.1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_stuck_counter   = 0
_reverse_counter = 0
_prev_fwd        = 200.0
_last_shift_time = -(SHIFT_DWELL_S + 1.0)
_last_shift_dir  = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SENSOR HELPERS — identical to V3.3.1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_LEFT_NEAR  = (4, 5, 6, 7)
_RIGHT_NEAR = (11, 12, 13, 14)
_LEFT_MID   = (2, 3)
_RIGHT_MID  = (15, 16)
_FORWARD    = 9


def _sanitise_scalar(raw, fallback: float) -> tuple:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return fallback, True
    if not math.isfinite(v):
        return fallback, True
    return v, False


def _sanitise_track(raw) -> tuple:
    if not isinstance(raw, (list, tuple)) or len(raw) < 19:
        return [0.0] * 19, True
    sanitised = []
    invalid   = False
    for v in raw[:19]:
        try:
            fv = float(v)
        except (TypeError, ValueError):
            sanitised.append(0.0)
            invalid = True
            continue
        if not math.isfinite(fv) or fv <= 0.0:
            sanitised.append(0.0)
            invalid = True
        else:
            sanitised.append(fv)
    return sanitised, invalid


def _curvature_index(track: list) -> float:
    fwd    = max(track[_FORWARD], 1.0)
    l_near = min(track[i] for i in _LEFT_NEAR)
    r_near = min(track[i] for i in _RIGHT_NEAR)
    l_mid  = min(track[i] for i in _LEFT_MID)
    r_mid  = min(track[i] for i in _RIGHT_MID)
    max_near  = max(l_near, r_near, 1.0)
    near_asym = abs(l_near - r_near) / max_near
    max_mid   = max(l_mid, r_mid, 1.0)
    mid_asym  = abs(l_mid - r_mid) / max_mid
    combined_asym = near_asym * 0.7 + mid_asym * 0.3
    fwd_loss      = max(0.0, 1.0 - fwd / FORWARD_STRAIGHT)
    raw = ASYM_SCALE * combined_asym + FWD_SCALE * fwd_loss
    return min(raw ** (1.0 / CURVATURE_SHARPNESS), 1.0)


def _target_from_curvature(curvature: float) -> float:
    return TARGET_MAX_KMH - (TARGET_MAX_KMH - TARGET_MIN_KMH) * curvature


def _lookahead_target(track: list, curvature: float, prev_fwd: float) -> float:
    fwd           = track[_FORWARD]
    fwd_delta     = fwd - prev_fwd
    predicted_fwd = max(fwd + fwd_delta * 75 * LOOKAHEAD_DECAY_WEIGHT, 10.0)
    predicted_loss  = max(0.0, 1.0 - predicted_fwd / FORWARD_STRAIGHT)
    predicted_curve = min(FWD_SCALE * predicted_loss * 2.0, 1.0)
    predicted_target = TARGET_MAX_KMH - (TARGET_MAX_KMH - TARGET_MIN_KMH) * predicted_curve
    current_target   = _target_from_curvature(curvature)
    return min(current_target, predicted_target)


def _boundary_speed_cap(position: float, angle: float, base_target: float) -> tuple:
    abs_pos = abs(position)
    if abs_pos > BOUNDARY_HARD or abs(angle) > ANGLE_HARD:
        reason = "emergency_pos" if abs_pos > BOUNDARY_HARD else "emergency_angle"
        return min(base_target, EMERGENCY_KMH), reason
    if abs_pos > BOUNDARY_SOFT:
        excess = (abs_pos - BOUNDARY_SOFT) / (BOUNDARY_HARD - BOUNDARY_SOFT)
        cap    = TARGET_MAX_KMH - excess * 20.0
        return min(base_target, cap), "soft_boundary"
    return base_target, ""


def _steering(angle: float, position: float, speed_kmh: float) -> float:
    speed_ms = max(speed_kmh / 3.6, 1.0)
    gain     = STEER_ANGLE_GAIN + STEER_SPEED_DAMP / speed_ms
    return _base.clip(angle * gain - position * STEER_CENTER_GAIN, -1.0, 1.0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TORQUE MODEL — identical to V3.3.1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _to_phys_rpm(reported_rpm: float) -> float:
    return reported_rpm / RPM_SCALE

def _kinematic_phys_rpm(speed_kmh: float, gear: int) -> float:
    if gear < 1 or gear > 6:
        return IDLE_PHYS
    ratio    = GEAR_RATIOS[gear]
    speed_ms = speed_kmh / 3.6
    return speed_ms / REAR_RADIUS * ratio * FINAL_DRIVE * 60.0 / (2.0 * math.pi)

def _curve_torque(phys_rpm: float) -> float:
    curve = _TORQUE_CURVE
    if phys_rpm <= curve[0][0]:
        return curve[0][1]
    if phys_rpm >= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        r0, t0 = curve[i]
        r1, t1 = curve[i + 1]
        if r0 <= phys_rpm <= r1:
            frac = (phys_rpm - r0) / (r1 - r0)
            return t0 + frac * (t1 - t0)
    return curve[-1][1]

def _net_torque(phys_rpm: float, accel_cmd: float) -> float:
    rpm_clamped = max(IDLE_PHYS, min(phys_rpm, RPM_MAX_PHYS))
    K           = ENGINE_BRAKE_COEFF * (rpm_clamped - IDLE_PHYS) / (RPM_MAX_PHYS - IDLE_PHYS)
    Tmax        = _curve_torque(rpm_clamped)
    return Tmax * (accel_cmd * (1.0 + K) - K)

def _wheel_torque(phys_rpm: float, gear: int, accel_cmd: float) -> float:
    if gear < 1 or gear > 6:
        return 0.0
    return _net_torque(phys_rpm, accel_cmd) * GEAR_RATIOS[gear] * FINAL_DRIVE


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TC HELPER — identical to V3.3.1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _tc_signed_linear(
    accel_in: float,
    wsv_field,
    body_speed_ms: float,
    wsv_tc_valid: bool,
) -> tuple:
    """Signed-linear traction control limiter.  Identical to V3.3.1.

    Returns (accel_out, tc_reason, signed_slip_ms).
    tc_reason: "" | "tc_active" | "tc_launch" | "tc_invalid"
    """
    if not wsv_tc_valid:
        return 0.0, "tc_invalid", 0.0
    if body_speed_ms < LAUNCH_SPEED_KMH / 3.6:
        return accel_in, "tc_launch", 0.0
    rear_linear_ms = (wsv_field[2] + wsv_field[3]) * 0.5 * REAR_RADIUS
    signed_slip    = rear_linear_ms - body_speed_ms
    if signed_slip <= TC_LINEAR_ONSET:
        return accel_in, "", signed_slip
    excess    = signed_slip - TC_LINEAR_ONSET
    fraction  = min(excess / TC_LINEAR_RANGE, 1.0)
    accel_out = max(0.0, accel_in * (1.0 - fraction))
    return accel_out, "tc_active", signed_slip


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PREDICTIVE CORNER CAP — Stage D (NEW)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _predictive_corner_cap(raw_dist_from_start) -> tuple:
    """Compute a predictive speed cap based on distFromStart sensor.

    Returns (cap_kmh, planning_reason) where planning_reason is one of:
      ""              — outside preview window, no cap (returns TARGET_MAX_KMH)
      "plan_approach" — in approach braking window, kinematic cap active
      "plan_zone"     — inside zone, zone speed cap active
      "plan_invalid"  — dist sensor invalid or out-of-range, fallback cap

    The returned cap_kmh is ALWAYS <= TARGET_MAX_KMH.
    It must be applied as: safe_target = min(safe_target, cap_kmh)
    after existing emergency caps.  It can never raise a target.

    Computation:
      1. Parse and validate raw_dist_from_start.
      2. Range check: d must be in [0, TRACK_LENGTH).  Out-of-range → invalid.
         No modulo is applied; distFromStart is a within-lap sensor reading.
      3. Compute distance to zone entry: d_to_zone = PLAN_ZONE_START - d
      4. Inside zone (d_to_zone <= 0 and d < PLAN_ZONE_END):
           cap = PLAN_ZONE_SPEED
      5. Post-zone (d >= PLAN_ZONE_END):
           return TARGET_MAX_KMH (no cap)
      6. Within preview (0 < d_to_zone <= PLAN_PREVIEW):
           braking_dist = max(d_to_zone - PLAN_MARGIN, 0.0)
           v_zone_ms    = PLAN_ZONE_SPEED / 3.6
           v_cap_ms     = sqrt(v_zone_ms² + 2 × PLAN_DECEL × braking_dist)
           cap          = v_cap_ms × 3.6  (clamped to TARGET_MAX_KMH)
      7. Beyond preview (d_to_zone > PLAN_PREVIEW):
           cap = TARGET_MAX_KMH (kinematic cap > 100 km/h, no effect)

    Zone end boundary: PLAN_ZONE_END = 2500 is exclusive.
    Cap is active for d in [PLAN_ZONE_START, PLAN_ZONE_END).
    At d == PLAN_ZONE_END the cap lifts (post-zone branch fires).
    """
    # ── Step 1: parse ─────────────────────────────────────────────────────────
    try:
        d = float(raw_dist_from_start)
    except (TypeError, ValueError):
        return PLAN_INVALID_CAP, "plan_invalid"
    if not math.isfinite(d):
        return PLAN_INVALID_CAP, "plan_invalid"

    # ── Step 2: range validation — NO modulo ─────────────────────────────────
    # distFromStart is a within-lap reading.  Values outside [0, TRACK_LENGTH)
    # are sensor faults or pre-grid glitches and must not be mapped to a
    # plausible position via modulo arithmetic.
    if d < 0.0 or d >= TRACK_LENGTH:
        return PLAN_INVALID_CAP, "plan_invalid"

    # ── Step 3: distance to zone entry ────────────────────────────────────────
    d_to_zone = PLAN_ZONE_START - d

    # ── Step 4: inside zone ───────────────────────────────────────────────────
    if d_to_zone <= 0.0 and d < PLAN_ZONE_END:
        return PLAN_ZONE_SPEED, "plan_zone"

    # ── Step 5: post-zone ─────────────────────────────────────────────────────
    if d >= PLAN_ZONE_END:
        return TARGET_MAX_KMH, ""

    # ── Step 6/7: pre-zone approach ───────────────────────────────────────────
    # d_to_zone > 0 here (car has not reached zone start yet)
    if d_to_zone > PLAN_PREVIEW:
        return TARGET_MAX_KMH, ""

    # Kinematic approach cap:
    #   v_cap² = v_zone² + 2 × a × max(d_to_zone − margin, 0)
    braking_dist = max(d_to_zone - PLAN_MARGIN, 0.0)
    v_zone_ms    = PLAN_ZONE_SPEED / 3.6
    v_cap_ms     = math.sqrt(v_zone_ms ** 2 + 2.0 * PLAN_DECEL * braking_dist)
    cap_kmh      = min(v_cap_ms * 3.6, TARGET_MAX_KMH)
    return cap_kmh, "plan_approach"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GEAR SELECTION — identical to V3.3.1
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _select_gear_v321(
    current_gear: int,
    reported_rpm: float,
    speed_kmh: float,
    accel_cmd: float,
    brake_cmd: float,
    wsv_slip: list,
    lat_speed_ms: float,
    position: float,
    angle: float,
    safety_active: bool,
    lap_time: float,
    last_shift_time: float,
    last_shift_dir: int,
    gear_sensors_valid: bool,
) -> tuple:
    """Torque-crossover gear selection with anti-hunting guards.
    Executable behaviour identical to V3.3.1.
    """
    if current_gear <= 0:
        phys_rpm = _to_phys_rpm(reported_rpm)
        return current_gear, "", phys_rpm, phys_rpm, reported_rpm, 0.0, last_shift_dir
    g = max(1, min(6, int(current_gear)))
    phys_rpm = _to_phys_rpm(reported_rpm)
    rear_linear_ms = (wsv_slip[2] + wsv_slip[3]) * 0.5 * REAR_RADIUS
    speed_ms       = speed_kmh / 3.6
    rear_slip_ms   = abs(rear_linear_ms - speed_ms)
    if (phys_rpm >= LIMITER_PHYS * LIMITER_RELIEF_FRAC
            and g < 6 and gear_sensors_valid
            and speed_kmh >= LAUNCH_SPEED_KMH):
        kin_rpm = _kinematic_phys_rpm(speed_kmh, g)
        kin_rpm_engaged = max(kin_rpm, IDLE_PHYS)
        if phys_rpm <= kin_rpm_engaged * COUPLING_RATIO:
            pred_phys = _kinematic_phys_rpm(speed_kmh, g + 1)
            pred_phys = max(pred_phys, IDLE_PHYS)
            if pred_phys < LIMITER_PHYS - LIMITER_MARGIN:
                pred_rep = pred_phys * RPM_SCALE
                return g + 1, "limiter_relief", phys_rpm, pred_phys, pred_rep, rear_slip_ms, +1
            else:
                return g, "limiter_relief_unsafe", phys_rpm, pred_phys, pred_phys * RPM_SCALE, rear_slip_ms, last_shift_dir
    if speed_kmh < LAUNCH_SPEED_KMH:
        return g, "blocked_launch", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    if not gear_sensors_valid:
        return g, "blocked_sensor", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    kin_rpm_cur = max(_kinematic_phys_rpm(speed_kmh, g), IDLE_PHYS)
    if phys_rpm > kin_rpm_cur * COUPLING_RATIO:
        return g, "blocked_coupling", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    if accel_cmd == 0.0 and brake_cmd > SHIFT_BRAKE_GATE:
        return g, "blocked_brake", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    if safety_active:
        return g, "blocked_safety", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    angle_limit = ANGLE_HARD * ANGLE_STABILITY_FACTOR
    if (lat_speed_ms > LAT_SPEED_GATE
            or abs(position) > BOUNDARY_SOFT
            or abs(angle) > angle_limit):
        return g, "blocked_stability", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    if rear_slip_ms > SHIFT_SLIP_GATE:
        return g, "blocked_slip", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    if (lap_time - last_shift_time) < SHIFT_DWELL_S:
        return g, "blocked_dwell", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    if accel_cmd < SHIFT_ACCEL_MIN:
        return g, "blocked_accel", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
    elapsed    = lap_time - last_shift_time
    tq_current = _wheel_torque(phys_rpm, g, accel_cmd)
    if g < 6 and tq_current > 0.0:
        rpm_up = max(_kinematic_phys_rpm(speed_kmh, g + 1), IDLE_PHYS)
        tq_up  = _wheel_torque(rpm_up, g + 1, accel_cmd)
        if tq_up > 0.0 and tq_up > tq_current * UPSHIFT_TQ_RATIO:
            if last_shift_dir == -1 and elapsed < DIR_HOLD_S:
                return g, "blocked_dir_hold", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
            return g + 1, "upshift", phys_rpm, rpm_up, rpm_up * RPM_SCALE, rear_slip_ms, +1
    if g > 1 and tq_current > 0.0:
        rpm_down = max(_kinematic_phys_rpm(speed_kmh, g - 1), IDLE_PHYS)
        if rpm_down >= LIMITER_PHYS - LIMITER_MARGIN:
            return g, "blocked_limiter", phys_rpm, rpm_down, rpm_down * RPM_SCALE, rear_slip_ms, last_shift_dir
        tq_down = _wheel_torque(rpm_down, g - 1, accel_cmd)
        if tq_down > 0.0 and tq_down > tq_current * DOWNSHIFT_TQ_RATIO:
            if last_shift_dir == +1 and elapsed < DIR_HOLD_S:
                return g, "blocked_dir_hold", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir
            return g - 1, "downshift", phys_rpm, rpm_down, rpm_down * RPM_SCALE, rear_slip_ms, -1
    return g, "", phys_rpm, phys_rpm, reported_rpm, rear_slip_ms, last_shift_dir


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN DRIVE FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def drive_v3_4(client) -> dict:
    """Compute and apply one control step.

    Identical to drive_v3_3_1 except step 2b: after the existing safety-cap
    pipeline and before target_spd = min(TARGET_MAX_KMH, safe_target),
    _predictive_corner_cap() is applied as:
        safe_target = min(safe_target, planned_cap)
    This can only reduce safe_target, never raise it.
    """
    global _stuck_counter, _reverse_counter, _prev_fwd, _last_shift_time, _last_shift_dir

    S = client.S.d
    R = client.R.d

    # ── Scalar sensor sanitisation ────────────────────────────────────────────
    scalar_invalid = False
    speed,    _inv = _sanitise_scalar(S.get("speedX"), 0.0);    scalar_invalid |= _inv
    angle,    _inv = _sanitise_scalar(S.get("angle"), 0.0);     scalar_invalid |= _inv
    position, _inv = _sanitise_scalar(S.get("trackPos"), 0.0);  scalar_invalid |= _inv
    rpm,      _inv = _sanitise_scalar(S.get("rpm"), 5236.0);    scalar_invalid |= _inv

    raw_gear = S.get("gear")
    try:
        gear_f = float(raw_gear)
        if not math.isfinite(gear_f):
            raise ValueError
        gear = gear_f
    except (TypeError, ValueError):
        gear = 1.0
        scalar_invalid = True

    raw_speedY = S.get("speedY", _MISSING)
    raw_speedY_invalid = False
    if raw_speedY is _MISSING or raw_speedY is None:
        raw_speedY_invalid = True
        speedY = 0.0
    else:
        try:
            speedY = float(raw_speedY)
            if not math.isfinite(speedY):
                raw_speedY_invalid = True
                speedY = 0.0
        except (TypeError, ValueError):
            raw_speedY_invalid = True
            speedY = 0.0
    lat_speed_ms = abs(speedY / 3.6)

    lap_time = S.get("curLapTime", 0.0)
    try:
        lap_time = float(lap_time)
        if not math.isfinite(lap_time):
            lap_time = 0.0
    except (TypeError, ValueError):
        lap_time = 0.0

    raw_track_field    = S.get("track")
    raw_wsv_field      = S.get("wheelSpinVel")
    raw_dist_from_start = S.get("distFromStart")   # NEW: read for planning

    track, sensor_invalid = _sanitise_track(raw_track_field)

    # ── WSV parsing (V3.3.1 logic: negative gated on launch speed) ───────────
    wsv_tc_valid       = True
    gear_sensors_valid = True
    wsv_tc   = []
    wsv_slip = []
    if isinstance(raw_wsv_field, (list, tuple)) and len(raw_wsv_field) >= 4:
        for i, v in enumerate(raw_wsv_field[:4]):
            try:
                fv = float(v)
            except (TypeError, ValueError):
                fv = 0.0
                if i >= 2:
                    gear_sensors_valid = False
                    wsv_tc_valid       = False
            if not math.isfinite(fv):
                fv = 0.0
                if i >= 2:
                    gear_sensors_valid = False
                    wsv_tc_valid       = False
            wsv_tc.append(fv)
            if i >= 2 and fv < 0.0:
                gear_sensors_valid = False
                if speed >= LAUNCH_SPEED_KMH:
                    wsv_tc_valid = False
            wsv_slip.append(max(fv, 0.0) if i >= 2 else fv)
    else:
        wsv_tc             = [0.0, 0.0, 0.0, 0.0]
        wsv_slip           = [0.0, 0.0, 0.0, 0.0]
        gear_sensors_valid = False
        wsv_tc_valid       = False
    if raw_speedY_invalid:
        gear_sensors_valid = False

    body_speed_ms = speed / 3.6
    if scalar_invalid:
        wsv_tc_valid = False

    # ── Dwell reset on lap boundary ───────────────────────────────────────────
    if lap_time < _last_shift_time:
        _last_shift_time = lap_time - SHIFT_DWELL_S - 1.0
        _last_shift_dir  = 0

    # ── 1. Stuck / Recovery ───────────────────────────────────────────────────
    if speed < STUCK_SPEED_KMH:
        _stuck_counter += 1
    else:
        _stuck_counter = 0
    if _stuck_counter >= STUCK_STEPS and _reverse_counter == 0:
        _reverse_counter = REVERSE_STEPS
        _stuck_counter   = 0
        print(f"[V3.4] STUCK RECOVERY at {S.get('distFromStart', 0):.0f} m", flush=True)
    if _reverse_counter > 0:
        _last_shift_dir = 0
        l_near    = min(track[i] for i in _LEFT_NEAR)
        r_near    = min(track[i] for i in _RIGHT_NEAR)
        wall_bias = (l_near - r_near) * 0.04
        R["gear"]  = -1
        R["accel"] = 0.0 if (sensor_invalid or scalar_invalid) else 0.40
        R["brake"] = 0.0
        R["steer"] = _base.clip(wall_bias, -0.5, 0.5)
        _reverse_counter -= 1
        _prev_fwd = track[_FORWARD]
        return {
            "target_speed": 0.0, "curvature": 0.0, "lookahead_target": 0.0,
            "mode": "RECOVERY", "safety_reason": "recovery",
            "sensor_invalid": sensor_invalid, "scalar_invalid": scalar_invalid,
            "cmd_gear": -1, "speedY": speedY,
            "raw_track": list(raw_track_field) if isinstance(raw_track_field, (list, tuple)) else [],
            "raw_wsv":   list(raw_wsv_field)   if isinstance(raw_wsv_field,   (list, tuple)) else [],
            "shift_reason": "recovery",
            "phys_rpm": round(_to_phys_rpm(rpm), 1),
            "pred_phys_rpm_post": round(_to_phys_rpm(rpm), 1),
            "pred_rep_rpm_post": round(rpm, 1),
            "rear_slip_ms": 0.0, "lat_speed_ms": round(lat_speed_ms, 4),
            "last_shift_dir": _last_shift_dir,
            "tc_reason": "recovery", "signed_slip_ms": 0.0,
            "planned_speed_cap": TARGET_MAX_KMH, "planning_reason": "recovery",
        }

    if int(gear) <= 0:
        gear = 1.0

    # ── 2. Curvature & speed target ───────────────────────────────────────────
    curvature   = _curvature_index(track)
    base_target = _target_from_curvature(curvature)
    look_target = _lookahead_target(track, curvature, _prev_fwd)

    floored_target             = max(TARGET_MIN_KMH, look_target)
    safe_target, safety_reason = _boundary_speed_cap(position, angle, floored_target)

    if sensor_invalid:
        safe_target = min(safe_target, EMERGENCY_KMH)
        if not safety_reason:
            safety_reason = "sensor_invalid"
    if scalar_invalid:
        safe_target = min(safe_target, EMERGENCY_KMH)
        if not safety_reason:
            safety_reason = "scalar_invalid"

    # ── 2b. Predictive corner cap (NEW) ───────────────────────────────────────
    # Applied AFTER emergency/sensor caps, BEFORE final min-clamp.
    # Can only reduce safe_target; never raises an already-lowered target.
    planned_cap, planning_reason = _predictive_corner_cap(raw_dist_from_start)
    safe_target = min(safe_target, planned_cap)

    target_spd = min(TARGET_MAX_KMH, safe_target)
    _prev_fwd  = track[_FORWARD]

    # ── 3. Steering ───────────────────────────────────────────────────────────
    R["steer"] = _steering(angle, position, speed)

    # ── 4. Throttle ramp ──────────────────────────────────────────────────────
    raw_accel  = (target_spd - speed) / ACCEL_RAMP_DIV
    R["accel"] = _base.clip(raw_accel, 0.0, ACCEL_MAX)
    if sensor_invalid or scalar_invalid:
        R["accel"] = 0.0

    # ── 5. Braking ────────────────────────────────────────────────────────────
    raw_brake  = (speed - target_spd) / BRAKE_RAMP_DIV
    R["brake"] = _base.clip(raw_brake, 0.0, BRAKE_MAX)
    if R["brake"] > BRAKE_ACCEL_THRESHOLD:
        R["accel"] = 0.0

    # ── 6. Traction control ───────────────────────────────────────────────────
    R["accel"], tc_reason, signed_slip_ms = _tc_signed_linear(
        accel_in=R["accel"], wsv_field=wsv_tc,
        body_speed_ms=body_speed_ms, wsv_tc_valid=wsv_tc_valid,
    )

    # ── 7. Gear selection ─────────────────────────────────────────────────────
    safety_active = bool(safety_reason)
    (cmd_gear, shift_reason, phys_rpm, pred_phys, pred_rep,
     rear_slip_ms, new_shift_dir) = _select_gear_v321(
        current_gear=int(gear), reported_rpm=rpm, speed_kmh=speed,
        accel_cmd=R["accel"], brake_cmd=R["brake"], wsv_slip=wsv_slip,
        lat_speed_ms=lat_speed_ms, position=position, angle=angle,
        safety_active=safety_active, lap_time=lap_time,
        last_shift_time=_last_shift_time, last_shift_dir=_last_shift_dir,
        gear_sensors_valid=gear_sensors_valid,
    )
    if cmd_gear != int(gear) and int(gear) > 0:
        _last_shift_time = lap_time
        _last_shift_dir  = new_shift_dir
    R["gear"] = cmd_gear

    return {
        "target_speed":        round(target_spd,  2),
        "curvature":           round(curvature,    4),
        "lookahead_target":    round(look_target,  2),
        "mode":                "DRIVE",
        "safety_reason":       safety_reason,
        "sensor_invalid":      sensor_invalid,
        "scalar_invalid":      scalar_invalid,
        "cmd_gear":            cmd_gear,
        "speedY":              speedY,
        "raw_track": list(raw_track_field) if isinstance(raw_track_field, (list, tuple)) else [],
        "raw_wsv":   list(raw_wsv_field)   if isinstance(raw_wsv_field,   (list, tuple)) else [],
        "shift_reason":        shift_reason,
        "phys_rpm":            round(phys_rpm, 1),
        "pred_phys_rpm_post":  round(pred_phys, 1),
        "pred_rep_rpm_post":   round(pred_rep,  1),
        "rear_slip_ms":        round(rear_slip_ms, 4),
        "lat_speed_ms":        round(lat_speed_ms, 4),
        "last_shift_dir":      _last_shift_dir,
        "tc_reason":           tc_reason,
        "signed_slip_ms":      round(signed_slip_ms, 6),
        "planned_speed_cap":   round(planned_cap, 2),
        "planning_reason":     planning_reason,
    }


# Alias for autostart worker drive-function discovery
drive_v3 = drive_v3_4


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RACE RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> int:
    global _stuck_counter, _reverse_counter, _prev_fwd, _last_shift_time, _last_shift_dir
    _stuck_counter   = 0
    _reverse_counter = 0
    _prev_fwd        = 200.0
    _last_shift_time = -(SHIFT_DWELL_S + 1.0)
    _last_shift_dir  = 0

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    prefix    = OUTPUT / f"v3_4-{timestamp}"

    _ray_cols = [f"track_ray_{i:02d}" for i in range(19)]
    _wsv_cols = [f"wsv_{i}" for i in range(4)]

    columns = [
        "step", "wall_seconds",
        "curLapTime", "lastLapTime", "damage",
        "distFromStart", "distRaced",
        "speedX", "speedY", "gear", "rpm",
        "trackPos", "angle",
        "target_speed", "lookahead_target", "curvature", "mode",
        "safety_reason", "sensor_invalid", "scalar_invalid", "cmd_gear",
        "accel", "brake", "steer",
        "shift_reason", "phys_rpm", "pred_phys_rpm_post", "pred_rep_rpm_post",
        "rear_slip_ms", "lat_speed_ms", "last_shift_dir",
        "tc_reason", "signed_slip_ms",
        "planned_speed_cap", "planning_reason",
    ] + _ray_cols + _wsv_cols

    summary = {
        "controller":        "controller_v3_4.py",
        "base_sha256":       "ca154ce3035109b89b6a3e073e26e9e7e263bc6cc01a182fd1546e14ce210e5a",
        "original_sha256":   hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
        "target_max_kmh":    TARGET_MAX_KMH,
        "track":             "corkscrew",
        "lap_completed":     False,
        "max_speed_kmh":     0.0,
        "avg_speed_kmh":     0.0,
        "status":            "starting",
        "stage_d_changes":   [
            "predictive_braking_chicane_2470_2500m",
            "zone_speed_40kmh",
            "plan_decel_5ms2",
            "plan_margin_5m",
            "plan_preview_150m",
        ],
    }

    client        = None
    started       = time.monotonic()
    last          = {}
    speed_samples = []

    print(
        f"[V3.4] controller_v3_4.py  |  target_max={TARGET_MAX_KMH} km/h  "
        f"|  zone={PLAN_ZONE_START:.0f}-{PLAN_ZONE_END:.0f}m@{PLAN_ZONE_SPEED}kmh  "
        f"|  decel={PLAN_DECEL}m/s²  margin={PLAN_MARGIN}m  "
        f"|  output: {prefix.name}.csv",
        flush=True,
    )

    try:
        client = WindowsClient(H="127.0.0.1", p=3001)
        with prefix.with_suffix(".csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for step in range(client.maxSteps):
                if not client.get_servers_input():
                    summary["status"] = "server_shutdown"
                    break

                diag = drive_v3_4(client)
                last = dict(client.S.d)
                raw_track_diag = diag.get("raw_track", [])
                raw_wsv_diag   = diag.get("raw_wsv",   [])

                row = {
                    "step":               step,
                    "wall_seconds":       round(time.monotonic() - started, 3),
                    "curLapTime":         last.get("curLapTime",    ""),
                    "lastLapTime":        last.get("lastLapTime",   ""),
                    "damage":             last.get("damage",        ""),
                    "distFromStart":      last.get("distFromStart", ""),
                    "distRaced":          last.get("distRaced",     ""),
                    "speedX":             last.get("speedX",        ""),
                    "speedY":             diag.get("speedY",         ""),
                    "gear":               last.get("gear",           ""),
                    "rpm":                last.get("rpm",            ""),
                    "trackPos":           last.get("trackPos",       ""),
                    "angle":              last.get("angle",          ""),
                    "target_speed":       diag["target_speed"],
                    "lookahead_target":   diag["lookahead_target"],
                    "curvature":          diag["curvature"],
                    "mode":               diag["mode"],
                    "safety_reason":      diag.get("safety_reason",  ""),
                    "sensor_invalid":     int(diag.get("sensor_invalid", False)),
                    "scalar_invalid":     int(diag.get("scalar_invalid", False)),
                    "cmd_gear":           diag.get("cmd_gear",        ""),
                    "accel":              client.R.d.get("accel",     ""),
                    "brake":              client.R.d.get("brake",     ""),
                    "steer":              client.R.d.get("steer",     ""),
                    "shift_reason":       diag.get("shift_reason",    ""),
                    "phys_rpm":           diag.get("phys_rpm",        ""),
                    "pred_phys_rpm_post": diag.get("pred_phys_rpm_post", ""),
                    "pred_rep_rpm_post":  diag.get("pred_rep_rpm_post",  ""),
                    "rear_slip_ms":       diag.get("rear_slip_ms",    ""),
                    "lat_speed_ms":       diag.get("lat_speed_ms",    ""),
                    "last_shift_dir":     diag.get("last_shift_dir",  ""),
                    "tc_reason":          diag.get("tc_reason",       ""),
                    "signed_slip_ms":     diag.get("signed_slip_ms",  ""),
                    "planned_speed_cap":  diag.get("planned_speed_cap", ""),
                    "planning_reason":    diag.get("planning_reason",  ""),
                }
                for i, col in enumerate(_ray_cols):
                    row[col] = raw_track_diag[i] if i < len(raw_track_diag) else ""
                for i, col in enumerate(_wsv_cols):
                    row[col] = raw_wsv_diag[i] if i < len(raw_wsv_diag) else ""
                writer.writerow(row)

                spd = last.get("speedX", 0)
                if isinstance(spd, (int, float)):
                    summary["max_speed_kmh"] = max(summary["max_speed_kmh"], spd)
                    speed_samples.append(spd)

                client.respond_to_server()

                if step % 50 == 0:
                    f.flush()
                    print(
                        f"[V3.4] t={last.get('curLapTime', 0):.1f}s  "
                        f"dist={last.get('distFromStart', 0):.0f}m  "
                        f"spd={spd:.1f}km/h  tgt={diag['target_speed']}  "
                        f"plan={diag.get('planning_reason', '')}@{diag.get('planned_speed_cap', 0):.0f}  "
                        f"g={last.get('gear', '?')}->{diag.get('cmd_gear', '?')}  "
                        f"tc={diag.get('tc_reason', '')}  "
                        f"sf={diag.get('safety_reason', '')}  "
                        f"dmg={last.get('damage', 0)}",
                        flush=True,
                    )

                if last.get("lastLapTime", 0) > 0:
                    summary["lap_completed"]    = True
                    summary["lap_time_seconds"] = last["lastLapTime"]
                    print(f"[V3.4] LAP COMPLETED: {last['lastLapTime']:.2f} s", flush=True)

                if time.monotonic() - started > 900:
                    summary["status"] = "wall_time_limit"
                    break
            else:
                summary["status"] = "step_limit"

    except (OSError, TimeoutError) as exc:
        summary["status"] = "connection_error"
        summary["error"]  = str(exc)
        print(f"[V3.4] ERROR: {exc}", file=sys.stderr)

    finally:
        if client and client.so:
            client.shutdown()
        summary["wall_seconds"]    = round(time.monotonic() - started, 3)
        summary["final_telemetry"] = last
        if speed_samples:
            summary["avg_speed_kmh"] = round(sum(speed_samples) / len(speed_samples), 2)
        out_json = prefix.with_suffix(".json")
        out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2), flush=True)

    return 2 if summary["status"] == "connection_error" else 0


if __name__ == "__main__":
    sys.exit(main())
