# WavePeek command and trajectory analysis

## Scope

This report analyzes the WavePeek treatment arm of the rerun
`2026-08-12_205534Z_deepseek-xhigh-full-3x-rerun_19f0bbea`.

The corpus contains 54 treatment trials. One trial terminated at the model-provider layer before meaningful tool use, so the command analysis covers 53 trajectories and 991 recorded WavePeek process invocations. The analysis uses the retained `wavepeek-invocations.jsonl` files together with the Pi session transcripts, shell tool calls, generated waveforms, and verifier outcomes.

The focus here is command selection, query construction, shell composition, waveform-generation workflow, and the interpretation of waveform evidence. JSON-envelope parsing mistakes are noted only where they materially changed the command workflow.

## Executive findings

WavePeek was not used as a single uniform tool. The agent developed five recurring modes:

1. **Discovery:** `info -> scope -> signal`.
2. **Manual waveform microscopy:** repeated `value` queries at selected timestamps.
3. **Clocked timelines:** `change` or unconditional `extract generic --when 1`.
4. **Event and invariant checks:** `extract generic` and `property` on a clock edge.
5. **Differential/reference-model analysis:** identical queries against buggy/fixed waveforms or extracted rows checked by Python models.

The high-level routing worked well. Every one of the 53 analyzable trajectories began with `info`; 45 performed all three discovery steps `info`, `scope`, and `signal`. Discovery commands succeeded in approximately 94% of invocations.

The main friction was in the advanced event model rather than file discovery:

- 10 `change` calls omitted mandatory `--on`;
- 12 `extract generic` calls omitted mandatory `--when`;
- 13 plain-signal or wildcard triggers were used without native sampling and all failed;
- 6 attempts used the intuitive but unsupported `property --capture count` and all failed;
- 5 attempts repeated `--at` instead of supplying one comma-separated list and all failed;
- 18 queries attempted signal slices or unpacked-array paths; 15 failed;
- 11 queries supplied bare numeric times and all failed.

The dominant actual interface was not `extract`; it was `value`. Of 385 `value` calls, 337 sampled only one timestamp. Shell loops then recreated batch sampling: 42 `for` loops generated 257 WavePeek invocations. The agent knew that comma-separated timestamps were possible—it used them in 41 calls—but did not consistently choose that route.

`extract generic` was nevertheless meaningful. It was invoked 127 times:

- 34 calls used `--when 1` or `1'b1` as a cycle table;
- 53 used a single event signal such as `valid_out_b`, `DE`, `push`, `o_done`, or `DCache_Req_Valid`;
- 28 used compound predicates such as `slv_en && slv_ready`;
- 12 omitted `--when` and failed.

Protocol-specific extraction was almost absent. Only `extract apb` was tried, twice, in the APB-interconnect task. Both calls correctly failed because the exposed interface had no `PENABLE`. The agent then used `extract generic` on `slv_en && slv_ready`, which was the right fallback for that simplified APB-like interface. No AXI, AXI-Stream, AHB, or ATB extractor was invoked.

The agent wrote a large amount of auxiliary material, but almost none of it was a reusable WavePeek driver. Across the treatment sessions, shell tool calls created at least 139 distinct files through `cat`/`tee`: 75 `.sv`, 16 `.v`, 42 `.py`, one `.sh`, and several other artifacts. Most were custom testbenches, reference implementations, or one-off mathematical models. Only one reusable shell helper directly wrapped WavePeek (`/tmp/chk.sh`). There was no reusable generic query script, no `jq`, no JSONL use, and no structured `--source` document.

The strongest successful pattern was:

> generate a focused waveform -> extract one bounded row set -> check a precise invariant in Python.

The best example was the successful 2D-convolution attempt, which extracted accumulator/result state once and asserted bit-level relationships across every non-X row. The weakest pattern was:

> generate many testbench variants -> manually sample many timestamps -> repeatedly reinterpret local evidence without an explicit distinguishing invariant.

That pattern appears in the failed 2D-convolution attempt, failed AES attempts, and all three failed OpenE902 LSU-control attempts.

## Quantitative command map

| Command family | Calls | Successful process exits | Failed process exits |
|---|---:|---:|---:|
| `value` | 385 | 349 | 36 |
| `change` | 128 | 89 | 39 |
| `extract generic` | 127 | 98 | 29 |
| `signal` | 94 | 84 | 10 |
| `property` | 82 | 73 | 9 |
| `scope` | 63 | 62 | 1 |
| `info` | 62 | 60 | 2 |
| `extract apb` | 2 | 0 | 2 |
| Help, docs, version | 48 | 48 | 0 |

