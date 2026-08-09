# Goal: Build a Minimal WavePeek × CVDP Research Lab

Build a small, reproducible Harbor-based workspace for repeated experiments that measure whether forced use of WavePeek helps coding agents debug existing CVDP tasks.

This is a research workspace for iterating on WavePeek's CLI, skill, and embedded documentation, not a one-off benchmark script. Keep it deliberately small: Harbor owns orchestration and trial storage, CVDP owns the tasks and objective verification, and the repository contains only the thin integration needed between them.

The workspace must support arbitrary selections from:

```text
CVDP task × model profile × arm × attempt × WavePeek revision
```

Finish by running the smoke experiment defined below.

## Fixed task set

Use the existing `selected.jsonl` as the immutable source of the 18 selected datapoints.

```text
SHA-256: 945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d
execution mode: native
```

Fail clearly if the file or digest differs. Do not reselect tasks, create mutations, or add synthetic datapoints.

Reuse the existing CVDP prompts, visible RTL/testbench files, harnesses, and objective verifier. The agent must not see hidden evaluator code, golden patches, or expected answers.

## Required foundation

Use Harbor as the outer orchestration layer for isolated trials, attempts, models, timeouts, artifacts, trajectories, and results.

Create only the minimal CVDP-to-Harbor adaptation required for the frozen tasks. Do not run the complete CVDP orchestrator inside Harbor, and do not build another scheduler, database, dashboard, or viewer around Harbor.

Use Pi with `tintinweb/pi-subagents` in every arm. Expose only the `general-purpose` subagent. It must inherit the exact parent model and reasoning level. Disable the other built-in agent types, nested delegation, and silent fallback to another subagent or model.

Preserve the main Pi trajectory and every created subagent trajectory. Usage totals must include subagent work when subagents are used. Extend Harbor's existing Pi support only where needed to install `pi-subagents`, preserve its transcripts, or complete usage accounting.

## Model profiles

Start with two committed profiles:

```text
gpt-5.6-luna-xhigh
  model: GPT-5.6 Luna
  auth: Codex OAuth from the user's ChatGPT subscription
  reasoning: xhigh

deepseek-v4-flash-0731-xhigh
  model: DeepSeek V4 Flash 0731
  provider: OpenRouter
  auth: OPENROUTER_API_KEY
  reasoning: xhigh
```

Resolve and record the exact provider/model identifiers accepted by Pi. Fail instead of silently changing the requested model, provider, or reasoning level.

Model support must be additive. Adding another model or reasoning level must mean adding a new profile, not changing runner code or mutating an existing profile. Every experiment must record the requested profile and its fully resolved model configuration.

Keep OAuth state and API keys outside the repository and out of artifacts.

## Arms

Within the same task and model profile, keep prompts, task files, Pi configuration, budgets, timeout, simulator environment, and verifier identical except for the treatment described below.

### `baseline`

- Pi plus `pi-subagents`;
- no WavePeek binary;
- no WavePeek skill or documentation;
- no WavePeek-specific instruction.

The baseline may use any ordinary tools available in the common environment.

### `wavepeek@<sha>`

- the identical setup;
- WavePeek built from one exact commit SHA;
- the WavePeek skill and embedded documentation from that same build;
- one fixed generic instruction requiring WavePeek use.

Use this instruction, or wording with exactly the same meaning:

> Use the installed WavePeek skill and CLI to inspect waveform behavior while solving this task. You must run WavePeek meaningfully against a task waveform before finalizing the solution.

Do not provide task-specific hints, signal names, expected causes, suggested commands, or precomputed output. The harness must not run WavePeek for the model.

A version, help, or skill-printing command alone is not compliant. At least one command must open and query a task waveform.

If a treatment trial does not do this, keep the trial and its CVDP result, mark it `treatment_compliant: false`, and do not automatically rerun it. Natural skill discovery is out of scope for this goal.

## WavePeek revisions

Every treatment variant must resolve to an immutable WavePeek commit SHA before any trial starts.

The run interface may accept a SHA, tag, branch, or clean local checkout. Support committed local development branches without requiring them to be published. Reject dirty, uncommitted worktrees.

Build the binary from the resolved commit and materialize the skill from the same build, preferably with `wavepeek skill`. Never mix binary, skill, or documentation from different revisions.

