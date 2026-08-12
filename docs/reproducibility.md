# Reproducibility and evidence

## Frozen identity

`experiment.lock.json` is the machine-readable identity of the default experiment environment. It pins CVDP, Harbor, WavePeek, Pi, pi-subagents, toolchain images, model-profile hashes, generated assets, and final arm image IDs.

Related sources of truth are:

- `selection/selected.jsonl` — exactly 18 native CVDP tasks;
- `selection/sources.lock.json` — CVDP dataset, tooling, files, bundles, and simulator image;
- `config/experiment.json` — runtime defaults and fixed policy;
- `config/models/*.json` — exact selectable model profiles;
- `config/pi/` — the Pi model catalog and subagent settings.

Run `just check` before materializing or executing anything. It rejects changed pins, an unlocked model profile, an altered task selection, unsupported required model identities, and relaxed delegation policy.

Update `experiment.lock.json` only for an intentional new default identity:

    python3 scripts/build_images.py --update-lock

Review the resulting lock and image changes before committing. Ordinary candidate WavePeek revisions use per-run manifests and do not rewrite the default lock.

## Frozen CVDP cohort

The selected manifest has 18 unique tasks: 10 traditional and 8 heavy. All use CVDP native execution mode. The selection hash is fixed in both code and `experiment.lock.json`.

Traditional rows materialize their visible CVDP context. Heavy rows are checked out from the exact sanitized Git bundle and commit in `selection/sources.lock.json`, exposing only the expected `external/` workspace. Generated Harbor tasks contain the prompt, visible workspace, metadata, and hidden verifier integration, but never a golden patch or solution artifact.

## Evidence boundary

A scientific run is stored as:

    experiments/YYYY-MM-DD_HHMMSSZ_<name>_<id>/
      analysis.md
      result.json
      artifacts/
        manifest.json
        harbor-job.json
        inputs/tasks/
        sources/
        harbor/
        summary.json
        analysis.json
        analysis.md
        run-checksums.json

A live preflight uses the same dated convention and stores `result.json`, reusable `preflight.json`, and raw Harbor data under `artifacts/`.

`run-checksums.json` seals the complete scientific artifact file set. `just verify <experiment>` detects added, removed, or changed raw files and validates any bound preflight marker and evidence hashes. The checksum is tamper-evidence, not filesystem write protection.

The full Harbor tree retains, when applicable:

- Harbor config, lock, result, and logs;
- hidden verifier stdout and reward;
- parent Pi event stream and native session;
- every delegated transcript and persistent child session;
- main, child, and total token/cache usage;
- final patch and Git status;
- exact model and reasoning identity;
- WavePeek invocation audit, including explicitly supplied waveform paths.

Provider-reported cost is currently unavailable and remains `null`. Pi catalog calculations are retained separately as labeled estimates and are not presented as billing evidence.

## Journal and immutability

`experiments/JOURNAL.jsonl` is append-only. Every new run or preflight adds a JSON line; historical records are never edited or removed. Archive migrations are represented by additional mapping events.

A continuation creates a new experiment and records the parent manifest path and hash. It does not modify the parent. Harbor retries remain zero; multiple attempts are explicit independent replicates.

Compact reports are versioned. Raw `experiments/*/artifacts/` directories are intentionally ignored by Git because they contain large trajectories, source archives, and Harbor payloads. Back up or publish those directories separately when full evidence must survive beyond the local workspace; the Git repository alone does not contain raw trials.

## Arm and verifier isolation

Baseline and treatment share task inputs, Pi, model profile, delegation policy, timeouts, and hidden verifier. Only the declared WavePeek treatment assets and instruction differ.

Harbor mounts hidden tests after agent execution. The agent-visible workspace must never receive hidden harnesses, generated `selection/subset.jsonl`, credentials, or solution patches. Benchmark reward is separate from infrastructure status: reward zero is a valid failed solution, while missing evidence or execution exceptions make the experiment audit fail.