The important contrast is between discovery and event-oriented commands:

- `info`, `scope`, and `signal`: 206/219 successful, about 94%;
- `value`: 349/385 successful, about 91%;
- `property`: 73/82 successful, about 89%, with all six failures from the guessed `capture=count` mode plus a few malformed expressions;
- `extract generic`: 98/127 successful, about 77%;
- `change`: 89/128 successful, about 70%.

`change` is the clearest command-level friction point. Its separation between event selection (`--on`), sampling mode, and displayed signals was not reliably internalized.

## Discovery behavior

The skill’s initial routing instructions worked unusually consistently:

- first substantive command in all 53 analyzable trajectories: `info`;
- 45 trajectories used all of `info`, `scope`, and `signal`;
- five used `info` and `scope` without `signal`;
- three used `info` and `signal` without `scope`.

Common first sequences were:

- `info -> scope -> signal -> change`: 12 trajectories;
- `info -> scope -> signal -> signal`: 11;
- `info -> scope -> signal -> extract generic`: 7;
- `info -> scope -> signal -> value`: 4.

This means the agent generally did not blindly guess the waveform file or top-level scope. The recurring mistakes happened after discovery, when it constructed exact names, ranges, triggers, or payloads.

Only 18 trajectories invoked a command-specific `help` subcommand, and only two touched `docs`. Fourteen trajectories experienced at least one failed WavePeek call without ever reading help or docs. The behavioral pattern was therefore:

> discover the hierarchy correctly, then learn detailed syntax by failed invocations.

## Mode 1: manual point sampling with `value`

`value` accounted for 39% of all WavePeek invocations.

### Shape of the usage

- 337 calls: one timestamp;
- 41 calls: one `--at` containing a comma-separated timestamp list;
- 5 calls: repeated `--at` flags, all rejected;
- 2 calls omitted `--at`, relying on command defaults.

Signal-list size:

- one signal: 160 calls;
- two to five signals: 185;
- more than five signals: 37.

The agent often used `value` as a debugger’s watch window, sampling internal state before and after selected clock edges. This worked well when the decisive timestamp was already known from a log or `change` query.

### Where it was effective

- AES key schedule: checking whether a large expanded-key register was stable across rounds;
- direct-map cache: inspecting victim way, hit/tag, valid, dirty, and output state at read/write edges;
- CLINT and LSU control: comparing buggy and fixed signals at identical timestamps;
- FIFO: checking head data, valid bits, address, and error flags around a failing row;
- I2SRV64: inspecting request payload and done-pulse context.

### Where it became inefficient

The agent repeatedly used shell loops for timestamp sweeps even though `value` accepts a comma-separated time list. Examples include:

- 10–13 cache timestamps per loop for hit/tag/victim state;
- three separate nine-point AES loops for round, done, and expanded-key state;
- nine FIFO timestamps for a table reconstruction;
- eight timestamps × two waveforms for CLINT differential analysis.

The direct-map-cache task is the clearest example: one successful attempt made 64 calls, 60 of them inside loops, with almost no syntax failure. The analysis was semantically sound but operationally equivalent to manually reading a waveform viewer one cursor position at a time.

### Signal slicing as a missing primitive

Wide AES vectors created a repeated need to inspect slices such as:

- `expanded_key[127:0]`;
- `expanded_key_ff[1407:1280]`;
- symbolic slices based on parameters;
- unpacked-array elements such as `current_data_ff[0][0]`.

WavePeek currently resolves dumped signal names, not arbitrary projection expressions. Eighteen calls attempted slice/array syntax; only three happened to resolve, and 15 failed. The fallback was to retrieve an entire 1408- or 1920-bit vector and slice its printed hexadecimal value in Python. A first-class bit-slice projection would directly remove a substantial portion of AES-specific friction.

## Mode 2: timelines with `change`

`change` was used 128 times and had the highest failure rate among the common commands.

### Intended uses

The agent used it to inspect:

- FSM round/state progression;
- FIFO pointer and flag transitions;
- ready/valid/data evolution;
- cache victim-way and hit transitions;
- interrupt register and output changes;
- LFSR evolution;
- done-pulse timing.

When the selected signals were actual state variables and the event was `posedge <clock>`, this was generally appropriate.

### Main friction

Trigger categories:

- 98 edge-triggered calls; 84 succeeded;
- 16 plain-signal/expression triggers; only four succeeded;
- four wildcard triggers; only one succeeded;
- 10 calls omitted `--on`; all failed.

