# Practical Use of WavePeek by Agents: A Complete Tool Call Analysis

Analysis date: 2026-08-10

## Executive Summary

In the main corpus, the three profiles performed **2,384 audited runs of the WavePeek binary** in **1,827 shell tool calls** across 162 treatment trials. Luna made two additional calls directly through `/opt/wavepeek/bin/wavepeek.real` after discovering a defect in the experimental wrapper, so the actual number of runs in the main corpus is at least 2,386. Clarification runs add another 101 audited calls, but they are not included in the headline metrics because they were executed with different limits and for only two tasks.

Practical usage was not chaotic. Nearly all models followed the same basic path:

1. read top-level help;
2. run `info`;
3. inspect `scope`;
4. find signals via `signal`;
5. run clocked `change`, less often `value` or `extract generic`;
6. repeat the query after the patch.

The basic CLI decomposition therefore works. The problems are concentrated not in selecting the first step, but in four transitions:

- from discovery output to copyable names for the next command;
- from “I want a table for every clock edge” to `change` semantics, which suppress unchanged rows;
- from potentially large JSON to compact agent-friendly output;
- from the repository/simulator to a stable and known waveform path.

The main conclusion:

> **The primary friction lies at command boundaries and around WavePeek, not in the speed or basic reliability of the core.**

All 66 core errors were subsequently worked around within the same trial. The median recovery cost was one subsequent invocation. However, 62.1% of core errors concern name resolution, and 39 of the 41 such errors were preceded by a successful `signal`, while 40 of 41 were preceded by successful `info` and `scope` calls. This means that the models mostly follow the correct discovery workflow, but the CLI does not give them an unambiguous query token that works consistently.

## Corpus and Units of Measurement

Main corpus:

- Luna xhigh: 54 treatment trials, 1,026 audited invocations;
- Terra xhigh: 54 treatment trials, 716 invocations;
- Sol high: 54 treatment trials, 642 invocations;
- total: 162 trials and 2,384 invocations.

A single shell tool call could contain several sequential WavePeek calls. The report therefore distinguishes between:

- **binary invocation** — one audit log entry;
- **shell tool call** — one bash call by the agent, possibly containing multiple commands;
- **trial** — one independent attempt by a model to solve one task on the WavePeek branch.

The analysis covers argv, exit status, duration, commands and complete tool output, diagnostics, repetitions, waveform acquisition, external JSON post-processing, and call positions in the trajectory. Errors are divided into three layers:

1. WavePeek core;
2. experimental audit wrapper;
3. agent/environment post-processing logic.

This distinction is fundamental: wrapper errors must not be turned into product feedback for the WavePeek core.

## What Actual Usage Looked Like

### Command Distribution

| Family | Luna | Terra | Sol | Total |
|---|---:|---:|---:|---:|
| `help` | 237 | 229 | 192 | 658 |
| `info` | 132 | 105 | 102 | 339 |
| `change` | 156 | 80 | 89 | 325 |
| `signal` | 132 | 87 | 78 | 297 |
| `value` | 106 | 82 | 23 | 211 |
| `extract generic` | 62 | 55 | 76 | 193 |
| `scope` | 71 | 60 | 50 | 181 |
| top-level help/version | 50 | 15 | 20 | 85 |
| `property` | 38 | 2 | 8 | 48 |
| `extract axistream` | 25 | 0 | 0 | 25 |
| `docs` | 17 | 1 | 4 | 22 |

No model used:

- actual `extract apb`;
- `--source`;
- `--include`;
- `--jsonl`;
- `schema`.

Two models read `extract apb` help, but switched to `extract generic`. All 25 uses of `--map` were in Luna's AXI-Stream calls.

### Canonical Trajectory

Before the first substantive query:

| Successful discovery before first analysis command | Luna | Terra | Sol |
|---|---:|---:|---:|
| `info` | 100% | 100% | 98.1% |
| `scope` | 100% | 100% | 88.9% |
| `signal` | 98.1% | 98.1% | 90.7% |
| help/docs | 100% | 100% | 98.1% |

In other words, the models were not “poking at the CLI blindly.” Problems arose after correct discovery.

In 100 of the 161 classified trials, the first analysis command was `change`:

- Luna: 36;
- Terra: 26;
- Sol: 38.

This is 62.1% of all trials with a substantive query. Almost every `change` was clocked: 156/156 for Luna, 80/80 for Terra, and 88/89 for Sol used `--on`.

