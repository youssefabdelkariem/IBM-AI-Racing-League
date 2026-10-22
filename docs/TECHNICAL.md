# Technical documentation - release P1 (65.968 s)

**Entry:** Python controller for the TORCS SCR interface; car `car1-ow1`, Corkscrew, 1 lap, standing start.

**Result:** 65.968 s, damage 0, 0 server timeouts. The same lap was reproduced in every validation run (local, native Windows TORCS; not an official league time). For comparison, the starter example client drove clean laps of about 3:05-3:27.

## 1. What is precomputed and what is decided live
| Precomputed or read at start-up, before the car moves | Decided live, every 20 ms control step |
|---|---|
| Road geometry from the **stock, unmodified** Corkscrew track file: centre-line curvature, heading, grade, banking | Steering angle |
| Racing line n(s): lateral offset from the centre line along the lap (`plan_cand.npz`, `line_4.4.npz`) | Throttle and brake pedals |
| Speed plan v(s) along that line (`plan_cand.npz`) | Gear and clutch |
| Controller parameters (`settings.json`) | All corrections: path error, heading error, yaw-rate feedback, sideslip, wheel slip, edge and grip limits |

During the race the controller uses only the standard SCR sensors: `distFromStart`, `speedX/Y`, `angle`, `trackPos`, `wheelSpinVel`, `rpm`, `gear` and `curLapTime`. It sends only the standard SCR commands: `steer`, `accel`, `brake`, `gear` and `clutch`.

It does not replay recorded actions. The precomputed line and speed plan are references that the feedback controllers track and correct in real time.

### Track file lookup (`c1_plan._find_track_xml`, read-only)
The first match wins:
1. `TORCS_TRACK_XML` (the file itself);
2. `TORCS_DIR` (the install folder) + `tracks/road/corkscrew/corkscrew.xml`;
3. an install found by walking up from `controller/`;
4. the usual Linux install paths;
5. `controller/data/corkscrew.xml`.

No path is hard-coded to a particular machine. The track file is never modified or redistributed.

## 2. Racing line
1. A **minimum-curvature line** within ±4.4 m of the centre line (road half-width 6 m). It is computed by Levenberg-Marquardt optimisation of the squared path curvature (`c1_plan.optimise_line`).
2. In two windows (the 330-680 m complex and the hairpin), the line and its curvature are rebuilt on the **exact** track geometry, integrated analytically per track segment. A model-based minimum-time speed plan is used there.
3. Small **local offsets** to the line, typically 0.1-1.0 m, were found by simulator-in-the-loop optimisation in seven windows:
   - 446 m, 770 m, 1,042 m, 1,528 m, 2,700 m;
   - the hairpin;
   - the Corkscrew, 2,301-2,493 m (added in P1).

   In every window the curvature is recomputed consistently from the offset line.

## 3. Steering control (lateral)
Every step the controller computes the car's lateral error and heading error relative to the planned line. Heading is based on the car's direction of travel, so sideslip is accounted for.

The steering command combines:
- **curvature feed-forward:** the planned curvature a short time ahead, with 0.28 s look-ahead (0.07 s in the exact-geometry windows, matching the measured steering response delay);
- **feedback** on lateral and heading error (pole placement on the path-error dynamics);
- a **PI loop on measured path curvature**, from the yaw rate;
- an understeer compensation map.

Safety layers:
- **counter-steer** proportional to sideslip;
- **spin recovery**, which blends the wheels towards the velocity direction above 8.6° of sideslip;
- a steering lock cap;
- a steering rate limit.

## 4. Speed control (longitudinal)
- **Target speed:** the plan speed a short look-ahead ahead, reduced live when needed:
  - a **live grip limiter** lowers the target when the demanded curvature exceeds the tyre-grip estimate at the current speed;
  - **path-error and track-edge guards** slow the car when it is far off its line or near the edge.
- A **speed law** converts plan acceleration and speed error into a throttle or brake command. It includes an engine-braking allowance and drag and grade compensation, and rate-limits both pedals.
- **End of lap:** near the finish line the speed look-ahead is clamped to the last plan sample. Interpolating past it would wrap to the first sample, which holds the standing-start speed cap. That fault made the car brake for the line until it was fixed (66.284 → 66.262 s).
- **Standing start:** full throttle until the line, a launch clutch setting, and a higher wheel-slip allowance during the launch phase.

## 5. Traction control (TC)
Rear over-speed (driven-wheel speed minus car speed) is compared with a threshold:
- 5.2987 m/s on straights (`tc_on`);
- 3.1124 m/s at full cornering load (`tc_corner`);
- scaled up with speed above 24.903 m/s (`tc_vs`).