The model repeatedly treated `--on` as either optional or as an arbitrary Boolean condition. It tried forms such as:

- a plain signal under the default pre-edge sampler;
- `--on 1`;
- a scoped canonical path while also using `--scope`;
- a Boolean comparison rather than a clock event;
- wildcard `*` without `--sample-mode native`.

It usually recovered after the diagnostic by switching to `posedge clk` or to native sampling. The command’s diagnostics were adequate; the issue was that the distinction between an event term and an evaluated condition was not stable in the agent’s working model.

### Semantic risk

`change` emits rows only when one of the printed values changes. The agent sometimes used it as a handshake or transaction timeline. This is acceptable for visual inspection but does not prove that every repeated event occurred. In the broadcaster and FIFO tasks it usually complemented `extract generic`, but in some trajectories it was the only temporal view. A repeated transfer with identical payload could therefore be invisible.

## Mode 3: `extract generic` as a clocked dataframe

The agent used `extract generic` more as a generic synchronous table constructor than as a narrowly filtered transaction extractor.

### Query classes

| Predicate form | Calls | Successful | Failed |
|---|---:|---:|---:|
| Single event signal | 53 | 43 | 10 |
| Unconditional (`1`, `1'b1`) | 34 | 32 | 2 |
| Compound predicate | 28 | 23 | 5 |
| Missing `--when` | 12 | 0 | 12 |

Frequent event predicates included:

- `o_done`, `key_done || o_done`;
- `valid_out_b`;
- `DE` or `DE == 1`;
- `push` and `pull`;
- `DCache_Req_Valid`;
- `slv_en && slv_ready`;
- round-number conditions.

### Successful uses

#### Monte Carlo CDC

All three attempts used a compact sequence:

1. `info`;
2. `scope`;
3. `extract generic` on `posedge clk_b` when `valid_out_b`.

The payload included `data_out_b` and `cross_domain_transfer_count`. Python then checked event count and monotonic counter behavior. This was one of the most efficient WavePeek workflows in the corpus: 6–7 calls per attempt, all three attempts passed.

#### 2D convolution, successful attempt

The agent extracted every clocked row for `conv_reg`, `o_data`, `resultado`, `parcial0`, and `parcial1` into `rows.json`, then asserted across all non-X rows that:

- the sign bit of `o_data` was the inverse of the accumulator sign bit;
- lower result bits matched;
- the final accumulator decoded to the expected signed value.

This is the strongest trajectory in the run because the waveform evidence was converted into an explicit invariant rather than manually narrated.

#### FIFO push/pull

In the stronger FRISCV FIFO attempt, the agent extracted rows on `push` and `pull` from both buggy and fixed waveforms, carrying pointer, data, and full/empty context. This directly represented queue operations and was more robust than a change-only timeline.

#### TMDS

Successful attempts extracted only data-enable cycles (`DE`) with `D`, `q_out`, disparity/counter state, and intermediate `q_m`. One attempt then compared `q_out` against a generated reference waveform and used `property` to search for mismatches.

#### APB-like interconnect fallback

After the strict APB extractor rejected the interface, generic extraction on `slv_en && slv_ready` captured completed transfers and the selected master-side address/control context. This was the correct abstraction for the available signals.

### Friction in `extract generic`

The required `--when` was not intuitive. Twelve calls omitted it, and 34 other calls explicitly wrote `--when 1`. These two observations point to the same user intent: “emit a row at every selected event.” Making the predicate optional with an implicit `true`, or providing a dedicated cycle-table shorthand, would remove a recurring failure without weakening semantics.

Other repeated construction errors were:

- space-separated payload names interpreted as one signal;
- guessed alias syntax such as `oo=o_done` or `q_out:q_out`;
- repeated `--payload` flags rather than one list;
- time windows slightly beyond the dump end;
- canonical names mixed with scoped names.

## Protocol extractors

### What was actually invoked

- `extract apb`: 2 calls;
- `extract axi`: 0;
- `extract axistream`: 0;
- `extract ahb`: 0;
- `extract atb`: 0.

### APB case

The APB-interconnect trajectory did more than blindly guess a command:

1. It read `wavepeek help extract apb`.
2. It identified the manager-facing `slv_*` side.
3. It mapped clock, reset, select, write, address, write-data, strobe, read-data, and ready signals.
4. It selected APB4 because `PSTRB` existed.
5. The extractor rejected the mapping because `PENABLE` was absent.