The models' practical mental model therefore looks like this:

> “I need a cycle table → `change --on posedge clk --signals ...`.”

But `change` is not a complete cycle table: it removes selected edges if none of the output values changed. The skill explains this, but the command name and available surface still pull models toward this usage.

## Friction No. 1: Help Discipline Creates One-Third of All Invocations

In total, 765 of 2,384 invocations — **32.1%** — were `help`, `docs`, or top-level help.

| Profile | Helper invocations | Share | Median per trial |
|---|---:|---:|---:|
| Luna | 304 | 29.6% | 5 |
| Terra | 245 | 34.2% | 5 |
| Sol | 216 | 33.6% | 4 |

Top-level help was read in:

- 50/54 Luna trials;
- 15/54 Terra trials;
- 20/54 Sol trials.

Help/docs-only shell calls produced 617,587 characters of tool output for Luna, 410,339 for Terra, and 445,339 for Sol — from 22.2% to 28.5% of all WavePeek-related tool output. Individual embedded docs produced 31–39 thousand characters.

This is not merely spontaneous model uncertainty. The current skill explicitly requires:

> Before using any command in a nontrivial way, read `wavepeek help <command>`…

Consequently, much of the helper tax is **policy-induced overhead**.

### What to Change in the Skill

Remove the blanket requirement. Replace it with:

- do not read top-level help if `wavepeek` is already available;
- read command help only for the first unknown flag, after an error, or for a specialized protocol adapter;
- after the first successful invocation, reuse the already verified form;
- do not load full docs if brief help is sufficient;
- explicitly stop WavePeek exploration once the specific diagnostic question has been answered.

One short canonical recipe in the skill will provide more value than mandatory progressive disclosure before every action.

## Friction No. 2: Name Resolution Is Inconsistent Across Commands

### Error Pattern

Of the 66 core failures:

| Category | Luna | Terra | Sol | Total |
|---|---:|---:|---:|---:|
| Signal/hierarchy mismatch | 25 | 4 | 3 | 32 |
| Waveform path not found | 9 | 4 | 0 | 13 |
| Time outside bounds | 6 | 2 | 1 | 9 |
| Scoped/canonical conflict | 1 | 3 | 1 | 5 |
| Unknown signal in expression/trigger | 3 | 0 | 1 | 4 |
| Expression parse error | 0 | 0 | 2 | 2 |
| Broken pipe/EPIPE | 0 | 1 | 0 | 1 |

The three naming categories account for 41/66, or **62.1% of core failures**.

The critical fact is that naming failures did not occur because the agent failed to inspect the hierarchy:

- 39/41 were preceded by a successful `signal`;
- 40/41 were preceded by a successful `scope`;
- 40/41 were preceded by a successful `info`;
- all 41 were preceded by help/docs.

### Why Discovery Output Is Insufficient

`signal --scope tb --recursive` returns, for example:

```json
{"name":"out_valid_o","path":"tb_fifo_buffer.out_valid_o"}
{"name":"out_valid_o","path":"tb_fifo_buffer.dut.out_valid_o"}
```

With a scope selected, the agent needs the copyable relative token `dut.out_valid_o`, but the JSON contains only the basename `name` and canonical `path`. The basename is ambiguous, while according to the skill the canonical path cannot be combined with a scope.

The model naturally derives `dut.out_valid_o`. This is where the inconsistency appears:

- scoped `value --signals dut.foo` worked in 11 of 12 observed calls;
- scoped `change` with descendant-relative names produced 19/19 failures;
- scoped `extract generic` with dotted descendant payload produced 6/6 failures;
- there was not a single successful scoped `extract generic` call with `dut.foo`.

TMDS is especially illustrative:

- `value --scope tb --signals D,q_out,dut.q_m,dut.cnt_prev` — successful;
- `extract generic --scope tb --payload D,q_out,dut.q_m,dut.cnt_prev` — fatal: payload must be relative.

But `dut.q_m` is already a relative path from `tb`.

### Required CLI Change

This is the highest-priority product change:

1. All commands must use one signal resolver.
2. `--scope` must define the namespace root rather than restricting names to immediate children only.
3. Descendant-relative paths such as `dut.foo` and `steps[0].RotWord` must work consistently in `value`, `change`, `property`, `--on`, `--eval`, `--when`, and `--payload`.
4. An exact canonical path can safely be accepted with a scope as well, normalizing it if it lies under the selected root.
5. `signal --scope` must add the field:

