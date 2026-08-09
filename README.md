# WavePeek × CVDP evaluation lab

This repository measures whether WavePeek helps Pi solve a frozen 18-task, waveform-relevant CVDP cohort. Harbor is the only experiment orchestrator: it owns task/model/attempt expansion, concurrency, isolation, timeouts, verification, retries, and raw trial storage. Repository scripts only verify pinned inputs, materialize Harbor tasks, invoke Harbor once, and normalize retained evidence.

The two arms are identical except for the declared treatment. Baseline has no WavePeek binary, skill, docs, instruction, path, or environment marker. `wavepeek@<sha>` adds a binary, generated official skill, exported embedded docs, and transparent invocation wrapper built from one immutable source commit. Treatment requires at least one successful WavePeek query against a waveform; use is measured rather than faked by a separate tool.

## Prerequisites and credentials

Use Linux x86-64 with Docker, Git, Python 3.12+, `uv`, and Just. The first bootstrap needs HTTPS access and approximately 20 GB of cache/image space.

Pi credentials remain external. By default the Harbor adapter reads `~/.pi/agent/auth.json`; override the path without copying it into the repository:

    export WAVEPEEK_EVAL_AUTH_FILE=/secure/path/auth.json

The file must contain `openai-codex` and `openrouter` records for the full smoke. `OPENROUTER_API_KEY` may replace the OpenRouter record. For each trial, the adapter uploads only that trial's provider record into ephemeral container storage and deletes it after Pi exits. Secret values are never written to Harbor config, logs, or artifacts.

The exact model profiles are:

- `openai-codex-gpt-5.6-luna-xhigh` → `openai-codex/gpt-5.6-luna`;
- `openrouter-deepseek-v4-flash-0731-xhigh` → `openrouter/deepseek/deepseek-v4-flash-0731`, with OpenRouter fallbacks disabled.

Both main and delegated `general-purpose` agents use `xhigh`. Delegated agents inherit the parent's exact model; unknown types, extra defaults, scheduling, nested delegation, and model fallback fail closed.

## Bootstrap and offline validation

From a clean checkout:

    just bootstrap
    just test

Bootstrap verifies the frozen CVDP source/dataset commits, all JSONL and sanitized bundle hashes, the simulator image ID, Pi and pi-subagents sources, WavePeek source archive, and final arm image IDs. It pins Harbor at `0348989adffbb43bf0b410fd36197333239633f1`.

Useful non-billing checks are:

    just check
    just materialize cvdp_agentic_axis_broadcaster_0001 baseline
    just dry-run smoke
    just preflight smoke
    just live-preflight

`live-preflight` performs two tiny non-CVDP Harbor trials, one per model. Each parent must launch exactly one `general-purpose` child; retained events and sessions must prove the same provider/model and `xhigh` for parent and child. A content-identity marker reuses a still-valid successful preflight. `just smoke` runs or reuses this gate automatically.

The smoke dry run must end with:

    trials=4 tasks=1 models=2 arm_variants=2 attempts=1

## Run interfaces

The required smoke is one non-interactive command:

    just smoke

It resolves exactly one task (`cvdp_agentic_axis_broadcaster_0001`), both exact model profiles, baseline plus WavePeek 2.2.0 at commit `a27a96b557cb7b9df970fbfef65a5c8354befbc9`, and one attempt: exactly four Harbor trials.

Run the full fixed cohort with:

    just run all all all 1 default full

Or select comma-separated task/model/arm values:

    just run 'cvdp_agentic_axis_broadcaster_0001,cvdp_agentic_lfsr_0001' \
      openai-codex-gpt-5.6-luna-xhigh all 1 default luna-subset

The positional arguments are `tasks models arms attempts revisions name`; `just --list` is the authoritative quick reference. Arms are `baseline`, `wavepeek`, or `all`. Harbor retries are fixed to zero so scientific outcomes are never silently replaced; attempts are explicit matrix cells.

WavePeek revisions accept a full SHA, a clean local checkout optionally followed by `#branch-or-commit`, or a remote Git URL followed by `#branch-or-commit`. Comma-separated revisions compare multiple treatment commits against one shared baseline:

    just run cvdp_agentic_axis_broadcaster_0001 all all 1 \
      '/work/wavepeek#topic-a,https://github.com/kleverhq/wavepeek#topic-b' revision-comparison

Every selector resolves to a full commit before execution. Each candidate gets a content-addressed source archive, image, binary/skill/docs hashes, and run-level retained source artifact; no task or runner code changes are needed.

Resume only interrupted infrastructure work in the same Harbor job:

    just resume <run-id>

Harbor preserves completed trials. Resume appends another journal event and never deletes the original evidence. Do not resume ordinary benchmark failures.

## Results

Inspect a run with:

    just status latest
    just analyze latest

Each `runs/<run-id>/` directory contains the resolved manifest, unmodified Harbor job/trial trees, normalized `summary.json`, `analysis.json`, source archives, and exhaustive `run-checksums.json`. Every completed trial must retain:

- Harbor config, lock, result, and logs;
- main Pi event stream and native session;
- every pi-subagents transcript and persistent native child session, when delegation occurs;
- exact main, per-subagent, and total input/output/cache-read/cache-write usage plus provider-reported cost fields;
- final patch and Git status;
- full verifier stdout and reward;
- retained waveform files and hashes;
- exact provider/model/reasoning identity;
- WavePeek call audit with timestamps, duration, status, working directory, argv, waveform paths, and binary hash.

OAuth monetary cost is not invented. Pi usage remains recorded, but subscription-backed Luna cost is reported as unavailable. Smoke analysis is explicitly labeled infrastructure evidence, not a causal performance claim.

`docs/EXPERIMENT_JOURNAL.jsonl` is append-only and points to each content-addressed run manifest/checksum set. Generated run payloads are ignored by Git; the journal and committed experiment definitions are versioned.

Never place CVDP golden patches, hidden tests, credentials, or generated `selection/subset.jsonl` in agent-visible workspaces. Harbor mounts hidden tests only after agent execution.