That rejection was correct. APB3, APB4, and APB5 all require a setup/access phase distinction through `PENABLE`. The task’s interface is APB-like but not a complete canonical APB interface. The agent briefly speculated that APB3 might omit `PENABLE`, then corrected itself and moved to generic extraction.

This is not primarily command friction. It demonstrates useful strictness: the protocol extractor prevented the agent from labeling a non-APB handshake as APB traffic.

A more actionable error could still say:

> No `PENABLE` can be mapped; this is not a complete APB interface. For a simplified enable/ready handshake, use `extract generic --on 'posedge <clk>' --when '<enable> && <ready>'`.

### Missed AXI-Stream opportunity

The AXI-stream broadcaster task had standard-looking source and three sink interfaces, yet the agent never tried `extract axistream`. Instead it built cross-interface cycle tables containing source data/valid/ready and multiple sink ready/data signals.

This choice was partly reasonable. A single `extract axistream` invocation models one stream interface, whereas broadcaster debugging needs simultaneous context from one source and several sinks. `extract generic` therefore provided a more convenient “whole broadcaster” row.

However, the generic queries mostly used `--when 1`, not actual transfer predicates. They proved that data values appeared in the expected order but did not directly establish:

- the accepted input transfer sequence;
- the transfer sequence on each output;
- exactly-once delivery to all three outputs under backpressure.

A stronger workflow would combine:

- one source `extract axistream`;
- one extraction per output;
- an agent-side join/check of payload sequences;
- one generic cross-interface table only around the first divergence.

Thus the absence of `extract axistream` was not a gross command-selection error, but it left protocol-level evidence weaker than it could have been.

### Why other protocol extractors were not used

The other tasks did not expose clean standard protocol interfaces:

- I2SRV64 used a custom DCache request/response interface, not AHB;
- TMDS, FIFO, CDC, cache, AES, LFSR, and CLINT are custom/stateful structures;
- generic extraction and properties were the right first-class primitives.

## Mode 4: properties and waveform predicates

`property` was invoked 82 times. More than half—42 calls—came from the single OpenE902 LSU-control task that failed in all three attempts.

### Command-level behavior

Capture modes:

- `match`: 54 calls, all successful;
- default capture: 15 calls, 12 successful;
- `assert`: 5, all successful;
- `switch`: 2, both successful;
- guessed `count`: 6, all failed.

The agent clearly wanted a count primitive. After `capture=count` was rejected, it usually switched to `capture=match` and counted rows in Python. Supporting a count summary directly would remove recurring boilerplate and reduce tool output.

### Where properties worked

- checking done pulses;
- detecting TMDS output/reference mismatches during `DE`;
- checking FIFO full/empty assertions;
- evaluating CLINT interrupt conditions;
- checking targeted BMU/DBUS denial logic.

### Conceptual limitation exposed by OpenE902 0059

The LSU-control task is the strongest example of correct command mechanics producing misleading confidence.

The agent:

- generated buggy and fixed waveforms;
- enumerated cycles where several outputs were high;
- compared match counts and timestamps;
- evaluated proposed Boolean equations on every clock edge present in the waveform;
- sampled individual decisive cycles.

All three WavePeek attempts nevertheless failed the verifier.

The issue was not lack of temporal visibility. The available stimulus did not exercise the decisive input combination used by the hidden verifier. A property evaluated over a waveform answers:

> Does this equation hold on the sampled cycles in this run?

It does not answer:

> Is this combinational equation correct over the relevant input space?

The missing next step was targeted stimulus generation, truth-table enumeration, or static Boolean reasoning. WavePeek was used as if local observational agreement were a proof of the RTL equation.

## Mode 5: differential and reference-model workflows

### Differential waveforms

Thirteen trajectories queried more than one waveform file. Ten had explicit differential naming or structure: `buggy/fixed`, `orig/mine`, DUT/reference, or a comparison dump.

Examples:

- 2D convolution: original versus modified implementation, plus a combined comparison testbench;
- I2SRV64: original versus patched waveform;
- FRISCV FIFO: buggy versus fixed dumps;
- OpenE902 CLINT: buggy versus fixed dumps;
- OpenE902 LSU control: buggy versus fixed dumps;
- OpenE902 BMU DBUS: original versus fixed;
- TMDS: DUT versus generated reference waveform.

This pattern was successful in six of the ten explicitly differential trajectories and unsuccessful in four. It is therefore neither automatically good nor bad. Its value depended on the quality of the distinguishing stimulus and the invariant being compared.

