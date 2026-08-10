# Running experiments

## Bootstrap

From the repository root:

    just bootstrap
    just test

Bootstrap downloads and verifies the pinned CVDP inputs, installs the pinned Harbor checkout, and builds the locked baseline and treatment images. It is safe to rerun; fetched sources and generated datasets are cached below `.cache/`.

Useful checks that do not call a model:

    just check
    just materialize cvdp_agentic_axis_broadcaster_0001 baseline
    just dry-run smoke
    just preflight smoke

`preflight` checks host tools, credentials, Harbor, image identities, and matrix resolution. `dry-run` materializes and prints the Harbor job but does not validate live model access.

## Smoke experiment

    just smoke

This is a paid command. It first runs or reuses a live model/delegation preflight, then executes exactly four Harbor trials:

- one fixed CVDP task;
- the two required model profiles;
- baseline and WavePeek arms;
- one attempt.

Force a new paid live preflight with:

    python3 scripts/lab.py live-preflight --force

A live preflight proves that each required parent can call one `general-purpose` child with the same provider, model, and reasoning level. Additional model profiles are not automatically included in this gate.

## Select a matrix

`just run` makes paid model calls. Resolve a small matrix with `dry-run` first.

The complete interface is:

    just run TASKS MODELS ARMS ATTEMPTS REVISIONS NAME \
      [CONCURRENCY] [AGENT_TIMEOUT] [VERIFIER_TIMEOUT]

`TASKS` and `MODELS` accept `all` or comma-separated IDs. `ARMS` accepts `baseline`, `wavepeek`, `all`, or a comma-separated subset. `ATTEMPTS` is a positive integer. `REVISIONS` is `default` or a comma-separated revision list. The default agent timeout is 7200 seconds (two hours). Attempts are independent replicates. Harbor retries are fixed to zero so a failed scientific outcome is never silently replaced.

Examples:

    just run all all all 1 default full

    just run \
      'cvdp_agentic_axis_broadcaster_0001,cvdp_agentic_lfsr_0001' \
      openai-codex-gpt-5.6-luna-xhigh \
      all 1 default luna-subset

`just --list` is the concise command reference. Use `just dry-run smoke` or `python3 scripts/lab.py job ... --dry-run` before a large matrix.

## Compare WavePeek revisions

`REVISIONS` accepts:

- `default` for the commit in `experiment.lock.json`;
- a full commit SHA from the configured WavePeek repository;
- a clean local checkout, optionally followed by `#branch-or-commit`;
- a Git URL followed by `#branch-or-commit`.

Multiple comma-separated revisions produce one treatment variant per resolved commit and one shared baseline:

    just run cvdp_agentic_axis_broadcaster_0001 all all 1 \
      '/work/wavepeek#topic-a,https://github.com/kleverhq/wavepeek#topic-b' \
      revision-comparison

Every selector resolves to a full commit before Harbor starts. Candidate source archives, build manifests, image IDs, and WavePeek asset hashes are retained with the experiment.

## Harbor ownership

The supported entry point is `Justfile`; do not hand-build a second trial loop around Harbor. `scripts/lab.py` emits one Harbor JobConfig containing the selected task dataset, one agent configuration per model profile, attempts, concurrency, zero retries, output directory, and job name. Agent and verifier timeouts are retained in each generated Harbor task configuration.

Harbor's checkout and Python environment live at `.cache/harbor/source`. Refresh it to the pinned revision with:

    python3 scripts/lab.py harbor-bootstrap

Raw Harbor job and trial directories remain unmodified beneath each experiment's `artifacts/harbor/` tree.

## Inspect and continue

    just status latest
    just analyze latest
    just verify latest

These commands also accept a dated experiment directory name or a historical run ID.

Use continuation only for interrupted infrastructure work. This is a paid model run:

    just resume <experiment-or-run-id>

Continuation creates a new dated experiment with a hashed `parent_run` reference. It never mutates the parent and currently reruns the selected matrix. A verifier reward of zero is a benchmark outcome, not a reason to resume.

## Experiment names

Every run receives a sortable UTC name:

    YYYY-MM-DD_HHMMSSZ_<name>_<random-id>

Choose a short `NAME` that describes the question, such as `luna-subset` or `revision-comparison`. All files for that run remain beneath the resulting `experiments/` directory.
