# Build a reproducible WavePeek evaluation lab on Harbor

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with the `exec-plan` skill.

## Purpose / Big Picture

This repository will become a small, reproducible experiment lab that measures whether WavePeek helps Pi solve waveform-relevant CVDP hardware-design tasks. A researcher will be able to bootstrap pinned inputs, select any subset of 18 frozen tasks and either supported model, run baseline and WavePeek treatment trials through Harbor, and inspect complete trial evidence without learning Harbor internals. The final demonstration is one non-interactive Just command that launches exactly four smoke trials: one frozen task, two model profiles, one attempt, and both experimental arms.

CVDP is the Chip Verification Dataset and provides the task prompts, visible source files, hidden verification harnesses, and golden patches. Harbor is the experiment framework that owns task isolation, agent execution, attempts, concurrency, timeouts, verification, and raw trial storage. Pi is the coding agent under test. Pi-subagents is the only delegation mechanism made available to Pi. WavePeek is the waveform-inspection command available only in the treatment arm.

## Non-Goals

This work does not create another benchmark orchestrator around Harbor, modify CVDP prompts or hidden tests, expose golden patches, estimate unsupported OAuth dollar costs, add model fallbacks, or compare WavePeek releases in the smoke run. It does not make all CVDP tasks waveform-capable; the cohort is the already-frozen set of 18 tasks. It does not use commercial simulators when the pinned CVDP Icarus/Cocotb environment is sufficient.

## Progress

- [x] (2026-08-09 14:17Z) Read `docs/GOAL.md`, mapped local CVDP, Harbor, Pi, pi-subagents, WavePeek, model, credential, and simulator inputs, and recorded their immutable revisions.
- [x] (2026-08-09 14:17Z) Initialized Git history by committing the user-provided goal unchanged.
- [x] (2026-08-09 15:13Z) Added and verified the frozen cohort, source lock, lock manifest, Just interface, CVDP/Harbor bootstrap, deterministic traditional/heavy Harbor task materialization, hidden verifier boundary, and reviewed baseline/treatment images.
- [x] (2026-08-09 15:49Z) Added the pinned Harbor Pi adapter, strict pi-subagents configuration, treatment-only WavePeek environment, audit wrapper, waveform retention, exact parent/subagent usage aggregation, and live identity evidence for both model profiles.
- [x] (2026-08-09 15:49Z) Added task/model/arm/attempt/revision selectors, remote/local/branch revision resolution, offline and live preflight gates, Harbor job generation/execution/resume, exact-cell artifact normalization, comparative analysis, checksums, append-only journal, and operator documentation.
- [x] (2026-08-09 17:55Z) Ran milestone reviews, three parallel final lanes, and two independent control passes; resolved every substantive correctness, security, reproducibility, and evidence finding.
- [x] (2026-08-09 16:52Z) Executed and audited exactly four accepted smoke trials for `cvdp_agentic_axis_broadcaster_0001`, both exact model profiles, both arms, one attempt, and WavePeek 2.2.0 in run `20260809T160628Z-fbb99664`.
- [x] (2026-08-09 17:55Z) Performed the final prompt-to-artifact audit in `docs/COMPLETION_AUDIT.md`; every explicit requirement maps to code, retained raw evidence, or committed compact proof.

## Surprises & Discoveries

- Observation: the frozen 18-row `selected.jsonl` existed only in the desktop trash, although its provenance document expected it in version control.
  Evidence: `/home/esynr3z/.local/share/Trash/files/selection/selected.jsonl` has SHA-256 `945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d` and exactly 18 non-empty JSON lines.
- Observation: the locally installed `wavepeek` is version 1.0.1 and cannot represent the requested treatment.
  Evidence: WavePeek repository tag `v2.2.0` resolves to `a27a96b557cb7b9df970fbfef65a5c8354befbc9`; treatment must build from that source rather than use the host binary.