```json
{
  "name": "out_valid_o",
  "path": "tb_fifo_buffer.dut.out_valid_o",
  "relative_path": "dut.out_valid_o"
}
```

6. A fatal error must print copyable candidates, not merely `not found`:

```text
signal 'dut.victimway' not found for change
closest query names under scope tb_assoc:
  victimway
  dut.victim_way
```

7. When a signal is genuinely absent from the dump, the message must distinguish that from an invalid path: “no dumped signal with this basename; RTL declaration may be optimized, aliased, or not dumped.”

Changing only the skill is insufficient here: the models already followed the recommended discovery process, while different commands accepted different name forms.

## Friction No. 3: Waveform Acquisition Is a Separate Workflow

In 62 of 162 trials — **38.3%** — the models added `$dumpfile/$dumpvars` themselves, created a temporary testbench/wrapper, or otherwise instrumented the simulation.

| Profile | Trials with instrumentation | Tool calls |
|---|---:|---:|
| Luna | 21/54 | 39 |
| Terra | 20/54 | 26 |
| Sol | 21/54 | 29 |

This share is virtually identical across all grades. A typical flow was:

1. find the testbench;
2. copy or rewrite it to a temporary file;
3. add `$dumpfile` and `$dumpvars`;
4. determine the compile list/top;
5. run Icarus;
6. find the generated file;
7. separately generate before/after dumps.

13 core failures were simply incorrect paths: a guessed `/app/verif/...`, a temporary file in a different directory, or relative `test.vcd` after the cwd changed.

### Conclusion

For CLI evaluation, this is a serious confounder: the experiment measures not only WavePeek, but also the model's ability to materialize a waveform.

### Minimal Harness Fix

Do not add simulator orchestration to the WavePeek core. It is enough to:

- materialize the baseline waveform in advance;
- pass an absolute path through `WAVEPEEK_WAVES` or a small manifest;
- preserve separate paths for before/after;
- record simulator, dump format, mtime/hash;
- guarantee that the relevant hierarchy is actually dumped.

`wavepeek capture` can be considered later, but it is excessive for the next evaluation. The cheapest and cleanest step is a standardized waveform manifest.

## Friction No. 4: Explicit Full-Range Policy Produces Bounds Errors

There were nine strict bounds failures. Most were small rounded overshoots:

- `90ns` with `time_end=80000ps`;
- `50ns` with `46000ps`;
- `120ns` with `117000ps`;
- `165ns` with `150000ps`;
- `274s` with `270s`;
- `450s` with `435500ps`.

CLI help already defines:

- omitted `--from` = dump start;
- omitted `--to` = dump end.

But the skill requires the covered interval to be explicit and verification that `time_end` is reached. The models therefore copy or round bounds manually and occasionally get them wrong.

### Minimal Fix

In the skill:

- when the full dump is needed, **do not specify `--from/--to`**;
- specify a range only for intentional narrowing;
- do not round `time_end`.

Optional CLI improvement:

```text
--from start --to end
```

Clamping arbitrary overshoot by default is undesirable: it may hide a genuine unit error. Symbolic bounds are safer.

The current errors themselves are good: they show exact dump bounds and command help, so recovery usually takes one call.

## Friction No. 5: No Direct “Table at Every Edge” Primitive

`change` was used as a cycle table even though its semantics are sparse. The skill contains the correct warning, but model behavior shows that documentation is not enough.

Current possible workarounds:

- manually enumerate timestamps in `value --at`;
- `extract generic --when 1 --payload ...`;
- use `change` while accepting suppression of identical rows;
- `--on '*' --sample-mode native`, which already has different semantics.

All workarounds are worse than a direct query.

### Proposed Surface

Add one simple primitive:

```text
wavepeek sample   --waves dump.vcd   --scope tb.dut   --on 'posedge clk'   --signals state,valid,ready,data   --max 50   --json
```

`sample` must emit **every selected event**, even when the values are identical. `change` remains a sparse transition primitive.

In addition, `--row-values full|delta` would be useful for `change`, so that delta mode does not repeat unchanged wide values in every row.

This change matches the models' actual request better than further expansion of the `change` documentation.

## Friction No. 6: Large Responses and Repeated Reading of Wide Buses

127 shell tool calls in 77 trials produced more than 10 thousand characters. 24 calls exceeded 20 thousand.

Maximums:

- 43,567 characters — Sol, FIFO `change`;
- 42,687 — Luna, AES `expanded_key_ff`;
- 38,826 — Luna, two embedded reference topics;
- 33–34 thousand — AES wide state and expression docs.