### Strong differential use

The CLINT attempt sampled the same eight register/interrupt signals at eight identical timestamps in buggy and fixed waveforms. This directly exposed which write or interrupt transition changed after the patch. The task passed.

The FRISCV FIFO attempts compared push/pull rows and pointer/flag behavior in buggy and fixed waveforms. The task passed in all attempts.

The BMU/DBUS task used targeted properties and point samples around access-denial conditions, and all attempts passed.

### Weak differential use

The failed 2D-convolution attempt created six waveform variants and made 49 calls, but mostly compared output values at selected times and repeatedly refined local extractions. It did not initially encode the signed-arithmetic and saturation rule as an invariant. The later successful attempt used only 12 calls and one deterministic checker.

The failed LSU-control attempt compared observed high-cycle counts between buggy and fixed waveforms. The local testbench did not contain the hidden decisive condition, so the differential view could not expose it.

The failed I2SRV64 attempt saw request and response pulse behavior but did not turn the expected phase/duration relation into a temporal assertion.

### Product implication

Manual two-waveform comparison is common enough to justify at least an official recipe and perhaps a small helper:

- run the same query against two dumps;
- align by normalized event time or clock-event index;
- report first differing row and context;
- distinguish missing rows from changed payload values.

A full `wavepeek diff` command may be larger than necessary, but a retained reference script or skill article would immediately replace many duplicated shell loops.

## Shell composition and helper artifacts

### Batch structure

The 991 invocations came from 602 unique shell tool-call batches:

| Shell composition | Batches | WavePeek invocations |
|---|---:|---:|
| Single-call pipeline | 363 | 363 |
| Sequential/multi-call batch | 133 | 304 |
| Shell `for` loop | 42 | 257 |
| Single direct call | 58 | 58 |
| Inline Python invoking WavePeek via `subprocess` | 6 | 9 |

WavePeek was therefore routinely embedded in a larger shell program rather than called directly.

Common shell patterns among the 602 batches:

- Python present: 262 batches;
- `2>&1`: 483;
- pipe to `head`: 286;
- `2>/dev/null`: 99;
- `grep`: 32;
- `sed`: 11;
- heredoc: 8;
- writing JSON to a file: 5;
- `jq`: 0;
- JSONL: 0.

The agent treated Python as its default query post-processor. Most code was inline and disposable rather than stored as a reusable utility.

### Files created during treatment sessions

At least 139 distinct files were created through `cat` or `tee` in the treatment sessions:

- 75 SystemVerilog files;
- 16 Verilog files;
- 42 Python files;
- one shell script;
- one C file;
- several patches and miscellaneous files.

These counts include debugging/testbench/reference artifacts, not only WavePeek wrappers.

The distribution is revealing:

- AES tasks generated many independent Python AES/key-schedule models and debug testbenches;
- one broadcaster attempt generated 27 temporary `.sv` testbench variants;
- the failed first 2D-convolution attempt generated 12 SystemVerilog testbenches plus a Python model;
- TMDS attempts generated reference Python implementations and several dump/check testbenches;
- Monte Carlo generated multiple temporary SystemVerilog variants.

The agent’s broader strategy was often:

> modify or replace the testbench to expose the right state -> generate a new dump -> inspect it with WavePeek -> revise the testbench or RTL again.

This is legitimate waveform-debugging practice, but it means WavePeek was embedded in a much larger simulation-instrumentation loop. In several cases, the cost and instability came more from proliferating testbenches and reference models than from the waveform queries.

### Reusable scripts versus one-off scripts

There was only one clear reusable shell wrapper around WavePeek:

```text
/tmp/chk.sh
```

It sampled AES key-expansion state at a supplied time. Most other automation was one of:

- a shell `for` loop over times;
- inline Python parsing one query;
- a domain reference model that did not itself provide a reusable WavePeek API;
- a temporary testbench producing a new waveform.

No trajectory materialized a general helper such as:

```text
wp_value_table.py
wp_compare_waveforms.py
wp_extract_check.py
```

This suggests that the CLI is composable enough for ad hoc scripting, but the skill does not yet induce stable reusable analysis patterns.

## Task-by-task trajectory assessment

### AES encryption/decryption 0003 — all three attempts passed

**Use:** key-schedule and round-state microscopy. `value` dominated: 40/70 calls. Seven loops generated 26 calls. The agent sampled `expanded_key_ff` at many times, checked stability, and occasionally used `extract generic` around round/done events.

**Strength:** it combined waveform samples with independent AES reference calculations.