- Observation: stock Harbor preserves Pi's main JSON stream and native session but neither copies pi-subagents transcripts nor includes subagent usage in its `AgentContext`.
  Evidence: Harbor `src/harbor/agents/installed/pi.py` parses only `/logs/agent/pi.txt` after the run.
- Observation: pi-subagents 0.14.3 documents fallback from an unknown agent type to `general-purpose`, which conflicts with the no-fallback requirement.
  Evidence: its README states “Unknown types fall back to general-purpose with a note”; the experiment must patch this to a hard failure and test it.
- Observation: eight selected heavy tasks depend on sanitized Git bundles outside the JSONL dataset.
  Evidence: `scripts/bootstrap.py --heavy-bundles --verify` restored and hash-verified all 40 locked bundles, and deterministic materialization of `cvdp_agentic_heavy_2dconv-FPGA_0009` exposed its selected target from the sanitized `external/` tree.
- Observation: Harbor silently discards an invalid local task while resolving a dataset, producing only “Either datasets or tasks must be provided.”
  Evidence: the first generated package name lacked Harbor's required `org/name` form; direct `TaskConfig.model_validate_toml` exposed the validation error. Generated names now use `cvdp-eval/<task-arm>`, and a Harbor NOP trial completed the hidden verifier.
- Observation: a first milestone security review found that a root agent could replace `/venv/bin/pytest` and that a task-level auth bind exposed unrelated providers.
  Evidence: generated tasks now switch to UID/GID 1000 after root-owned verifier setup, and `harbor_adapter.py` uploads a temporary JSON file containing only the selected provider record, deletes the host temporary immediately, and removes the container copy after Pi exits.
- Observation: the initial delegated-agent patch accidentally forced child thinking to Pi's default instead of honoring the generated profile.
  Evidence: review caught `const thinkingLevel = undefined`; the patch now honors `agentConfig.thinking`, and the runner pins the child frontmatter from the parent's selected reasoning. Live preflight retained two identities per profile—parent and child—and all four identities report the exact provider/model with `xhigh`.
- Observation: Harbor task workspaces are not Git repositories by default, so a naive post-run `git diff HEAD` fails.
  Evidence: the first live preflight completed model calls but failed artifact capture with exit 129. Generated task images now create a root-protected Git directory at `/opt/cvdp-baseline` with a working-tree pointer in `/app`; the adapter captures intent-to-add, binary diff, and status through the protected baseline.
- Observation: Harbor stores the conventional `/logs/artifacts` directory at `artifacts/logs/artifacts`, not directly below `artifacts`, and a model can generate/query a waveform in `/tmp` then remove it before final collection.
  Evidence: diagnostic smoke `20260809T155016Z-1eaebab4` completed exactly four scientific cells but the first normalizer looked in the wrong artifact path; Luna treatment queried `/tmp/tb_axis_broadcast.vcd`, which was gone at final scan. The run remains immutable and rejected. Normalization now follows Harbor's manifest destination, the common runner snapshots `/app` and `/tmp` waveforms during execution, and the treatment wrapper copies each queried waveform beside its audit record.

## Decision Log

- Decision: use `Justfile` as the sole user-facing automation interface and small Python standard-library scripts behind its recipes.
  Rationale: the user explicitly required Just, and Python's standard library is enough for hashing, JSONL/TOML generation, subprocesses, archives, and reports; this avoids a project dependency layer.
  Date/Author: 2026-08-09 / coding agent
- Decision: pin WavePeek 2.2.0 by the full commit `a27a96b557cb7b9df970fbfef65a5c8354befbc9`, not by tag text or the host executable.
  Rationale: the experiment requires immutable revision identity and same-build binary, skill, and documentation.
  Date/Author: 2026-08-09 / coding agent
- Decision: pin Harbor to commit `0348989adffbb43bf0b410fd36197333239633f1` and invoke its own `harbor run --config` entry point rather than implement job loops.
  Rationale: this gives Harbor ownership of task expansion, models, attempts, concurrency, timeouts, verification, and raw results while keeping repository code limited to configuration/materialization and postprocessing.
  Date/Author: 2026-08-09 / coding agent