The problem is not only the number of rows. `change` prints a full snapshot of the requested signals in every emitted row. Consequently, a 1,408/1,920-bit key schedule is repeated many times even when the agent only needs a round/state transition.

### What to Add

High priority:

- `--summary`: row count, first/last time, truncation, diagnostics;
- `--count`: for `property`/`extract`;
- `--row-values delta`: changed fields only;
- ability to select a slice of a wide signal in the output;
- `returned`, `matched_total`, `truncated` in the envelope.

Medium priority:

- `--signals-file`/response file for long lists;
- reusable query spec for before/after;
- compact rendering of wide values: width + prefix/suffix/hash behind an explicit flag.

`--jsonl` already exists, but no model used it. The mere existence of a streaming format does not solve the agent-context problem: the agent needs a built-in summary or a recommended redirection/post-processing pattern.

## Friction No. 7: JSON Post-Processing Has No Short Blessed Path

JSON was used almost everywhere:

- Luna: 97.2% of data invocations;
- Terra: 99.6%;
- Sol: 98.6%.

This is a strength of the skill.

But for large results, models created their own handlers:

| Profile | Redirect to JSON file | Python `json.load` calls |
|---|---:|---:|
| Luna | 5 | 5 |
| Terra | 5 | 8 |
| Sol | 15 | 18 |

Sol redirected output to a file and printed a compact summary more often than the others. This reduced visible tool output and was the most mature observed pattern.

Problems:

- `jq` was absent from the environment; three shell calls failed;
- one agent expected `data.rows`, but for row commands `data` is the list itself, and received `AttributeError`;
- no model called `wavepeek schema`, even though the skill recommends it for exact parsing.

### Skill Change

Do not assume `jq` is available. Provide one copyable Python recipe:

```python
import json

result = json.load(open("wavepeek.json"))
print("diagnostics:", result.get("diagnostics", []))
data = result["data"]

if isinstance(data, list):
    print("rows:", len(data))
    print("first:", data[:3])
    print("last:", data[-3:])
else:
    print(data)
```

And state explicitly:

- `info.data` is an object;
- row-producing commands usually return a list;
- inspect `diagnostics`;
- for large results, redirect and then print only count/first/last.

An additive top-level `summary` will reduce dependence on command-specific shapes without a breaking schema change.

## Friction No. 8: Diagnostics Too Often Report Intentional Behavior

A total of 265 diagnostics were observed:

| Code | Meaning | Count |
|---|---|---:|
| WPK-W0001 | limit disabled | 178 |
| WPK-W0002 | output truncated | 54 |
| WPK-W0003 | empty result | 33 |

WPK-W0001:

- `--max=unlimited`: 166;
- `--max-depth=unlimited`: 12.

But `unlimited` was explicitly selected by the user. The warning does not report an unexpected state and creates mandatory “inspect diagnostics” work.

WPK-W0003 mixes different cases:

- no extract rows — 14;
- no signals under scope — 12;
- no property matches — 5;
- no changes — 2.

“No property matches after the fix” may be desired evidence. “No signals” is a discovery failure. One warning code should not represent both meanings.

WPK-W0001 + WPK-W0003 account for 79.6% of all diagnostics.

### Proposed Change

- Explicit `unlimited` should not be a warning. Metadata `limit:null` is sufficient.
- Keep truncation WPK-W0002 as a warning; it genuinely affects correctness.
- Keep empty signal discovery as a warning.
- Represent zero property/extract/change rows as a normal summary or `info`, not a warning.
- Add command-specific count metadata.

## Friction No. 9: Expression Diagnostics Point to the Wrong Error

Two Sol expressions produced:

```text
EXPR-PARSE-LOGICAL-UNMATCHED-OPEN
```

Although the parentheses in the strings were balanced:

```text
o_done && (o_data == 0x001122...)
clint_cpu_mt_int == (sysio_clint_mtime >= 64h10)
```

The actual problem is most likely the literal syntax:

- SV-like `128'h...` is supported;
- `0x...` is not a documented form;
- `64h10` omits the `'`.

### Changes

- The parser diagnostic must identify the offset/token and print a caret.
- For an unknown literal, report the expected forms.
- Add one hex example to the compact skill: `64'h10`, `128'h0011...`.
- Do not require the agent to load the 31K expression reference for such a correction.

## Friction No. 10: Broken Pipe Turns into a Rust Panic