**Weakness:** repeated attempts to address symbolic or explicit slices of wide vectors; many manual time sweeps; a large number of Python/reference scripts relative to the actual waveform question.

**Assessment:** successful but WavePeek mainly served as a sample source for external reasoning. The trajectory was not concise.

### AES 0005 — all three attempts passed

**Use:** decrypt sequencing, key expansion completion, round progression, and output-done timing. This was the most call-heavy task: 111 calls, including 63 `value` calls and seven shell loops producing 45 calls.

**Strength:** the agent checked reuse of the expanded key and correlated round/done state with outputs.

**Weakness:** repeated time sweeps and several intuitive-but-invalid command forms (`capture=count`, repeated `--at`, vector slices). The sole reusable WavePeek shell helper appeared here.

**Assessment:** effective but disproportionately expensive. It demonstrates that manual point sampling can eventually solve a task while still being a poor default workflow.

### AES 0009 — one pass, two failures

**Use:** round progression, key-schedule state, debug output ports, and final `o_done/o_data` rows. Failed attempts grew more elaborate, including custom debug testbenches and many round-filtered extracts.

**Strength:** temporal internals were investigated in depth.

**Weakness:** the decisive verifier failure involved the public/default interface width rather than an internal timing divergence. Local testbenches overrode parameters and made the internal waveform look correct.

**Assessment:** WavePeek became an attractive distraction. The agent validated a locally chosen configuration instead of first validating the module’s default contract.

### AES 0012 — two passes, one failure

**Use:** 28 `extract generic` calls and 30 `value` calls. The strongest attempts extracted the full expanded key, compared it word-by-word against a Python AES-256 schedule, and inspected round progression.

**Strength:** good hybrid waveform/reference-model reasoning. Successful attempts converted a huge internal register into an independently checked schedule.

**Weakness:** many retries caused by missing predicates, out-of-range windows, unsupported slices, and one-off parser/model scripts. The failed attempt built 11 Python helpers plus a C helper without converging.

**Assessment:** strong evidence that WavePeek is valuable for internal algorithm sequencing, but only when coupled to one trusted reference model rather than many evolving models.

### AXI-stream broadcaster — all three attempts passed

**Use:** unconditional cycle tables and `change` queries across source and multiple output interfaces. The agent traced the sequence `A5 -> 5A -> 5B` under backpressure.

**Strength:** generic extraction made simultaneous cross-interface state visible and clearly showed the formerly lost `0x5A` value.

**Weakness:** no protocol extractor or per-interface transfer conservation check; one attempt generated 27 temporary testbenches.

**Assessment:** waveform use was substantively successful. The analysis would be stronger and much cheaper with one focused backpressure test, source/output transfer extraction, and a sequence comparison.

### Custom FIFO 0004 — all three attempts passed

**Use:** mostly hardcoded timestamp sampling and `change` timelines. 45 `value` and 17 `change` calls; five loops generated 38 calls.

**Strength:** the agent reconstructed queue/data/error timing around reported table rows.

**Weakness:** 18 failed calls, chiefly trigger/clock naming, missing arguments, and inaccessible unpacked-array elements. It repeatedly switched between guessed clocks and trigger styles.

**Assessment:** ultimately effective but one of the clearest command-friction trajectories. A clocked row extractor with visible queue-state signals would have been simpler.

### Direct-map cache 0003 — all three attempts passed

**Use:** extensive point sampling of victim way, tags, hits, valid/dirty state, and outputs. One attempt made 64 calls with no failed WavePeek process.

**Strength:** command construction was accurate and the evidence matched the cache scenarios.

**Weakness:** 60 calls were generated by loops. The same evidence could have been obtained with a small number of multi-time `value` or unconditional clocked extracts.

**Assessment:** semantically good, operationally inefficient. This is the strongest argument for a canonical multi-time/cycle-table recipe.

### Dual-port memory — two passes, one failure

**Use:** simple discovery, transition scans, and point values around simultaneous port operations.

**Strength:** WavePeek exposed unknown/X read behavior and collision timing.

**Weakness:** the failed trajectory observed the symptom but did not derive or validate the required collision policy.

**Assessment:** appropriate lightweight use, but waveform observation alone did not specify the intended memory semantics.

### Heavy 2D convolution — two failures, one pass

**Failed attempt 1:** six waveform variants, 49 calls, 12 generated SystemVerilog testbenches, manual output comparisons, and repeated generic extracts. It produced abundant evidence but did not initially encode the signed arithmetic/saturation rule.

