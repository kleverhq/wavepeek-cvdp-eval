# Architecture

## Purpose

This repository runs controlled CVDP comparisons between a clean Pi baseline and the same agent environment equipped with WavePeek. Harbor remains the sole orchestrator; repository code prepares reproducible inputs and validates evidence rather than implementing another scheduler.

## Execution flow

1. `scripts/lab.py check` verifies the frozen task cohort, source pins, model profiles, runtime policy, and lock-file hashes.
2. `scripts/lab.py resolve_matrix` expands the requested tasks, models, arms, WavePeek revisions, and attempts into a Harbor job definition.
3. CVDP rows are materialized as Harbor tasks. The visible workspace is separated from the hidden verifier, and solution artifacts are rejected.
4. The exact generated task dataset is copied to the new experiment's `artifacts/inputs/tasks/` directory before execution.
5. Harbor expands and executes the matrix with `harbor_adapter:ReproduciblePi`. Harbor owns concurrency, isolation, timeouts, attempts, verification, and raw trial storage.
6. `harbor_adapter.py` stages only the selected provider credential and starts `harbor/pi_runner.py` inside the task container.
7. The runner creates an isolated Pi home, exposes only the pinned pi-subagents extension and `general-purpose` child type, and retains parent and child sessions.
8. Harbor mounts the hidden CVDP tests after agent execution. Benchmark reward and infrastructure status remain separate.
9. `scripts/lab.py` normalizes trajectories, usage, patches, verifier output, and WavePeek calls, then seals the artifact tree with `run-checksums.json`.

## Arms

Both arms derive from the same `common` stage in `agent/Dockerfile`.

The baseline contains the simulator, Pi, pi-subagents, and the common runner. Tests reject any WavePeek binary, path, skill, documentation, instruction, or environment marker in this arm.

The treatment adds a WavePeek build from one resolved Git commit. `agent/wavepeek-wrapper.py` transparently invokes the real binary, preserves its output and exit status, and records every call. A treatment trial is compliant only after a successful supported query against an explicitly supplied waveform path.

## Component boundaries

- **Harbor** orchestrates tasks and trials. Its pinned checkout is cached at `.cache/harbor/source`.
- **CVDP** supplies prompts, visible context, heavy repositories, and hidden verifiers.
- **Pi** is the parent coding agent runtime.
- **pi-subagents** supplies delegation; this lab exposes only `general-purpose` with one level of depth.
- **WavePeek** is the treatment under evaluation, not the orchestrator or verifier.
- **`scripts/lab.py`** is the operator-facing integration layer and archive normalizer.

## Sources of truth

| Concern | Source of truth |
|---|---|
| Commands | `Justfile` |
| Matrix resolution, task materialization, archive contract | `scripts/lab.py` |
| Runtime defaults and fixed policy | `config/experiment.json` |
| Frozen experiment identity | `experiment.lock.json` |
| CVDP source and bundle pins | `selection/sources.lock.json` |
| Frozen task cohort | `selection/selected.jsonl` |
| Model profiles | `config/models/*.json` |
| Pi catalog and subagent settings | `config/pi/` |
| Image composition | `agent/Dockerfile`, `scripts/build_images.py` |
| Pi isolation and evidence | `harbor/pi_runner.py`, `harbor_adapter.py` |
| WavePeek invocation audit | `agent/wavepeek-wrapper.py` |
| Executable invariants | `tests/` |
| Experiment index | `experiments/JOURNAL.jsonl` |

Files under `experiments/` are generated evidence, not runtime configuration.

## Repository layout

- `agent/` — baseline/treatment image and WavePeek/pi-subagents integration assets.
- `config/` — experiment defaults, exact model profiles, and Pi runtime data.
- `harbor/` and `harbor_adapter.py` — Pi execution inside Harbor.
- `scripts/` — bootstrap, image construction, orchestration, normalization, and trajectory parsing.
- `selection/` — frozen 18-task input and its source lock.
- `experiments/` — append-only index, compact reports, and local raw artifacts.
- `tests/` — arm-isolation, materialization, normalization, identity, and usage checks.