- Decision: maintain one generated Harbor task variant per task and arm, with tests under Harbor's hidden `tests/` mount and no golden patch materialized anywhere in the task.
  Rationale: Harbor natively withholds `/tests` until agent execution ends, so reuse its trust boundary instead of writing a new one.
  Date/Author: 2026-08-09 / coding agent
- Decision: configure only a project `general-purpose` subagent that inherits the exact parent model and `xhigh` thinking, disable nested extensions for the child, disable default Explore/Plan types, and patch unknown types to hard-fail.
  Rationale: this is the smallest configuration that permits required Pi delegation while preventing silent model/type fallback and uncontrolled nested delegation.
  Date/Author: 2026-08-09 / coding agent
- Decision: have the custom Harbor agent read external host auth, write a mode-0600 temporary file containing only the selected provider record, upload it to `/run/secrets/pi-auth.json`, and remove both copies at the earliest safe points.
  Rationale: a task-level bind of the full Pi auth file would expose unrelated provider credentials to agent shell commands. Harbor's native `upload_file` API supports per-trial provider isolation without serializing secret values into job configuration or artifacts.
  Date/Author: 2026-08-09 / coding agent

## Outcomes & Retrospective

Milestones 1–4 and the completion audit are complete. The accepted run `20260809T160628Z-fbb99664` contains exactly four complete cells with no retries or audit errors. Baseline failed both hidden verifiers; WavePeek 2.2.0 treatment passed both and made 13 audited calls per treatment. The bound live preflight is `preflights/20260809T160543Z-51062efd`; complete preflight hashes are committed in `docs/PREFLIGHT_RESULT.json`. `docs/SMOKE_ANALYSIS.md` and `docs/SMOKE_RESULT.json` preserve the compact human and machine conclusions. Final review findings were applied: infrastructure exceptions now fail audit, continuation creates immutable child runs, future runs retain generated tasks, attempts are analyzed as independent replicates, timeout/concurrency are selectable, model profiles are discovered from config, compliance requires retained supported waveform evidence, and full run verification is exposed through Just.

## Context and Orientation

`docs/GOAL.md` is the immutable product requirement. `docs/EXEC_PLAN.md` is this living implementation record. The repository started otherwise empty, so every operational file named below is new.

The frozen selection comes from CVDP tooling commit `8e894cf74414ab1eaea1e2b4e80a02f123df07b6` and CVDP v1.1.0 dataset commit `5b807d945f6a99aa645f7e43a64a2115e281b4bf`. `selection/selected.jsonl` will contain only compact metadata for 18 tasks and must always hash to `945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d`. `selection/sources.lock.json` will record source URLs, revisions, file checksums, sanitized heavy bundles, and pinned simulator image identity. Full CVDP rows are external cached inputs: traditional rows contain `system_message`, `prompt`, visible `context`, hidden `harness`, and hidden golden `patch`; heavy rows additionally refer to sanitized repository bundles. The generated task materializer copies visible context to a Docker build context and hidden harness files to Harbor's `tests/` directory. It validates target files but never writes golden patch contents.

`config/experiment.json` is the human-readable experiment configuration and `experiment.lock.json` is its immutable supply-chain lock. They pin Harbor, CVDP, WavePeek, Pi, pi-subagents, selection checksum, model profiles, defaults, images, and file hashes. The required profiles are `openai-codex/gpt-5.6-luna` and `openrouter/deepseek/deepseek-v4-flash-0731`, both with `xhigh`; additional committed profiles are discovered without runner-code edits. Pi events and native sessions are checked after every trial, and a provider/model/reasoning mismatch fails infrastructure.