One Terra call ran:

```text
wavepeek extract generic ... --json | jq ...
```

`jq` was absent, the downstream pipe closed, and WavePeek printed a Rust panic:

```text
failed printing to stdout: Broken pipe (os error 32)
```

This is a core defect. A Unix CLI must exit without a backtrace on EPIPE. Fix:

- handle `std::io::ErrorKind::BrokenPipe`;
- do not use a panic-producing stdout path for normal pipe closure;
- add a regression test with `wavepeek ... | head -n 0` or a closed consumer.

The missing `jq` remains an environment/agent error, but WavePeek should not amplify it with panic output.

## Separately: Defect in the Experimental Audit Wrapper

There were 28 tool failures:

```text
OSError: [Errno 36] File name too long
```

Distribution:

- Luna: 24 in 13 trials;
- Terra: 3 in 3;
- Sol: 1 in 1.

The wrapper iterated over arbitrary argv values as `Path` objects and called `.exists()`. A long `--signals` or `--eval` string was interpreted as a file name. By that point the core had often already printed valid JSON successfully, after which the wrapper appended a traceback and returned exit 1.

This is **not a WavePeek core problem**. But it is an important result for the evaluation harness:

- the wrapper must parse only explicit file flags (`--waves`, `--source`);
- `Path.exists()` must be protected against `OSError`;
- the audit must preserve core stdout/stderr separately;
- the wrapper must not change the exit status after a successful core call because of its own telemetry;
- a long-argv regression is mandatory.

Luna read the wrapper source once and called `.real` directly twice to continue working. These two invocations are absent from the audit log.

Until the wrapper is fixed, it is impossible to fairly compare “CLI error rates” across grades: Luna used long lists more often and therefore suffered disproportionately from the instrumentation defect.

If the 66 core failures and 28 wrapper failures are combined, the visible friction rate is:

- Luna: 6.6% of invocations;
- Terra: 2.4%;
- Sol: 1.4%;
- total: 3.9%.

But the product core rate is only 2.77%.

## How Much Errors Hindered the Agent

All 66 core failures were recovered within the same trial.

| Profile | Core failures | Recovered | Recovery on next invocation | Median gap to same-family success |
|---|---:|---:|---:|---:|
| Luna | 44 | 44 | 30 | 2.5 |
| Terra | 14 | 14 | 11 | 1.5 |
| Sol | 8 | 8 | 6 | 1.5 |

This is a good sign:

- fatal messages are usually sufficiently specific;
- discovery commands are available;
- the CLI does not lead the trajectory into a dead end.

But “all errors were recovered” does not mean the UX is good. A retry adds a call, new output, and another pass over the context. Here, friction manifests primarily as cost rather than terminal failure.

## Repeated Work

Exact duplicate extra invocations:

- Luna: 81, or 7.9%;
- Terra: 35, or 4.9%;
- Sol: 27, or 4.2%;
- total: 143, or 6.0%.

Repeated `info` for the same path:

- Luna: 43 extra;
- Terra: 21;
- Sol: 17.

Some repetitions are justified: the same path was overwritten with the after-fix waveform. But the CLI does not help distinguish a new file from one already inspected.

Useful additive fields for `info`:

- file size;
- mtime;
- lightweight content fingerprint;
- format/backend;
- signal/scope counts.

A reusable query spec or `wavepeek diff` could be added later for the before/after workflow, but this is lower priority than the resolver and compact output.

## Use of Protocol Adapters

### AXI-Stream

Only Luna actually used `extract axistream`: 25 calls in two trials. The broadcaster task had four interfaces: one input and three outputs. For each interface, the model repeated:

- profile;
- clock;
- valid;
- ready;
- data;
- name;
- time window.

It then repeated mappings for the fixed/final/tail waveform. One trial accumulated 27 WavePeek invocations.

Terra and Sol used `extract generic` because one-line `--when valid && ready --payload ...` is cheaper.

### APB

Luna and Sol read `extract apb` help, but made no actual call. The interconnect used bespoke master/slave names, and the mapping/adapter fit offered no obvious advantage over generic extraction.

### Conclusion

The main skill should not be expanded with an even larger catalog of adapters. What is needed is either:

- automatic mapping detection by prefix;
- a multi-interface spec;
- an explicit compare/alignment operation;
- or a default route to `extract generic` when a protocol adapter does not save actions.

A low-priority idea for AXI-Stream:

