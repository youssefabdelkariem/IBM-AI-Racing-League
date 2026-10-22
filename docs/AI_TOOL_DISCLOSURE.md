# AI tool disclosure

This controller was developed with substantial help from AI coding tools. This statement is based on the project's own development records: the project history, the development state notes and the reports of each optimisation phase.

| Tool | Provider | What it did |
|---|---|---|
| **IBM Bob** | IBM | Early controller versions V2-V5: first speed controllers (80 → 100 km/h ceilings), safety and recovery logic, wheel-slip traction control, gear anti-hunting, predictive braking at the Corkscrew. Those versions were later replaced; the final controller does not import that code. |
| **OpenAI Codex** | OpenAI | Audit of the starter controller and the track geometry; independent stock-car controllers (best 80.726 s); restoration and hash verification of the stock car; review of a public competitor's code and a reference-only benchmark run. |
| **Claude Code** (Claude models) | Anthropic | The controller line used in this entry: exact-geometry reference, steering and speed laws, simulator-in-the-loop CMA-ES corner optimisation, launch optimisation, server-timeout diagnosis and fix, and the portable 66.284 s package. For release P1 it also did the performance audit, finish-line fix, traction control and ABS optimisation, Corkscrew line optimisation, the 770 m corner study, final packaging, validation, the lap recording procedure and this documentation. |
| **IBM Granite** | IBM | Not used to develop, tune or validate this controller. No project record documents such use. |

No other AI tools are documented in the project records.

## Human role
The author:
- set the objectives and constraints of every phase, for example the 0.73 track-position limit in the 446 m complex, no car or physics changes, and no publishing without approval;
- approved each phase and its results;
- decides what is submitted.

## Third-party reference
A public competitor driver, [AdrianoNTorres/IBM-AI-RACE-CHALLENGE](https://github.com/AdrianoNTorres/IBM-AI-RACE-CHALLENGE), was run unmodified and locally as a performance benchmark. Its telemetry was used for diagnosis. **No code, tables or parameters were copied into this controller.** An earlier experimental controller fitted to that driver's behaviour was never part of the entry.

## Simulator behaviour
The clutch strategy relies on TORCS's clutch model, which passes full torque at about one-third engagement (see [`COMPLIANCE.md`](COMPLIANCE.md)). No car, physics or track file was modified.