Above the threshold the throttle is reduced proportionally over a 4.8367 m/s band (`tc_range`).

## 6. ABS
If front slip ratio exceeds 0.05 (`abs_on`) while braking above 8 m/s, the brake pedal is reduced proportionally, never below 30 %.

## 7. Gears and clutch
- **Gears:** the lowest gear that keeps the speed-derived rpm below the limit, with up/down thresholds, a minimum time between shifts, and 2nd as the lowest gear when moving.
- **Clutch:** besides the launch, the clutch is partly opened while accelerating at low driven-axle rpm and for 3 steps after each shift. This uses the standard SCR clutch command and TORCS's clutch model, in which full torque is passed at about one-third engagement while drivetrain inertia blends linearly. No car or physics file is changed. This behaviour is disclosed in [`COMPLIANCE.md`](COMPLIANCE.md).

## 8. Robustness of the implementation
- **Garbage collection:** Python's collector is frozen and disabled for the race (`submission_driver.py`). A collector pause delays the reply to the server. The server then reuses the previous command ("Timeout for client answer"), which changes the lap by about 0.4 s.
- **Memory:** the controller allocates only a few short-lived objects per step (about 3,300 steps per lap), so memory growth without collection is negligible.
- **Track file:** located automatically and opened read-only.

## 9. Optimisation methodology
TORCS is **deterministic**: identical settings give bit-identical laps when no server timeout occurs. One full lap is therefore an exact evaluation, taking about 7 s of wall time in results-only mode.

- **Simulator-in-the-loop search.** Every candidate is a real TORCS lap, ranked by the official lap time. Methods: CMA-ES, one-at-a-time screening, and structured local refinement.
- **Hard validity constraints on every candidate:**
  - complete lap, zero damage, zero server timeouts, car on track;
  - at most 0.73 of the half-width in the 446 m complex;
  - kerb guards at 1,931 m: entry ≤ 272.5 km/h, top speed ≤ 278.0 km/h, both below the measured damage onset;
  - a sideslip cap;
  - per-corner edge-clearance limits.
- **Independent validation.** Every accepted change was rebuilt from its saved files. It was raced repeatedly through the unmodified entry point, interleaved with the previous best, and also run in graphics mode while screen recording.

## Performance history
All entries use the stock car. "Lap" is the validated local lap time.

| Stage | Lap (s) | What changed |
|---|---|---|
| Starter example client | ~185-207 | Organiser starter code |
| Exact-geometry windows, model-based speed plans | 66.986 → 66.906 | - |
| Closed-loop line/speed optimisation in corner windows (1,528 m, 770 m, 1,042 m, 2,700 m, 330-680 m complex) | 66.906 → 66.356 | - |
| Launch optimisation (clutch, traction allowance) | 66.284 | Previous release |
| Finish-line fix | 66.262 | Look-ahead clamp at the end of the lap (section 4) |
| Traction control and ABS tuning | 66.020 | Looser TC and earlier ABS release: about +0.55 s at full throttle and -0.39 s braking per lap |
| Corkscrew line | **65.968** | **Release P1.** Straighter line through the left-right direction change: sideslip 14.4° → 9.4°, minimum speed +4.3 km/h |

A study of the 770 m corner after P1 found no reliable further gain and was not adopted.

### Parameters changed from the previous release (66.284 s)
These are the only `settings.json` differences; `controller_c3.py` differs only by the end-of-lap clamp in section 4.

| Parameter | 66.284 s release | P1 |
|---|---|---|
| `tc_on` | 4.827 | 5.2987 |
| `tc_vs` | 30.5 | 24.903 |
| `tc_corner` | 1.5 (code default) | 3.1124 |
| `tc_range` | 3.0 (code default) | 4.8367 |
| `abs_on` | 0.12 (code default) | 0.05 |
| `S_live` | 1.1187 | 1.18966 |
| `k_filter` | 0.395 | 0.15 |
| `c3_file` | `plan_y2_4.npz` | `plan_cand.npz` (adds the Corkscrew line offsets) |

## 10. Final measured performance (logged run of the release package)
- **Lap:** 65.968 s; damage 0; 0 server timeouts.
- **Sideslip:** peak 13.6°.
- **Track position:** maximum 0.967 of the half-width (on track).
- **446 complex:** 0.721 of the half-width (limit 0.73).
- **1,931 m kerb:** entry speed 271.7 km/h (guard 272.5); top speed 276.9 km/h (guard 278.0).

The lap was reproduced in results-only mode, in graphics mode, and while recording with OBS.