`scripts/lab.py` is the standard-library command implementation called by `Justfile`; `scripts/trajectory.py` contains its pure Pi trajectory parsers. The commands verify, bootstrap, materialize, preflight, resolve/run/continue Harbor jobs, normalize, inspect, and integrity-check evidence. Generated payloads live below `.cache/`, `preflights/`, and `runs/`; compact proofs and the append-only journal are committed under `docs/`.

`harbor_adapter.py` will subclass Harbor's installed `Pi` agent only where stock behavior is insufficient. It installs exact Pi and pi-subagents package versions, prepares strict project-local Pi files, securely stages authentication, executes Pi at the exact provider/model and `xhigh`, copies the main/native/subagent trajectories, verifies provider/model/thinking metadata, aggregates main and subagent usage, and emits trial audit metadata. It must not schedule tasks, attempts, or arms.

The baseline and treatment share the same task prompt, visible files, hidden verifier, Pi version, pi-subagents version, model profile, and Harbor limits. Baseline contains no WavePeek binary, skill, docs, path, prompt reference, or environment marker. Treatment builds WavePeek from the pinned source commit in a pinned Rust builder and copies the resulting binary to the runtime image. It obtains `SKILL.md` and bundled docs from that same built binary, hashes all treatment assets, exposes the skill to Pi, and places a transparent wrapper named `wavepeek` ahead of the real binary. The wrapper records invocations without changing arguments or output. Each record includes timestamp, duration, exit status, working directory, argv, and referenced waveform paths, with no requirement that every treatment trial call WavePeek.

Harbor writes raw job and trial material beneath a dated run directory. Postprocessing adds a run-level manifest, normalized per-trial summary, per-trial final patch, verifier output, runtime, exact usage fields, model identity, trajectories, WavePeek call audit, and simple comparative analysis without deleting Harbor's raw data. `runs/JOURNAL.jsonl` is append-only: one record per experimental revision with paths and status.

## Open Questions

The run interface still needs to turn additional remote commits, local committed revisions, and branches into content-addressed treatment images without rewriting the default 2.2.0 lock. The fixed smoke revision is fully proven: `wavepeek docs export` emits 24 embedded topics from the same built binary, and binary, skill, docs, source archive, commit, and image identities are locked.

No implementation question remains. The accepted smoke proved treatment waveform-query compliance, patch capture, hidden verifier output, trajectories, usage, and normalization. The post-fix control review and formal checklist are complete. A fresh clone at commit `46ab19b` also completed `just check`, `just bootstrap`, `just test`, and a non-billing four-cell dry run with clean Git status; evidence is in `docs/CLEAN_BOOTSTRAP.md`. No required work remains.

## Plan of Work

### Milestone 1: Freeze inputs and generate faithful Harbor tasks

Copy the exact frozen selection and source lock into `selection/`, then add `experiment.toml`, `.gitignore`, `Justfile`, and the first `scripts/lab.py` implementation. `just check` will parse every selected row, reject checksum drift, reject duplicate IDs, validate all required manifest revisions, and confirm that exactly 10 traditional and 8 heavy task descriptors exist. `just bootstrap` will download or reuse CVDP source data and heavy bundles only when their hashes match the lock.

The materializer will accept task IDs and arms, locate each full CVDP row by its frozen source/line identity, and create deterministic Harbor directories beneath `.cache/tasks/`. It will write `instruction.md` from the untouched CVDP system message and prompt, copy only visible context into the environment build context, place only hidden harness in `tests/`, and generate a CVDP-compatible verifier entry point. It will assert that no golden patch bytes or patch JSON are written. A fixture-based test will exercise this boundary without network access. At the end of this milestone, `just materialize cvdp_agentic_axis_broadcaster_0001 baseline` will produce a valid Harbor task, and repeated materialization will produce identical content.

A reviewer subagent will inspect input integrity, hidden/visible separation, heavy-task handling, and whether the generated verifier faithfully calls CVDP's harness. Findings will be fixed before continuing.

### Milestone 2: Make Pi arms reproducible inside Harbor