```text
wavepeek extract axistream   --interface input=s_axis   --interface out1=m_axis_1   --interface out2=m_axis_2   --interface out3=m_axis_3
```

But the general surface should be fixed first; adapters are not the main bottleneck in the corpus.

## Differences Between Models

The types of problems are the same across all three profiles. Grade changes frequency and style, but does not create a new class of usage.

### Luna xhigh

- 1,026 invocations, median 18.5 per trial;
- 44 core failures;
- 47 recursive signal searches in 25 trials;
- 38 `property`, 106 `value`;
- the only model that used `extract axistream`;
- 12 trials with full docs;
- the largest share of exact duplicates.

Luna is the most exploratory. It descends into the hierarchy more often, tries advanced surface features, and repeats before/after queries. It therefore both finds more CLI edge cases and suffers more from the wrapper on long argv values.

### Terra xhigh

- 716 invocations, median 13;
- 14 core failures;
- only three recursive signal searches;
- 82 `value`, 55 generic extracts;
- help share 34.2%.

Terra more often groups several WavePeek invocations into one bash call. This reduces agent tool turns, but not necessarily the number of CLI operations. Concatenating multiple JSON envelopes also complicates automatic parsing and error attribution.

### Sol high

- 642 invocations, median 12;
- 8 core failures;
- 76 generic extracts, only 23 `value`;
- redirects JSON and prints a Python summary more often;
- does not use specialist adapters;
- two expression literal errors.

Sol limits exploration most effectively and more often turns WavePeek into targeted extraction. But meaningful-call yield in the previous comparison remained almost the same as for the other profiles: grade improves stopping and post-processing, but does not eliminate CLI ambiguities.

### Overall Cross-Model Conclusion

The same patterns recur:

- mandatory help;
- `info/scope/signal`;
- `change` as a cycle table;
- guessed descendant names;
- explicit rounded bounds;
- before/after repetition;
- external JSON summary.

This means that improvements to the resolver, skill, and output surface should transfer across models rather than being Luna-specific tuning.

## Where Everything Worked Smoothly

### Sol — Direct-Map Cache, 6 Invocations

```text
help info
help signal
help change
info
signal
change
```

No core/wrapper errors. The dump existed, the scope was short, the signals were directly in the DUT scope, and the query was single and focused.

### Terra — Dual-Port Memory, 9 Invocations

After `info/scope/signal`, the model used two `value` calls at selected timestamps. There were no errors or diagnostics. The main friction occurred only before WavePeek, while creating the dump.

### Sol — OpenE902 CLINT, 8 Invocations

`info/scope/signal/change` on the buggy waveform, followed by `info/change` on the fixed waveform. No errors or diagnostics. This is a good reference before/after workflow.

### Luna — LFSR, 11 Invocations

`info/scope/signal/change/value`, followed by repetition after the patch. No core errors in the selected trial. Even here there were several helper calls, so the skill tax remains, but the CLI model itself behaved predictably.

### Common Properties of Smooth Cases

- the waveform path is already known or stable;
- the hierarchy is shallow;
- a scope is selected in which clock and payload are colocated;
- the signal list is short and contains no descendant-relative paths;
- there are no wide arrays;
- the question can be answered with one primitive;
- the after-fix query repeats an already verified command.

## Breakdown by Task