Record the requested source, resolved commit SHA, `wavepeek --version`, binary SHA-256, and skill SHA-256. Multiple selected WavePeek revisions must appear as separate treatment variants such as `wavepeek@a27a96b`.

## Run interface

Provide one documented non-interactive entry point built on Harbor. A short script or generated Harbor job configuration is sufficient.

It must select:

- one, several, or all tasks from `selected.jsonl`;
- one, several, or all model profiles;
- baseline, one or more WavePeek revisions, or both;
- any positive attempt count, including 1, 3, and 5;
- an experiment name;
- Harbor timeout and concurrency settings when needed.

Without code changes it must support, among other combinations:

```text
one task × one model × one arm × one attempt
one task × one model × both arms × three or five attempts
several or all tasks × one model × both arms
all tasks × all models × both arms
one selection × several WavePeek SHAs
```

Each invocation creates a new dated experiment ID and resolved manifest. Never overwrite an old experiment. Preserve raw attempt-level outcomes rather than only Pass@k aggregates.

## Results and WavePeek usage

Use Harbor's normal job and trial artifacts wherever possible. For every trial preserve:

- objective CVDP pass/fail and verifier output;
- final patch or diff;
- main and subagent trajectories;
- final agent response;
- resolved model and reasoning configuration;
- timestamps, wall time, tokens, cache usage, and reported cost when available;
- setup, provider, timeout, and infrastructure errors;
- relevant repository and tool revisions.

Add the smallest transparent wrapper needed to audit WavePeek calls without changing arguments, stdout, stderr, or exit status. The resulting data must show how often WavePeek was called, which subcommands were used, which waveform files were queried, which calls succeeded or failed, when the first call occurred, and total time spent in WavePeek.

For every experiment produce a compact machine-readable summary and a short human analysis comparing pass/fail outcomes, treatment compliance, WavePeek usage, time, tokens/cost when available, and important trajectory differences. Do not invent monetary cost for subscription-backed OAuth runs when none is reported.

## Append-only journal

Maintain a version-controlled append-only journal with a simple dated layout, for example:

```text
EXPERIMENTS.md
experiments/<UTC timestamp>-<slug>/
  manifest.json
  summary.json
  analysis.md
```

Each experiment entry must record its purpose, task/model/arm/attempt selection, WavePeek SHA or SHAs, compact results, trajectory observations, conclusions, and paths to the raw Harbor job artifacts.

Never rewrite an old record after a rerun or changed interpretation. Add a new experiment or a dated correction. Commit manifests, summaries, and analyses. Keep large raw Harbor jobs and trajectories in stable dated local directories ignored by Git.

## First smoke experiment

Run exactly four trials:

```text
task:     cvdp_agentic_axis_broadcaster_0001
models:   gpt-5.6-luna-xhigh
          deepseek-v4-flash-0731-xhigh
arms:     baseline
          wavepeek@<selected WavePeek SHA>
attempts: 1
```

Run them unattended from clean isolated workspaces.

The smoke experiment is complete only when:

- all four trials are accounted for;
- both profiles used the exact requested model and `xhigh` reasoning without fallback;
- baseline trials had no WavePeek binary, skill, or instruction;
- both treatment trials made at least one compliant WavePeek query against a task waveform;
- the CVDP verifier ran for every trial;
- patches, trajectories, usage, verifier output, and WavePeek audit data were preserved;
- a dated manifest, summary, analysis, and journal entry were created.

Report the outcomes, but do not treat four trials as evidence for or against WavePeek effectiveness. This smoke validates the research workspace and treatment wiring.

## Constraints

Keep the implementation local-first and direct.

Do not create new tasks, expose hidden answers, build a custom evaluation platform, add natural-activation or ablation arms, or tune the setup separately for individual tasks or models.

Do not silently retry agent failures, timeouts, treatment noncompliance, or verifier failures. Retry only clear infrastructure failures unrelated to agent behavior, and record both the original failure and the retry.

Prefer configuration and short scripts over reusable abstractions. Add an abstraction only after more than one required path needs it.

## Done when

A clean checkout plus external credentials can reproduce the smoke experiment and launch any requested subset of the frozen task/model/arm/attempt/WavePeek-revision matrix through Harbor.

It must be straightforward to select a committed WavePeek branch, run an experiment, inspect objective results and complete trajectories, quantify WavePeek use, and append a dated research record without changing the experiment machinery.