Add the custom Harbor Pi adapter and strict Pi project template. Pin Pi 0.80.1 and pi-subagents 0.14.3. Vendor only the minimal pi-subagents source patch needed to turn an unknown or disabled type into a hard error; preserve the package license and record the source Git commit. Set `general-purpose` to inherit the parent model, force `xhigh`, retain transcript output, persist sessions below `/logs/agent`, and load no extensions in children. Disable Explore and Plan. Ensure model scoping lists only the exact parent model for each generated trial.

Generate distinct baseline and treatment Dockerfiles. The baseline validation scans its whole generated build context and configuration for forbidden WavePeek names and paths. The treatment performs a multi-stage build from WavePeek commit `a27a96b557cb7b9df970fbfef65a5c8354befbc9`, verifies version `v2.2.0`, emits the skill/docs from that source, and installs the audit wrapper. Unit checks will prove transparent stdout/stderr/status behavior and well-formed audit JSONL. Adapter tests will feed synthetic main and subagent transcripts and assert exact input, output, cache-read, cache-write, and reported-cost aggregation.

Use Harbor's install-only path with a no-model-call fixture to prove local adapter import, Pi/package installation, auth staging, baseline absence, treatment identity, and trajectory collection. A reviewer subagent will inspect provider/model enforcement, fallback prevention, secret handling, arm isolation, WavePeek provenance, and usage arithmetic. Resolve all findings before continuing.

### Milestone 3: Add run, results, journal, and operator workflow

Extend `scripts/lab.py` to resolve task/model/arm/attempt/revision selectors, preflight dependencies, and emit one Harbor `JobConfig` JSON. It will call pinned Harbor's own CLI once per experimental revision. Harbor, not the script, expands task/model/attempt combinations and owns concurrency and retry behavior. The smoke selector will assert its Cartesian product is exactly four before launch.

After Harbor exits, postprocessing will preserve its raw directory and derive stable run/trial manifests. It will capture the final Git diff from `/app`, verifier logs and reward, wall time, main/subagent trajectories, exact model events, usage, WavePeek audit, and run status. Analysis will report per-arm and per-model pass counts and pairwise deltas, labeling four-cell smoke output as infrastructure validation rather than statistical evidence. Journal append will use exclusive file creation/locking semantics and never rewrite prior records.

Write `README.md` with bootstrap, selection, dry-run, subset, full matrix, resume/retry, analysis, and smoke commands. No direct Python or Harbor knowledge should be required for normal use. `just --list` must expose the workflow. A reviewer subagent will inspect that Harbor remains the only orchestrator, every output requirement is covered, the journal is append-only, and commands are reproducible from a clean checkout.

### Milestone 4: Validate and execute the smoke experiment

Run all local checks, deterministic materialization checks, Docker build checks, Harbor install-only tests, and a verifier-only oracle/fixed-patch fixture before spending model calls. Inspect generated configs to prove exactly the requested task, two exact profiles, both arms, one attempt, `xhigh`, and WavePeek commit. Then launch the single non-interactive smoke recipe. It must create exactly four completed Harbor trials and no retries unless an infrastructure failure is explicitly recorded rather than hidden.

Audit each trial's raw and normalized artifacts. Verify provider/model/thinking from emitted events, full main and subagent trajectories, usage fields, patch, verifier output, and WavePeek audit. Confirm baseline contains no WavePeek trace and treatment provenance hashes agree. Append one journal line and generate comparative analysis. Spawn parallel final reviewers for correctness/reproducibility, experiment leakage/security, and requirement coverage. Fix any issue and rerun only invalid infrastructure trials with explicit journal lineage; do not silently replace scientific outcomes.

## Concrete Steps

All commands run from the repository root `/home/esynr3z/projects/wavepeek-eval`.

First validate and bootstrap immutable inputs:

    just check
    just bootstrap