| Task | Observation |
|---|---|
| `AES_encryption_decryption_0003` | Deep generate scopes `steps[N]`, a parent clock, and a wide key schedule. Errors occurred while attempting to combine `clk` from the parent with `steps[0].*` inside a narrow scope; one point at `274s` exceeded the `270s` end. `value` with descendant-relative names sometimes worked, whereas `change` with the same forms did not. |
| `AES_encryption_decryption_0005` | The main friction involved internal key expansion names absent or renamed in the dump, wide `change` rows, and six audit-wrapper defect triggers for Luna on long signal lists. The waveform already existed, so there was no acquisition friction. |
| `AES_encryption_decryption_0009` | Wide `expanded_key_*` signals produced the largest responses; two failures were caused by relative `test.vcd` after the cwd changed. This is a good example of the need for a stable absolute path and compact representation of wide buses. |
| `AES_encryption_decryption_0012` | Sol used a balanced expression, but the C-style literal `0x...` did not match the documented SV-like grammar. The diagnostic reported `unmatched opening parenthesis`, thus pointing away from the actual cause. An example `128'h...` and a caret/token diagnostic are needed. |
| `axis_broadcaster_0001` | The only task in which `extract axistream` was actually used, and only by Luna: 25 calls in two trials. Mapping for the input and three outputs was repeated separately before and after the patch. Terra and Sol preferred `extract generic`; this indicates high mapping boilerplate and the absence of multi-interface comparison. |
| `custom_fifo_0004` | In 7/9 trials, the models added `$dumpfile/$dumpvars` themselves. A deep generated hierarchy produced identical basenames at the TB and DUT levels. Large cycle tables and attempts at external JSON parsing were observed; Sol also encountered missing `jq` after WavePeek had already produced successful output. |
| `direct_map_cache_0003` | One of the smoothest classes: an existing dump, short hierarchy, focused signals. The only core error was `dut.victimway` in scoped `change`, although similar descendant-relative forms work in `value`. This is a clean minimal reproduction of the inconsistent resolver. |
| `dual_port_memory_0001` | No core or wrapper errors in all nine trials. In 7/9 trials, a dump had to be created, after which `info/scope/signal/value/change` worked predictably. This is the best positive control for the basic CLI model. |
| `heavy_2dconv-FPGA_0009` | The worst task for core naming friction: nine errors. The models searched for RTL registers `parcial0`, `resultado`, and `conv_reg`, but some internal arrays and names were absent or represented differently in the VCD. Nearest-name suggestions and an explicit distinction between “not dumped/optimized away” and “invalid path” are required. |
| `heavy_I2SRV64_0001` | TB request signals and internal DUT state signals are mixed. The parent scope naturally requires names such as `dut.arbiter_busy`, but `extract generic` rejects them, while long canonical lists broke the audit wrapper. This is the strongest end-to-end argument for one descendant-relative resolver and `relative_path` in discovery. |
| `heavy_ULX3S_FPGA_Camera_Streaming_0005` | `dut.q_m` and `dut.cnt_prev` were successfully read through scoped `value`, but rejected by scoped `extract generic`/`change`. There was also a small overshoot of `120ns` against `117000ps`. The task clearly demonstrates both naming inconsistency and pre-edge/cycle inspection friction. |
| `heavy_friscv_0001` | Two models read `extract apb` help, but neither called the adapter: bespoke naming and mapping cost made `extract generic` simpler. In 6/9 trials, the dump was created manually. This is a signal not to expand the protocol surface in the main skill without auto-mapping or clear savings. |
| `heavy_friscv_0005` | Errors involved paths to before/after dumps and descendant internal counters. One Sol `change` produced 43,567 characters — the corpus maximum — because of the full snapshot in every row. An edge sampler with bounded rows and a delta/compact value mode are needed. |
| `heavy_opene902_0057` | After manual dump setup, the basic before/after workflow was often smooth. Friction included incorrect temporary paths, Luna's long lists, and a misleading parse error for `64h10`. This is a good candidate for an expression-diagnostics regression test. |
| `heavy_opene902_0059` | The most varied friction: scoped payload `dut.*`, missing `jq`, Rust panic on EPIPE, audit-wrapper ENAMETOOLONG, and a subsequent deliberate wrapper bypass via two direct `.real` calls. It should become an integration regression fixture. |
| `heavy_opene902_0071` | Incorrect before/after paths and a trigger name outside the selected DUT scope predominated. Models often switched between `change`, `value`, and `property`. A copyable query name and a simpler way to reference a parent clock from a common scope are needed. |
| `lfsr_0001` | The cleanest existing-waveform case: short hierarchy, several signals, `value/change`, and almost no errors. The only error was an attempt to request both a TB alias and `dut.lfsr_out` in scoped `change`. Suitable as a UX smoke test. |
| `monte_carlo_0006` | `extract generic` was used for CDC/event counting, but the models aggregated JSON manually. Four bounds errors, one invalid internal name, and one Python `AttributeError` occurred because the agent expected `data.rows`, while `data` is a list. `--count/--summary` and an exact parsing recipe are needed. |

## Prioritized Backlog

### P0 — Fix Before the Next Evaluation

#### H0. Audit Wrapper: Do Not Treat Arbitrary argv Values as Paths

Evidence: 28 ENAMETOOLONG errors, valid core JSON before the traceback, two direct bypasses.

Acceptance:

- long `--signals`, `--eval`, and `--payload` values do not trigger filesystem stat;
- the wrapper returns the core exit status;
- stdout/stderr are preserved independently;
- telemetry failure does not break the task command.

#### C0. Unified Signal Resolver for All Commands

