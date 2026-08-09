# Repository guidance

## Source of truth

- Use `README.md` for orientation and `docs/architecture.md` for component boundaries.
- Treat `Justfile` and `scripts/lab.py` as the operator and orchestration contracts.
- Treat `experiment.lock.json`, `selection/sources.lock.json`, and `selection/selected.jsonl` as immutable experiment identity inputs.
- Model profiles live in `config/models/`; Pi and delegation policy lives in `config/pi/`, `agent/`, `harbor/pi_runner.py`, and `harbor_adapter.py`.
- `experiments/JOURNAL.jsonl` is append-only. Dated experiment directories contain evidence, not configuration.

## Workflow

Run the smallest relevant checks first:

    just check
    just test
    just dry-run smoke

`just bootstrap` downloads inputs and builds images. `just live-preflight`, `just smoke`, `just run`, and `just resume` can make paid model calls; do not run them unless the task explicitly requires live execution.

## Safety

- Never expose credentials, hidden CVDP tests, golden patches, or generated `selection/subset.jsonl` to agent-visible workspaces.
- Do not edit completed experiment artifacts or prior journal lines. Continuations create new dated experiments.
- Keep Harbor as the only task/trial orchestrator; do not add a parallel scheduler.
- Preserve baseline isolation: no WavePeek binary, skill, docs, instruction, path, or environment marker.
- Changes to pins, model profiles, Pi policy, image assets, or the frozen selection require an intentional lock update and matching tests.
- Raw `experiments/*/artifacts/` data is Git-ignored; do not delete it during cleanup or refactoring.