Expected output includes the selection identity and exact revisions:

    selected.jsonl: 18 rows, sha256=945c389...124d
    WavePeek: a27a96b557cb7b9df970fbfef65a5c8354befbc9 (v2.2.0)
    inputs: verified

Materialize and inspect the smoke task without model calls:

    just materialize cvdp_agentic_axis_broadcaster_0001 baseline
    just materialize cvdp_agentic_axis_broadcaster_0001 wavepeek
    just dry-run smoke

The dry run must print four cells and finish with:

    trials=4 tasks=1 models=2 arms=2 attempts=1

Run local and container validation:

    just test
    just preflight smoke

Launch the only required paid/external demonstration:

    just smoke

After completion, inspect normalized status and analysis:

    just status latest
    just analyze latest

To run an arbitrary subset later, use selectors exposed by `just run`, for example:

    just run 'cvdp_agentic_axis_broadcaster_0001,cvdp_agentic_lfsr_0001' all all 1

The README and `just --list` will define the exact argument order and accepted selector values.

## Validation and Acceptance

`just check` must fail on a one-byte selection change, an unknown selected ID, a mismatched source line, a revision that is not a full SHA, a model other than the two exact profiles, or a WavePeek version/commit mismatch. Its successful output must count all 18 frozen tasks.

`just test` must cover manifest parsing, selector Cartesian products, smoke cardinality, deterministic task materialization, hidden/golden separation, strict subagent type handling, usage aggregation, WavePeek wrapper transparency/audit output, result normalization, and append-only journal behavior. Container checks must establish that the baseline cannot resolve or discover WavePeek and that treatment reports version 2.2.0 with matching binary/skill/docs provenance.

A generated Harbor config must contain one CVDP dataset/task set, two exact Pi agent model configurations for smoke, `thinking=xhigh`, one attempt, both generated arm tasks, explicit concurrency/timeouts, no retries that alter scientific outcomes, read-only auth mounting, and the local adapter import path. Harbor's own lock/config files in the completed job are the authoritative resolved execution input.

The smoke acceptance is exactly four Harbor trial directories corresponding to one task times two models times two arms times one attempt. Every trial must retain raw Harbor config/lock/result/log files, main Pi JSON stream, native Pi session, every subagent transcript/session if delegation occurred, exact token fields, reported cost if available, final patch, full verifier logs/reward, runtime, and arm metadata. Baseline evidence must show no WavePeek installation, skill, docs, prompt reference, executable invocation, or environment marker. Treatment evidence must identify commit `a27a96b557cb7b9df970fbfef65a5c8354befbc9`, version 2.2.0, asset hashes, and a valid call audit that may contain zero calls.

The final analysis must state pass/fail by model and arm, usage/runtime comparisons, and WavePeek call counts without claiming statistical significance. `runs/JOURNAL.jsonl` must gain exactly one immutable line for the smoke revision and retain any prior lines byte-for-byte.

## Idempotence and Recovery

Bootstrap uses content-addressed cache paths and verifies before reuse, so interruption is safe: rerun `just bootstrap`. Materialization writes to a temporary sibling and atomically renames it only after validation, so rerunning cannot expose a partial task. WavePeek and Docker images are keyed by immutable commits and content hashes.

Each experiment revision gets a unique UTC timestamp plus manifest digest. A failed run remains in place with status and logs. Resume or infrastructure retry creates explicit lineage in a new job/revision record and never overwrites or relabels the failed trial. Journal appends are atomic and guarded by a lock; analysis is derived and may be regenerated inside the same run directory only when its input manifest digest matches.

Credentials are never copied into the repository, generated tasks, or run artifacts. They are read-only mounted into an ephemeral container path and copied to the ephemeral agent home with mode 0600. Recovery from missing credentials is to configure Pi on the host and rerun preflight; scripts must not prompt for or serialize credential values.

## Artifacts and Notes