Evidence: 41 naming failures; scoped `value` accepts descendants, while `change` and `extract generic` do not.

Acceptance:

- the same `relative_path` works in `value/change/property/extract`;
- expressions and payload use the same resolver;
- parent scope + child DUT signal is a standard case;
- errors show candidates.

#### C1. Handle EPIPE Cleanly

Evidence: Rust panic when `jq` was absent.

Acceptance:

- a closed stdout consumer does not print a panic/backtrace;
- predictable Unix exit behavior;
- regression test with an early-closing pipe.

#### S0. Remove the Mandatory-Help Policy

Evidence: 765 helper invocations, 22–28.5% of tool output.

Acceptance:

- top-level help is not mandatory;
- command help is used only in cases of uncertainty/error;
- the main skill contains a short recipe and stop rule.

### P1 — Maximum Expected Impact

#### C2. `relative_path`/`query_name` in `signal` Output

Discovery must return not only the canonical `path`, but also a string that can be inserted into the next command with the current scope.

#### C3. First-Class `sample` at Every Edge

Eliminates the systematic use of sparse `change` as a cycle table.

#### C4. `--summary`, `--count`, `returned/matched_total/truncated`

Reduces large responses and the need for Python/jq.

#### C5. Delta Rows and Compact Wide Values

Reduces 20–43K responses for AES/FIFO.

#### S1. Omit Bounds for the Full Dump

Eliminates most of the nine bounds failures without changing the core.

#### S2. Blessed JSON Post-Processing Recipe

Python, with no `jq` dependency and correct differentiation between object/list `data`.

#### D0. Reclassify Diagnostics

Explicit unlimited — metadata; zero semantic matches — normal summary; truncation — warning.

#### H1. Provide a Waveform Manifest

Eliminates the acquisition confounder and path guessing in the next evaluation.

### P2 — After Validating P0/P1

- reusable query spec for before/after;
- `--signals-file`/response files;
- multi-interface AXI-Stream extraction/comparison;
- adapter mapping discovery;
- file fingerprint in `info`;
- symbolic `start/end` bounds;
- separate `wavepeek diff`.

## What Must Not Be Broken

The data also demonstrate strengths of the current implementation:

- `info → scope → signal → value/change/extract` is an understandable decomposition;
- models almost always select the JSON envelope;
- diagnostics are in JSON rather than lost only in stderr;
- fatal errors usually contain exact bounds or the missing name;
- recovery is fast;
- the binary is very fast; core performance is not the bottleneck;
- the skill successfully kept models from reading VCD directly as text;
- `extract generic` is a robust universal primitive;
- strict out-of-bounds behavior is better than a silently incorrect result.

No major redesign or stateful REPL is needed. Several localized changes will have the greatest impact:

1. consistent name resolution;
2. copyable relative paths;
3. a separate edge sampler;
4. compact/count output;
5. a shorter skill;
6. a fixed evaluation harness.

## Minimal New Skill Flow

Before CLI changes:

```text
1. Find the absolute waveform path from the harness/manifest.
2. wavepeek info --waves "$W" --json
3. wavepeek signal --waves "$W" --scope "$S" --recursive --filter '...' --max 50 --json
4. Use the exact names returned by discovery; do not reconstruct them from RTL.
5. For each event/handshake: extract generic.
6. For transitions: change.
7. For point samples: value.
8. Full dump: do not specify --from/--to.
9. Large JSON: redirect to a file, print diagnostics + count + first/last.
10. Stop when the query has answered a question capable of changing the diagnosis or patch.
11. Read help only after an error or for an unfamiliar advanced command.
```

After adding `relative_path` and `sample`, items 4–6 become even simpler.

## Conclusion

Forced usage proved useful as a UX stress test. It showed that the WavePeek core is already fast, deterministic, and recoverable enough for agent work. But the current surface forces the agent to pay an unnecessary cost for:

- help;
- conversion between canonical/relative names;
- manual cycle-sampling semantics;
- overly complete JSON;
- waveform setup;
- external aggregation.

The most important observation is not “agents often make mistakes.” It is more precise:

> **Agents almost always perform the recommended discovery, but the discovery result is not a portable contract across commands.**

If only one product-level aspect is fixed, it should be a unified signal resolver with `relative_path`. If only one skill-level aspect is fixed, remove mandatory help and provide a short, stop-oriented recipe. If only one harness-level aspect is fixed, provide a ready absolute waveform path and remove the erroneous argv-as-path audit.