**Successful attempt 3:** 12 calls, one focused dump, one `extract generic`, and one Python invariant checker over all rows.

**Assessment:** the clearest within-task contrast. More waveform calls did not help; a precise invariant did.

### I2SRV64 DCache arbiter — one pass, one model failure, one provider-invalid attempt

**Use:** generic request rows, done-pulse properties, and state transitions. No standard protocol extractor was appropriate.

**Strength:** request payload and arbiter state were captured at the correct clock event.

**Weakness:** the failed attempt did not convert the expected write/read response phase and pulse width into an explicit temporal check.

**Assessment:** useful visibility, incomplete specification of the timing contract.

### ULX3S camera/TMDS — two passes, one failure

**Use:** `DE`-gated extraction, intermediate encoding state, output/reference mismatch properties, and generated reference/test waveforms.

**Strength:** successful attempts used the correct event boundary and an independent encoder/reference.

**Weakness:** failed calls frequently used space-separated payloads, guessed aliases, wrong scopes, and invalid count capture. The failed attempt did not converge despite extensive instrumentation.

**Assessment:** good fit for WavePeek when the extracted rows feed a trusted reference model.

### FRISCV APB interconnect — one failure, two passes

**Use:** change/value timelines, one generic completion extractor, and the only two protocol-specific calls in the run.

**Strength:** the agent read APB help, mapped the manager-facing interface thoughtfully, accepted the strict `PENABLE` rejection, and fell back correctly.

**Weakness:** it initially treated the task name “APB” as sufficient evidence of a canonical APB interface.

**Assessment:** good recovery. The extractor’s strictness was useful and prevented a false protocol interpretation.

### FRISCV FIFO — all three attempts passed

**Use:** pointer/flag timelines and, in the strongest attempt, push/pull rows from buggy and fixed dumps.

**Strength:** event-oriented extraction matched queue semantics well; differential analysis was focused.

**Weakness:** some wildcard/native and time-bound friction; repeated long argument lists were not materialized as a source document.

**Assessment:** one of the better practical uses of `extract generic`.

### OpenE902 CLINT 0057 — all three attempts passed

**Use:** write-event extraction, interrupt properties, and a buggy/fixed timestamp sweep over register and interrupt outputs.

**Strength:** differential samples were directly tied to writes and interrupt behavior.

**Weakness:** scoped/canonical clock-name mixing caused retries; the comparison remained manually scripted.

**Assessment:** successful and technically meaningful, though a first-divergence helper would reduce duplication.

### OpenE902 LSU control 0059 — all three attempts failed

**Use:** 42 properties, multiple buggy/fixed comparisons, match-count loops, and targeted point samples.

**Strength:** the agent used WavePeek’s Boolean-query capability extensively and generally correctly.

**Weakness:** it treated agreement over the local waveform as proof of the Boolean equations. The decisive hidden stimulus was absent.

**Assessment:** the key failure was methodological rather than command syntax. WavePeek was used to validate observations, but the task required broader input-space reasoning or new targeted stimulus.

### OpenE902 BMU/DBUS 0071 — all three attempts passed

**Use:** compact change/value/property checks around access denial and response validity, with one original/fixed comparison.

**Strength:** targeted signals, small number of calls, and direct relation to the bug condition.

**Weakness:** one repeated-`--at` syntax mistake.

**Assessment:** efficient and successful.

### LFSR 0001 — all three attempts passed

**Use:** state transitions, point sampling, recurrence properties, and one unconditional extract.

**Strength:** simple temporal structure made waveform evidence easy to interpret.

**Weakness:** repeated experiments with plain-signal triggers, missing `--on`, and a property expression that placed `posedge` inside `--eval`.

**Assessment:** successful despite unnecessary command exploration. One clocked extraction plus a recurrence checker would be cleaner.

### Monte Carlo CDC 0006 — all three attempts passed

**Use:** almost exclusively event extraction on `valid_out_b`, plus counter/data checks.

**Strength:** concise, transaction-like, and machine checked. It used only 19 calls across all three attempts.

**Weakness:** one initial under-specified extract and one output-truncation adjustment.

**Assessment:** the best example of a low-friction, high-value generic extraction workflow.

## What worked

The successful patterns were:

1. **Always discovering bounds and hierarchy first.**
2. **Sampling on the owning clock edge.**
3. **Using `extract generic` for actual events rather than value changes.**
4. **Generating a focused dump when the original waveform lacked internal state.**
5. **Comparing waveform rows to one explicit invariant or trusted reference model.**
6. **Using buggy/fixed differential analysis with identical stimulus.**
7. **Keeping the decisive row set bounded and machine-checkable.**