Pinned identities discovered before implementation:

    CVDP tooling     8e894cf74414ab1eaea1e2b4e80a02f123df07b6
    CVDP dataset     5b807d945f6a99aa645f7e43a64a2115e281b4bf
    selected.jsonl   945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d
    Harbor           0348989adffbb43bf0b410fd36197333239633f1
    WavePeek 2.2.0   a27a96b557cb7b9df970fbfef65a5c8354befbc9
    Pi               0.80.1
    pi-subagents     0.14.3 (package Git head c10b1836256e760da75296ccd4e57a77ada1325e)

Exact model profiles:

    GPT-5.6 Luna              openai-codex/gpt-5.6-luna
    DeepSeek V4 Flash 0731    openrouter/deepseek/deepseek-v4-flash-0731

## Interfaces and Dependencies

`Justfile` is the stable operator interface. It must provide at least `check`, `bootstrap`, `materialize TASK ARM`, `dry-run SELECTOR`, `preflight SELECTOR`, `test`, `run TASKS MODELS ARMS ATTEMPTS`, `smoke`, `status RUN`, and `analyze RUN`. Recipes call `python3 scripts/lab.py ...` and pinned Harbor through `uvx`; they do not duplicate shell control flow.

`config/experiment.json`, `experiment.lock.json`, and `config/models/*.json` are parsed with the Python standard library. Revisions and hashes are full lowercase hexadecimal strings. Profiles have stable keys, exact `provider/model`, reasoning, credential policy, and optional compatibility data. Arms are `baseline` and `wavepeek@<sha>`.

`scripts/lab.py` exposes a command-line `main(argv: list[str] | None = None) -> int`. Internal pure helpers accept `pathlib.Path` and dictionaries so the built-in `unittest` suite can exercise them without external services. Subprocess execution uses argument arrays, never shell interpolation, except the fixed Just/Harbor entry commands.

`harbor_adapter.py` defines `class ReproduciblePi(harbor.agents.installed.pi.Pi)`. It overrides only installation, run setup/collection, and post-run context aggregation. Harbor discovers it through `harbor_adapter:ReproduciblePi` from the repository root. It keeps Harbor's `Pi.run` semantics and `ModelConnectionSpec` rather than introducing a second agent protocol.

External runtime dependencies are Docker, Git, Just, Python 3.12+, uv, first-bootstrap network access, configured Pi providers, and sufficient disk. Harbor, Pi, pi-subagents, Rust/Node builders, simulator, CVDP inputs, and WavePeek are pinned by immutable checksum/commit in `experiment.lock.json` and `selection/sources.lock.json`.

Plan revision note (2026-08-09): created the initial self-contained plan after repository and dependency research; recorded unresolved heavy-bundle and Harbor-mount details as explicit proof obligations rather than assumptions.

Plan revision note (2026-08-09 15:13Z): recorded completed and independently reviewed Milestone 1, the native Harbor credential-upload design that replaced an unsafe full-auth bind, resolved bundle/docs/adapter questions, and the remaining paid-session and multi-revision proof obligations.

Plan revision note (2026-08-09 15:49Z): recorded completed Milestones 2–3, reviewer-driven delegated-thinking and exact-cell fixes, the successful content-bound live parent/subagent preflight for both models, and the Git-baseline artifact design discovered during live execution.

Plan revision note (2026-08-09 16:07Z): recorded the rejected first four-cell diagnostic smoke, Harbor's actual conventional-artifact destination, and the live waveform snapshot/queried-file retention fixes required before the accepted smoke.

Plan revision note (2026-08-09 17:05Z): recorded the accepted four-cell run, complete live-preflight proof, final three-lane review findings and fixes, config-driven profiles/settings, immutable continuation, future task retention, and the remaining control pass/completion audit.

Plan revision note (2026-08-09 17:55Z): recorded successful clean-checkout bootstrap, two completed control passes, retained executed-task snapshots for future runs, strict retained-waveform compliance, complete generic analysis/journal output, and final prompt-to-artifact completion.
