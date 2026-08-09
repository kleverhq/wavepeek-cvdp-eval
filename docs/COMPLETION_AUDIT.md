# Completion audit against `docs/GOAL.md`

Audit date: 2026-08-09. Accepted smoke: `20260809T160628Z-fbb99664`. Rejected diagnostic: `20260809T155016Z-1eaebab4`. This checklist maps each explicit requirement to current code or retained evidence; proxy signals are not used alone.

## 1. Purpose and orchestration boundary

- **Harbor is the outer framework.** `runs/20260809T160628Z-fbb99664/manifest.json` records one `harbor run` command at pinned commit `0348989adffbb43bf0b410fd36197333239633f1`. It passes task dataset, custom Pi adapter, two models, attempts, concurrency, zero retries, output directory, and job name in one invocation.
- **No second task/attempt scheduler exists.** `scripts/lab.py` resolves selectors and materializes Harbor tasks, then invokes Harbor once. Harbor's job/trial config, lock, result, logs, verifier and random trial names are retained below the run's `harbor/` tree.
- **Pi delegation uses pi-subagents.** `agent/Dockerfile`, `agent/patch-pi-subagents.py`, `agent/common/general-purpose.md`, and `experiment.lock.json` pin pi-subagents commit `2966cd5a33c0640de9698b56a39c11f83207a835`. No custom child-agent protocol is implemented.

## 2. Frozen inputs and cohort

- **Selection is immutable.** `selection/selected.jsonl` has exactly 18 unique native tasks and SHA-256 `945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d`. `scripts/lab.py check` fails on drift.
- **CVDP sources are pinned.** Tooling commit `8e894cf74414ab1eaea1e2b4e80a02f123df07b6`, dataset commit `5b807d945f6a99aa645f7e43a64a2115e281b4bf`, 45 dataset/bundle hashes, simulator image ID, and tool versions are in `selection/sources.lock.json` and `experiment.lock.json`.
- **Cached full rows and heavy bundles are authenticated at materialization time.** `full_row()` verifies the full JSONL digest before reading prompt/context/harness; heavy materialization verifies the selected sanitized bundle before Git checkout.
- **No golden patch enters generated tasks.** Materialization writes only system message + prompt, visible context/sanitized `external/` tree, and hidden Harbor `tests/`; tests reject solution artifacts. Hidden CVDP tests are mounted by Harbor only after agent execution.
- **All 18 tasks are selectable.** A non-billing all-cohort resolution produced `trials=36 tasks=18 models=1 arm_variants=2 attempts=1` and 36 valid Harbor task directories. Unit tests separately exercise traditional and heavy targets.

## 3. Exact model profiles and delegation policy

- **Required profiles are exact.** `config/models/` maps GPT-5.6 Luna to `openai-codex/gpt-5.6-luna` and DeepSeek V4 Flash 0731 to `openrouter/deepseek/deepseek-v4-flash-0731`; both are `xhigh`. OpenRouter `allow_fallbacks` is false.
- **Profiles are config-driven.** `scripts/lab.py` discovers all committed model JSON files; `harbor_adapter.py` validates the selected provider/model/reasoning against those files and sends the complete non-secret profile to the runner. Additional profiles, including different reasoning levels, require config/lock updates, not runner branching; the resolved Harbor JobConfig carries reasoning per agent.
- **Main and child identity fail closed.** The adapter validates every assistant event and every native main/child session against exact provider/model/reasoning. An unavailable or substituted model raises infrastructure failure.
- **Only `general-purpose` delegation is exposed.** Project-local defaults, Explore, Plan, unknown fallback, scheduling and nested extension loading are disabled. The patched extension honors only frontmatter thinking, generated from the selected parent reasoning; child model remains inherited.
- **Live proof exists.** `docs/PREFLIGHT_RESULT.json` hashes all 106 files from preflight `20260809T160543Z-51062efd`. Each model's parent called one `general-purpose` child; parent and child reported the same exact provider/model and `xhigh`, with main event stream, native sessions, child transcript/session and usage retained.

## 4. Arms, fairness and WavePeek provenance

- **Baseline is clean.** Image and generated-context tests prove no WavePeek command, `/opt/wavepeek`, skill, docs, instruction, or environment marker. Accepted baseline trials record zero WavePeek calls.
- **Treatment difference is explicit.** Treatment appends one fixed instruction and adds only pinned binary, official generated skill, exported embedded docs, wrapper, and treatment image layers. CVDP prompt/context/harness, Pi, subagents, model, limits and verifier remain shared.
- **WavePeek 2.2.0 is immutable.** Tag `v2.2.0` resolves to `a27a96b557cb7b9df970fbfef65a5c8354befbc9`. The lock records source archive, Cargo.lock, binary, skill, docs and image hashes. Default remote rebuild reproduced the locked image IDs.
- **Remote, SHA, branch and local committed revisions are supported.** `--revisions` accepts a SHA, clean local path with optional `#ref`, or URL with `#ref`, resolves to a full commit, builds content-addressed treatment images, preserves requested selector/repository/commit, and supports multiple treatment revisions against one baseline. Unit tests prove baseline is not duplicated.
- **Use is measured and required, not faked.** The transparent wrapper preserves stdout/stderr/status and records start/end, duration, cwd, argv, binary hash, supported waveform paths and retained waveform hashes. Normalization counts only successful known query commands whose retained files exist inside the artifact root and match their SHA-256.
- **Waveforms are retained.** The common runner snapshots `.vcd`, `.vcd.gz`, `.fst` and `.fsdb` files from `/app` and `/tmp` during execution; the treatment wrapper immediately copies queried waveforms. Accepted checksums list waveform artifacts for every cell.

