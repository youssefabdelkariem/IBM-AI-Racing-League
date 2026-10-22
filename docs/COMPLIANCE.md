# Compliance notes

This is the author's reading of the league materials. **No written organiser ruling has been received.** Nothing here is an approval, and the open questions below are still unanswered.

## Sources
- IBM AI Racing League framework ("The Rule of 8").
- Task slides "TORCS and Bob - Corkscrew".
- TORCS container setup guide and customising guide.
- Orientation session.

## Rule text (quoted)
| # | Source | Text |
|---|---|---|
| R1 | Framework | "All team members must complete at least one IBM SkillsBuild credential – IBM Granite credential is mandatory for team members" |
| R2 | Framework | "All laps must begin from a standing start and use the Corkscrew Track" |
| R3 | Framework | "Do not change internal TORCS car model dynamics or livery for your official team submission. You may only change your AI Python code" |
| R4 | Framework | "Add your team name and university name to your videos – so we know who you are" |
| R6 | Framework | "Lap times will be used as a qualifier – team videos to be used to select the winner" |
| S | Framework | "Team submit their race artifacts, inc' race video, team video & Github repo" |
| T | Task slides | "Track = Corkscrew Lap = 1 from standing start"; "Beat the original time with zero car damage" |
| G | Setup guide | `torcs_jm_par.py` "Main starter file — edit this for the competition"; `snakeoil3_gym.py` "Core UDP client — do not edit" |

## Status of this release
| Item | Finding | Status |
|---|---|---|
| Standing start, Corkscrew, 1 lap, zero damage | Initial speed 0; Corkscrew Quick Race; 1 lap; damage 0 in every validation run | Met |
| Car dynamics and livery unchanged | Car XML, category, physics module, SCR server, livery and track are hash-identical to the stock files before and after every race (`evidence/release_p1_65968/`) | Met |
| Only Python code changed | Only the controller's Python code and its own data files (settings, precomputed plan) were changed | Met, by the wording of R3 |
| `snakeoil3_gym.py` unedited | Byte-identical to the starter file (SHA-256 in `controller/SHA256SUMS.txt`) | Met |
| Reading the stock track XML at start-up | Not addressed by any rule. The file is opened read-only and never modified or shipped. | **Not confirmed (Q1)** |
| Precomputed racing line and speed plan | Not addressed by any rule. The plan is part of the Python package, derived offline from the stock track geometry and closed-loop simulator runs. | **Not confirmed (Q1)** |
| Clutch control during acceleration | The clutch is a standard SCR command and no rule restricts it. Its effect relies on TORCS's clutch model, which passes full torque at about one-third engagement. No car file is changed. | Disclosed; **optional question (Q2)** |
| Entry script | The package uses its own entry script (`run_controller.py`) with the unmodified `snakeoil3_gym.py`, not `torcs_jm_par.py` | **Not confirmed (Q3)** |
| Deadline and submission form | `ibm.biz/TORCSForm` per the framework; the exact extended deadline is not confirmed in writing | **Not confirmed (Q4)** |
| Validation environment | All validation used the native Windows TORCS build supplied with the course download, not the Linux container | **Not confirmed (Q5)** |
| AI tools | The rules expect IBM Granite (R1) and IBM Bob (T). No rule forbids other tools. See `AI_TOOL_DISCLOSURE.md`. | Disclosed |
| Videos | Team and university names on the videos (R4); a team video (R6) | Outside this repository |

No rule found prohibits a feature this controller needs. The open points are ambiguities, not prohibitions.

## Questions for the organisers (unanswered)
1. **Track data and precomputed plans.** The controller reads the stock, unmodified Corkscrew track file at start-up to compute the road geometry. It also uses a racing line and speed plan precomputed offline for Corkscrew, shipped as data files with the code. During the race it uses only the normal SCR sensors and commands. Is this permitted for the official qualifying lap?
2. **Clutch command.** The controller uses the standard SCR clutch command during acceleration (partly open clutch), not only at the start. No car or physics file is changed. Is this acceptable?
3. **Submission format.** The controller runs through its own entry script (`run_controller.py`) with the unmodified `snakeoil3_gym.py`, not through `torcs_jm_par.py`. Is a separate entry script acceptable?
4. **Deadline.** What is the exact submission deadline (date, time and time zone) after the extension, and is `ibm.biz/TORCSForm` still the route?
5. **Environment.** The qualifying lap was produced with the supplied Windows TORCS build, not the container. Is that acceptable for the qualifying time?