The most convincing trajectories were Monte Carlo CDC, successful 2D convolution, FRISCV FIFO, CLINT, and targeted BMU/DBUS checks.

## What did not work

The recurring weak patterns were:

1. **Manual timestamp microscopy without a stated invariant.**
2. **Creating many testbench/reference variants before isolating the first distinguishing condition.**
3. **Using local waveform agreement as proof of a combinational equation.**
4. **Using `change` as a transaction counter.**
5. **Validating an internal algorithm while neglecting the default module interface.**
6. **Repeating identical or nearly identical queries after syntax/parser errors.**
7. **Using shell pipelines and `head` as the primary output-bound mechanism instead of native query bounds.**

The failed 2D-convolution attempt, AES 0009 failures, and OpenE902 LSU-control failures illustrate these patterns.

## Concrete implications for WavePeek and its skill

### P0: document/encode the event model more directly

The command-routing material should include three literal canonical recipes:

```text
cycle table:
  extract generic --on "posedge clk" --when 1 --payload ...

event rows:
  extract generic --on "posedge clk" --when "valid && ready" --payload ...

Boolean check:
  property --on "posedge clk" --eval "condition" --capture match
```

The distinction among event selection, predicate evaluation, and output-change suppression needs to be visible without opening a reference article.

### P0: make common intuitive forms legal

The corpus provides direct evidence for several forgiving changes:

- allow omitted `--when` in `extract generic` to mean `true`;
- accept repeated `--at` flags additively;
- accept repeated `--payload`/`--signals` flags additively;
- add `property --count` or `--capture count`;
- improve recovery diagnostics for plain/wildcard triggers by printing the exact native-sampling rewrite.

### P1: support projections of wide signals

A projection syntax for packed-vector slices would materially improve AES and other wide-datapath work. At minimum:

```text
expanded_key[127:0]
```

should be representable without dumping and parsing the entire vector. Unpacked arrays that are absent from the dump must still remain unavailable.

### P1: add a first-divergence/differential recipe

Ten trajectories independently reinvented two-waveform comparison. A small maintained helper or skill article should cover:

- same query on two dumps;
- alignment by event index/time;
- first missing/differing row;
- context before and after divergence.

### P1: make protocol fallback explicit

Protocol extractor errors should suggest the corresponding generic handshake recipe when required protocol signals are physically absent. The APB `PENABLE` case is an ideal example.

### P1: provide an AXI-Stream broadcaster recipe

For one source and multiple sinks:

1. extract accepted source transfers;
2. extract each output transfer stream;
3. compare payload sequences;
4. use generic cross-interface rows only around the first mismatch.

This would turn visual state evidence into a protocol-level conservation check.

### P2: guard against query thrashing

A wrapper can track:

```text
waveform content hash + argv + exit/result class
```

and warn after an identical failed query is repeated without a waveform change. It should not reject repeats because identical queries against regenerated dumps are legitimate.

### P2: separate waveform evidence from testbench proliferation

The skill should encourage this order:

1. state the hypothesis;
2. identify the minimum missing signals/stimulus;
3. create one focused testbench/dump;
4. run one bounded extraction;
5. check one distinguishing invariant.

This would counter the observed tendency to create many temporary testbench variants without a stable evidence criterion.

## Final assessment

The rerun shows that DeepSeek did not merely “call WavePeek because it was forced.” It developed real waveform-debugging workflows: discovery, clocked tables, event extraction, differential dumps, Python reference models, and iterative testbench instrumentation.

The usage was strongest when WavePeek supplied a compact, clock-aligned dataset to a deterministic checker. It was weakest when used as an interactive microscope without a root-cause hypothesis or when local waveform coverage was mistaken for specification coverage.

The protocol extractors were not broadly exercised. The sole APB attempt demonstrated correct strict rejection and a sensible generic fallback. AXI-Stream extraction was a missed opportunity for stronger transfer-conservation evidence in the broadcaster task, although generic extraction remained useful for cross-interface backpressure context.

The most important product-level conclusion is that agents naturally want three higher-level operations:

1. **clocked cycle tables**;
2. **counts and assertions over matching events**;
3. **first divergence between two waveforms**.

WavePeek already contains most primitives needed for the first two, but their current CLI forms are not the forms the agent instinctively writes. The differential workflow currently has to be rebuilt manually in shell and Python.