## 5. Matrix, settings and run interface

- **Matrix dimensions are represented.** Tasks, profile IDs, baseline/treatment revisions, independent attempts, concurrency, agent/verifier timeouts and full revision records are stored in the resolved matrix. WavePeek revision count expands treatment variants without duplicating baseline.
- **Settings are selectable.** `just run` exposes tasks, models, arms, attempts, revisions, name, concurrency, agent timeout and verifier timeout. Values are validated, written into task TOML/job command, and retained in future run manifests.
- **One non-interactive interface exists.** `Justfile` exposes `bootstrap`, `check`, `test`, `materialize`, `dry-run`, `preflight`, `live-preflight`, `run`, `smoke`, `resume`, `status`, `analyze` and `verify`. `README.md` documents credentials and exact examples.
- **Retries do not replace scientific outcomes.** Harbor receives `--max-retries 0`; attempts are explicit independent cells. Infrastructure exceptions now make audit fail. Continuation creates a new run with content-hashed parent lineage and never rewrites its parent.

## 6. Required per-trial and run outputs

- **Raw Harbor evidence is complete.** Each accepted trial retains config, lock, result, trial log, full verifier stdout/reward, main Pi stream/session, trajectory index, final response, patch/status, session stats and artifact manifest.
- **Delegated evidence is conditional and complete.** Luna baseline used one child and retains both `.output` transcript and persistent child session. Other cells used no child and truthfully retain empty child lists.
- **Usage is exact and separated.** Summary retains main, per-child and total input/output/cache-read/cache-write values. `reportedCost` is null; Pi catalog calculations are separately labeled `piCalculatedCost`, not billing evidence.
- **Patch and verifier output exist for all four cells.** `missing_evidence` is empty and `infrastructure_status` is complete in `summary.json`; benchmark reward remains separate from infrastructure state.
- **WavePeek audit is complete.** Each treatment made 13 calls, with 9/11 successful meaningful queries respectively and retained query files. Baselines made zero calls.
- **Run identity and source are retained.** Manifest records all source/tool/image/profile hashes and a content-addressed WavePeek source tar. Future runs execute from and checksum `runs/<id>/inputs/tasks`; for the accepted run, `docs/SMOKE_TASKS.json` records post-run deterministic archives whose Harbor content digests exactly match every accepted trial lock.
- **Output integrity is checkable.** `run-checksums.json` covers 230 accepted files. `python3 scripts/lab.py verify 20260809T160628Z-fbb99664` recomputed the complete file set/hashes and bound preflight proof successfully.

## 7. Analysis and journal

- **Machine analysis exists.** Accepted `analysis.json` contains all cells and model comparisons; attempts are treated as independent replicates in current code rather than arbitrarily paired.
- **Human analysis exists.** `docs/SMOKE_ANALYSIS.md` covers purpose, selection, results, usage/runtime, WavePeek total duration, trajectory/delegation differences, conclusions, limitations and raw/checksum pointers.
- **Compact machine proof exists.** `docs/SMOKE_RESULT.json`, `docs/PREFLIGHT_RESULT.json` and `docs/SMOKE_TASKS.json` preserve accepted outcomes and immutable pointers while large payloads remain ignored.
- **Journal is append-only.** `docs/EXPERIMENT_JOURNAL.jsonl` retains the rejected diagnostic, accepted raw run event, and enriched acceptance event. The rejected run is not silently relabeled or deleted.

## 8. Required final smoke

- **Exact cardinality.** Run `20260809T160628Z-fbb99664` has exactly four observed and expected cells: one task × two exact profiles × baseline/treatment × one attempt. Harbor recorded zero retries and no exceptions/audit errors.
- **Results.** Both baseline cells failed the hidden benchmark; both WavePeek treatment cells passed. Both treatment cells are compliant and each made 13 audited calls. All four provider/model/reasoning identities are exact.
- **Interpretation is bounded.** The committed analysis explicitly states that four trials are infrastructure evidence, not a defensible causal claim.

## 9. Clean-checkout proof

- **Bootstrap was exercised from a new clone.** `docs/CLEAN_BOOTSTRAP.md` records `just check`, `just bootstrap`, `just test`, and `just dry-run smoke` from `/tmp/wavepeek-eval-clean` at commit `46ab19b`. Bootstrap downloaded and verified all 45 CVDP inputs, reproduced locked images, created the runner environment, installed pinned Harbor, passed 17 tests, resolved exactly four smoke cells, and left Git clean. It made no model calls.

## Audit conclusion

All explicit deliverables and completion criteria in `docs/GOAL.md` have concrete code or artifact evidence. The full 18-task, multi-attempt scientific matrix was intentionally not run because the goal requires infrastructure readiness and a four-cell demonstration, not a full benchmark result. No required work remains after the final control review and verification commands recorded above.
