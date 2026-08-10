---
title: "The Impact of WavePeek on Agentic RTL Problem Solving by OpenAI GPT-5.6 Models"
subtitle: "A Paired Study of Luna xhigh, Terra xhigh, and Sol high on 18 CVDP Tasks"
date: "August 10, 2026"
lang: en-US
---

# Source Experiments

This report is based on the following experiment records in this repository.

Primary 108-trial experiments used for the normalized 324-trial comparison:

- Luna xhigh: `experiments/2026-08-09_194827Z_luna-xhigh-full-3x_a0015b2a/`
- Terra xhigh: `experiments/2026-08-10_044313Z_terra-xhigh-full-3x_50674f54/`
- Sol high: `experiments/2026-08-10_074605Z_sol-high-full-3x_6bcc3773/`

Supplementary six-trial clarification experiments used only to interpret the two infrastructure anomalies:

- Luna xhigh Monte Carlo clarification: `experiments/2026-08-10_042702Z_luna-xhigh-monte-carlo-clarification_6cc7fe46/`
- Terra xhigh AES clarification: `experiments/2026-08-10_072737Z_terra-xhigh-aes0012-verifier-clarification_964a66d9/`

The clarification experiments supplement but do not replace or alter the three primary experiment records.

# Abstract

This study examines not a single model, but a family of three OpenAI GPT-5.6 profiles that were actually used: **Luna xhigh**, **Terra xhigh**, and **Sol high**. The same paired A/B experiment was performed for each profile on 18 CVDP RTL tasks: a baseline without WavePeek and a treatment in which the agent was required to meaningfully apply WavePeek to a waveform before finalizing its solution. The main normalized sample contains **324 trials**: 3 models x 18 tasks x 2 branches x 3 attempts. Including 12 clarification runs for two infrastructure anomalies, 336 trials were actually performed.

The main result is that the **"always use WavePeek on every RTL task" policy is not supported**. In the pooled sample, the pass rate changed from 80.9% to 82.7%, or +1.9 percentage points; the task-level bootstrap interval for the mean effect includes both a small negative effect and a small improvement, while the exact sign test shows no difference. At the same time, forced WavePeek consistently increases time, fresh input, output, cache reads, the number of turns, tool calls, and context size for all three profiles.

Increasing the model grade changes the **shape of the cost**, but does not eliminate it. Luna tends to turn the mandatory tool into a long exploratory loop. Terra reduces the number of turns and calls most strongly. Sol follows a roughly Terra-like tool-use plan, but writes substantially less and uses less reasoning on each turn. At the same time, there is no reliable evidence that the more advanced model derives a greater quality improvement from WavePeek or uses the CLI fundamentally more accurately.

Task-level analysis shows a strong ceiling effect: 10 of 18 tasks passed in all 18 "model x branch x attempt" combinations, while three hard-tail tasks produced 46 of the 59 failures. Collectively, all models solved each of the 18 tasks at least once, but the baseline branch alone already covered 18/18 tasks; forced WavePeek covered 17/18. Thus, the current benchmark primarily measures the cost of mandatory waveform verification for solutions that have already nearly been found, rather than the value of a waveform as a source of an otherwise unknown diagnosis.

# Executive Summary

1. **Do not force WavePeek globally.** On this workload, mandatory use provides no statistically detectable quality improvement, but creates a large and reproducible resource tax.
2. **Do not interpret the experiment as a negative test of WavePeek itself.** The experiment measured a mandatory-use policy, not a scenario in which "the tool is available and selected when needed."
3. **More advanced profiles run the agent loop more efficiently, but do not demonstrably derive more benefit from WavePeek.** Terra reduces the number of steps; Sol compresses reasoning and output. Meaningful-call yield remains around 62-63% for all profiles.
4. **The binary is not the main source of overhead.** All WavePeek calls across all three treatment branches took only a few seconds in total. The losses arise from help/discovery, dump preparation, additional hypotheses, repeated RTL reading, and repeatedly rereading the expanded context.
5. **The benchmark does not sufficiently differentiate the models and is poorly aligned with WavePeek's strongest use case.** Most tasks are saturated, and prompts often state the defect or required change in advance.
6. **The next experiment should measure selective use on diagnosis-hidden tasks.** It should include unavailable, available-not-forced, selective-router, and forced-stress-test branches, as well as tasks in which the waveform contains genuinely missing causal information.

# 1. Research Questions

The study addresses five related questions.

**Q1. Does mandatory WavePeek improve the solve rate?** Paired branches of the same model are compared on the same tasks.

**Q2. What is the resource cost of mandatory WavePeek?** Wall-clock time, fresh input, cache reads, output, reasoning, API turns, tool calls, tool-result output, final context, and proxy cost are measured.

**Q3. Does the effect change as model grade increases?** Luna xhigh, Terra xhigh, and Sol high are compared.

**Q4. Does the practical style of WavePeek use differ?** The analysis covers the number of calls, meaningful successful calls, help/discovery tax, result volume, and the position of waveform analysis within the trajectory.

**Q5. Do failures overlap across models?** Task coverage, solution robustness, and the concentration of errors by task are examined.

# 2. Experimental Design

## 2.1. Profiles

| Profile | Model ID | Reasoning | Role in comparison |
| --- | --- | --- | --- |
| Luna xhigh | openai-codex/gpt-5.6-luna | xhigh | junior profile; longest trajectories |
| Terra xhigh | openai-codex/gpt-5.6-terra | xhigh | middle profile; reasoning matched to Luna |
| Sol high | openai-codex/gpt-5.6-sol | high | senior profile; lower reasoning level than Luna/Terra |

The Luna -> Terra comparison is closer to a clean grade comparison because the reasoning level is the same. The Terra -> Sol comparison contains a confound: both the model and the reasoning level change. Therefore, differences involving Sol cannot be attributed entirely to grade alone.

## 2.2. Tasks, Branches, and Repetitions

The same 18 preselected CVDP datapoints were used for all profiles. Each task has two branches and three independent attempts:

- **Baseline**: WavePeek is unavailable.
- **Forced WavePeek**: the skill and CLI are installed, and the prompt includes an instruction to meaningfully apply WavePeek to the task waveform before the final response.

The exact additional instruction for the treatment branch was:

> Use the installed WavePeek skill and CLI to inspect waveform behavior while solving this task. You must run WavePeek meaningfully against a task waveform before finalizing the solution.

Thus, the treatment is not merely tool availability. It is a stronger policy: **availability + skill + mandatory meaningful activation**.

## 2.3. Scale

- 18 tasks x 2 branches x 3 attempts = 108 trials per profile;
- 3 profiles = 324 trials in the main normalized sample;
- two clarification runs of 6 trials each were additionally performed;
- 336 trials were actually run in total.

WavePeek was called at least once in all 162 treatment trials, and the adoption audit classified the use as compliant. Therefore, a negative or null quality result cannot be explained by the tool not being activated.

## 2.4. Infrastructure and Provenance

The main full runs used the same task set and pinned infrastructure versions:

- WavePeek v2.2.0, commit `a27a96b557cb7b9df970fbfef65a5c8354befbc9`;
- Pi coding agent 0.83.0, commit `845d6ff1f6643aba440341cce877ce1c43ebbc39`;
- Harbor commit `0348989adffbb43bf0b410fd36197333239633f1`;
- CVDP dataset commit `5b807d945f6a99aa645f7e43a64a2115e281b4bf`;
- frozen selection SHA-256 `945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d`.

## 2.5. Handling Infrastructure Anomalies

There were two anomalies in the original full runs:

1. Luna, `monte_carlo_0006`, treatment attempt: agent timeout after 3600 seconds.
2. Terra, `AES_encryption_decryption_0012`, baseline attempt: verifier timeout after 600 seconds.

A separate six-trial clarification series with increased limits was performed for each affected task. In the main sample, the entire corresponding task pair—that is, three baseline and three treatment attempts—was replaced with the clarification results. After normalization, the symmetric 324-trial matrix is preserved. The Luna clarification solved Monte Carlo in neither branch; the Terra clarification solved AES0012 in all six attempts. Consequently, the original timeouts do not determine the final conclusions.

## 2.6. Statistical Approach

The methodology follows the key principles of paired agent-evaluation studies by JetBrains [1-3]: do not rely on k=1, compare the same task across branches, instrument adoption, and distinguish a null significance result from proven equivalence.

For continuous metrics, the median of three attempts is first taken within each "task x branch" pair, after which the paired treatment/baseline ratio is calculated for the 18 tasks. The report presents the median paired effects, bootstrap interval, and Wilcoxon signed-rank test on the log ratios.

For quality, trial pass counts and task-level changes in 0-3 successful attempts are used. The exact sign test is applied only to tasks with nonzero changes. A null result is interpreted as **"no difference detected,"** not as proof of identity.

# 3. Main Quality Result

| Profile | Baseline | Forced WavePeek | Difference | Difference, pp |
| --- | ---: | ---: | ---: | ---: |
| Luna xhigh | 44/54 (81.5%) | 45/54 (83.3%) | +1 trial | +1.9% |
| Terra xhigh | 45/54 (83.3%) | 43/54 (79.6%) | -2 trials | -3.7% |
| Sol high | 42/54 (77.8%) | 46/54 (85.2%) | +4 trials | +7.4% |
| All profiles | 131/162 (80.9%) | 134/162 (82.7%) | +3 trials | +1.9% |

In the pooled sample, forced WavePeek produced only three additional successes out of 162 attempts. This is not a monotonic grade effect:

- Luna: +1 trial;
- Terra: -2 trials;
- Sol: +4 trials.

| Profile | Mean task-level effect | 95% bootstrap interval | Better / worse / tie | Exact sign p |
| --- | ---: | ---: | ---: | ---: |
| Luna xhigh | +1.9% | -5.6% ... +9.3% | 3/2/13 | 1.0000 |
| Terra xhigh | -3.7% | -13.0% ... +3.7% | 1/2/15 | 1.0000 |
| Sol high | +7.4% | 0.0% ... +16.7% | 3/0/15 | 0.2500 |
| All profiles | +1.9% | -3.1% ... +6.8% | 7/4/43 | 0.5488 |

The pooled sign test gives p approximately 0.55. The interval permits both a small negative and a small positive effect. The correct conclusion is therefore:

> On this benchmark, no consistent change in solve rate from mandatory WavePeek was detected in either the pooled sample or any individual profile. The data do not prove equal quality and do not rule out a small effect.

## 3.1. Why Sol's Positive Result Is Insufficient

Sol improved from 42/54 to 46/54, but all four additional successes are concentrated in three tasks:

- `dual_port_memory_0001`: 1/3 -> 3/3;
- `heavy_2dconv-FPGA_0009`: 0/3 -> 1/3;
- `heavy_opene902_0059`: 2/3 -> 3/3.

No task worsened for Sol, so the sign test on the three non-ties gives p=0.25. This is an interesting signal, but not reliable evidence. On `dual_port_memory` and `2dconv`, Sol's baseline was weaker than those of the junior profiles; some of the improvement plausibly reflects stochastic recovery after unsuccessful baseline trajectories.

## 3.2. No Single Task Where WavePeek Helped All Models

No task-level improvement is reproduced simultaneously for Luna, Terra, and Sol. For example:

- `2dconv` improved for Luna and Sol, but worsened for Terra;
- `dual_port_memory` improved for Terra and Sol, while Luna already had 3/3 in both branches;
- `monte_carlo` worsened for Terra from 2/3 -> 0/3, while Luna and Sol did not solve it in either branch.

This heterogeneity looks more like an interaction between a specific task and a stochastic trajectory than a stable new capability.



# 4. Resource Cost of Forced WavePeek

| Metric | Luna xhigh | Terra xhigh | Sol high |
| --- | ---: | ---: | ---: |
| Wall-clock | +30.9% [+11.2%; +80.6%], p=0.0028 | +68.6% [+17.3%; +87.4%], p=0.0005 | +56.0% [+25.5%; +106.6%], p=0.0003 |
| Fresh input | +74.6% [+55.9%; +118.7%], p=<0.0001 | +59.3% [+30.3%; +101.6%], p=<0.0001 | +63.9% [+44.0%; +141.1%], p=<0.0001 |
| Output | +36.8% [+7.6%; +121.8%], p=0.0023 | +70.9% [+31.2%; +122.1%], p=<0.0001 | +57.2% [+17.0%; +157.0%], p=<0.0001 |
| Cache reads | +256.6% [+117.0%; +388.1%], p=<0.0001 | +153.7% [+103.2%; +297.5%], p=<0.0001 | +265.9% [+141.2%; +416.8%], p=<0.0001 |
| API turns | +64.6% [+24.1%; +97.1%], p=<0.0001 | +43.6% [+26.8%; +91.7%], p=0.0003 | +45.5% [+27.9%; +86.6%], p=0.0003 |
| Tool calls | +82.3% [+67.2%; +164.9%], p=<0.0001 | +60.0% [+40.6%; +97.4%], p=0.0003 | +86.7% [+39.4%; +138.5%], p=0.0002 |
| Tool-result output | +187.1% [+119.3%; +212.3%], p=<0.0001 | +110.1% [+69.6%; +154.2%], p=<0.0001 | +156.3% [+103.3%; +194.9%], p=<0.0001 |
| Reasoning | +35.3% [+11.7%; +106.6%], p=0.0047 | +71.3% [+33.0%; +149.9%], p=<0.0001 | +70.4% [+42.9%; +189.0%], p=<0.0001 |
| Final context | +96.6% [+71.7%; +115.2%], p=<0.0001 | +73.7% [+59.6%; +105.1%], p=<0.0001 | +90.9% [+62.1%; +123.3%], p=<0.0001 |
| Pi cost proxy | +86.2% [+41.9%; +137.2%], p=<0.0001 | +73.8% [+45.0%; +133.8%], p=<0.0001 | +84.9% [+39.7%; +149.4%], p=<0.0001 |

All major resource metrics increase. Fresh input, cache reads, tool-result output, tool calls, and final context are especially consistent. The direction is the same on almost every task:

- tool calls increased on 18/18 Luna tasks, 17/18 Terra tasks, and 18/18 Sol tasks;
- cache reads increased on 18/18, 17/18, and 17/18 tasks;
- final context increased on all 18 tasks for each profile.





## 4.1. Typical Task in Absolute Terms

| Profile | Branch | Time | Fresh input | Output | Cache reads | Turns | Tool calls | Context | Cost proxy |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Luna xhigh | Without WavePeek | 293 s | 48.8k | 13.2k | 273.7k | 17.0 | 21.5 | 31.5k | 0.031 |
| Luna xhigh | Forced WavePeek | 404 s | 92.1k | 18.1k | 881.4k | 26.0 | 44.5 | 62.2k | 0.059 |
| Terra xhigh | Without WavePeek | 208 s | 36.3k | 8.3k | 135.7k | 11.0 | 15.0 | 22.3k | 0.207 |
| Terra xhigh | Forced WavePeek | 341 s | 51.6k | 14.9k | 387.6k | 15.0 | 23.5 | 41.8k | 0.355 |
| Sol high | Without WavePeek | 167 s | 32.4k | 5.2k | 81.7k | 11.0 | 14.0 | 16.7k | 0.393 |
| Sol high | Forced WavePeek | 253 s | 54.0k | 7.8k | 253.4k | 15.5 | 24.5 | 32.0k | 0.676 |

Absolute cost-proxy values across models reflect differences in the profiles' list prices and should not be used as a pure measure of algorithmic efficiency. For the effect of WavePeek, the relative change within a single profile is more important. `reportedCost` is absent from the trials, so the cost proxy is not an actual billed amount.

## 4.2. Nearly Identical Absolute Detour

Despite different baseline runtimes, forced WavePeek adds approximately the same separate block of work:

- Luna: a median paired increase of about 78 seconds;
- Terra: about 80 seconds;
- Sol: about 83 seconds.

The senior profiles have faster baselines, so the same absolute detour becomes a larger relative percentage for Terra and Sol. A stronger model speeds up the main task, but the mandatory WavePeek workflow remains.

# 5. How Grade Changes Agent Behavior

| Profile | API turns: B -> WP | Tool calls: B -> WP | Reasoning: B -> WP | Output: B -> WP | WP calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Luna xhigh | 17.0 -> 26.0 | 21.5 -> 44.5 | 9.4k -> 11.1k | 13.2k -> 18.1k | 18.5 |
| Terra xhigh | 11.0 -> 15.0 | 15.0 -> 23.5 | 4.5k -> 7.9k | 8.3k -> 14.9k | 12.0 |
| Sol high | 11.0 -> 15.5 | 14.0 -> 24.5 | 2.2k -> 3.3k | 5.2k -> 7.8k | 12.0 |



## 5.1. Luna: A Long Exploratory Loop

Luna has the longest trajectory in both branches and expands it especially strongly under mandatory WavePeek. A typical treatment task requires 26 turns, 44.5 tool calls, and 18.5 WavePeek calls. Luna more often continues exploring after obtaining a sufficient answer: it reads help, searches again for signals, runs several query variants, and returns to the RTL and simulation.

This does not mean that Luna uses the tool incorrectly in every individual case. At the workload level, however, it is worse at stopping, and the local utility of a waveform query quickly turns into a large context loop.

## 5.2. Terra: The Main Improvement Is Fewer Steps

Moving from Luna to Terra produces the clearest efficiency jump with the same `xhigh` setting:

- in treatment, Terra makes approximately 42% fewer turns;
- approximately 46% fewer tool calls;
- approximately 31% fewer WavePeek calls;
- substantially less fresh input and cache reads.

Terra made fewer tool calls than Luna on all 18 tasks. Terra's defining characteristic is earlier termination of exploration, not a fundamentally different type of query.

## 5.3. Sol: Not Fewer Tools, but Less Text Between Them

Sol high follows a roughly Terra-like tool-use plan. In treatment, relative to Terra, it:

- is approximately 12% faster;
- uses approximately half as many reasoning tokens;
- generates approximately 29% less output;
- while often reading more fresh input and making slightly more tool calls.

On 13 of 18 tasks, Sol used more fresh input than Terra, and on 11 of 18 it made more tool calls. At the same time, output was lower on 17 of 18 tasks, reasoning was lower on all 18, and runtime was lower on 15 of 18. This looks not like a shorter plan, but like denser execution of each step.

In treatment, reasoning per turn is approximately 390 tokens for Luna, 405 for Terra, and 203 for Sol. However, part of the effect may be due to Sol using `high` versus `xhigh` for the other two profiles.

## 5.4. No Monotonic Reduction in the Forced-Tool Tax

A higher grade does not consistently reduce relative overhead. Terra has a lower tax on several input/context metrics, but Sol returns to Luna-like increases in cache reads and tool calls. This is expected if a fixed detour is added to an increasingly fast baseline.

# 6. Practical Use of WavePeek

| Profile | All calls | Meaningful successful | Meaningful yield | Help/discovery | Help share | Failed | Binary time | WP in tool output | WP in tool-output increase |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Luna xhigh | 1031 | 634 | 61.5% | 310 | 30.1% | 39 | 3.49 s | 37.8% | 68.0% |
| Terra xhigh | 705 | 440 | 62.4% | 244 | 34.6% | 14 | 1.95 s | 33.1% | 70.1% |
| Sol high | 642 | 406 | 63.2% | 210 | 32.7% | 8 | 1.79 s | 35.1% | 63.3% |



## 6.1. Senior Models Call the CLI Less Often, but Not More Accurately

The number of calls falls from 1031 for Luna to 705 for Terra and 642 for Sol. However, meaningful yield remains virtually unchanged: 61.5%, 62.4%, and 63.2%. This provides no evidence that a senior model is fundamentally better at selecting commands or formulating queries. The main effect is earlier stopping.

## 6.2. Help/Discovery Tax Persists at Every Grade

About 30-35% of invocations are `help`, `docs`, `-h`, `--help`, and related discovery activity. This is directly related to the skill's current philosophy: it is positioned as a router and requires consulting installed help or the relevant documentation topic before nontrivial use.

This approach improves syntax accuracy, but creates a recurring tax in a forced workload. The model often follows this sequence:

1. read the skill;
2. invoke top-level help;
3. read help for a specific command;
4. find the waveform;
5. run `info`;
6. find the scope and signals;
7. formulate a query;
8. verify the result and continue the investigation.

For a naturally relevant complex task, this sequence may be justified. For a prescriptive repair, it becomes ceremony.

## 6.3. Direct WavePeek Output Expands Subsequent Context

WavePeek accounts for 33-38% of all tool-result output in treatment branches and explains 63-70% of the increase in tool-result output relative to baseline. This material is then reprocessed on every subsequent turn. Therefore, the largest relative penalty is not necessarily in fresh input, but in cache reads: +154% for Terra and approximately +257-266% for Luna/Sol.

This is a typical mechanism of **agentic amplification**:

> additional tool -> additional results -> additional hypotheses and turns -> rereading the accumulated context -> further growth in cache reads.

## 6.4. The Binary Is Practically Free

The total measured WavePeek execution time across all 54 treatment trials for each profile was:

- Luna: about 3.49 seconds;
- Terra: about 1.95 seconds;
- Sol: about 1.79 seconds.

Against approximately 80 additional seconds on a typical task, this is negligible. The source of overhead is not the performance of the Rust CLI, but the surrounding agent behavior.

## 6.5. WavePeek More Often Confirms a Patch Than Forms the Diagnosis

According to an approximate event-order heuristic, a meaningful waveform-backed call occurred before the first detected code edit in only:

- 21/54 Luna trials (38.9%);
- 20/54 Terra trials (37.0%);
- 16/54 Sol trials (29.6%).

This is not a strict semantic classification: a shell edit may not be the only way to modify a file, and an early query does not necessarily causally determine the patch. Nevertheless, the pattern is consistent: in most runs, the model first derives a solution from the prompt, RTL, and test, and then uses WavePeek as a mandatory verification step. This effect is strongest for Sol.

# 7. Task-Level Picture and Failure Overlap

## 7.1. Aggregate Coverage

Under the most permissive definition—"a task is solved if at least one trial passed the verifier"—the union of all profiles and branches covers **18/18 tasks**. No task has a 0/18 result across the full sample.

Moreover:

- the baseline without WavePeek already has at least one success on 18/18 tasks;
- forced WavePeek has at least one success on 17/18 tasks;
- the only task with 0/9 across the entire WavePeek branch is `monte_carlo_0006`.

| Profile | Any success, both branches | Robust: >=2/3 in at least one branch | No successes out of 6 |
| --- | ---: | ---: | --- |
| Luna xhigh | 17/18 | 16/18 | monte_carlo 0006 |
| Terra xhigh | 17/18 | 15/18 | axis_broadcaster 0001 |
| Sol high | 16/18 | 15/18 | axis_broadcaster 0001, monte_carlo 0006 |

The intersection of the sets of completely unsolved tasks is empty:

- Luna did not solve `monte_carlo_0006`;
- Terra did not solve `axis_broadcaster_0001`;
- Sol did not solve `axis_broadcaster_0001` or `monte_carlo_0006`.

The models partially complement one another, but this does not mean the benchmark requires an ensemble: nearly all coverage is already provided by the pooled baseline of the three profiles alone, and most tasks are solved by all of them.

## 7.2. The Benchmark Is Nearly Binary

The distribution of successes over 18 attempts per task is:

- 10 tasks: 18/18;
- 4 tasks: 15-17/18;
- 1 task: 12/18;
- 3 tasks: 2-3/18.

The three hard-tail tasks produced 46 of all 59 failures, or about 78%. This is not a smooth difficulty scale, but a large saturated cluster and a sharp tail.



## 7.3. Three Hard-Tail Tasks

| Task | Luna B -> WP | Terra B -> WP | Sol B -> WP | Total |
| --- | ---: | ---: | ---: | ---: |
| axis_broadcaster 0001 | 2/3 -> 1/3 | 0/3 -> 0/3 | 0/3 -> 0/3 | 3/18 |
| heavy 2dconv-FPGA 0009 | 0/3 -> 1/3 | 1/3 -> 0/3 | 0/3 -> 1/3 | 3/18 |
| monte_carlo 0006 | 0/3 -> 0/3 | 2/3 -> 0/3 | 0/3 -> 0/3 | 2/18 |

### `heavy_2dconv-FPGA_0009`

This is the cleanest case of a "rare successful trajectory." Each model solved the task exactly once, but in different branches: Luna and Sol with WavePeek, Terra without it. No configuration reached 2/3. Formally, the task is covered, but the system does not solve it reproducibly.

The prompt nevertheless lists five specific defects and four required fixes. Therefore, the rarity of success points more to the difficulty of correctly implementing a multi-location patch than to the need to discover an unknown cause from the waveform.

### `axis_broadcaster_0001`

All three successes belong to Luna; Terra and Sol produced 0/12. Here the model failures do not overlap by chance. Two interpretations are possible: Luna more often selects an appropriate handshake architecture, or its stochastic distribution is simply more favorable at small n. Forced WavePeek does not eliminate an incorrect abstraction of AXI Stream backpressure.

### `monte_carlo_0006`

The only successes are 2/3 for Terra baseline. Luna and Sol produced 0/12, and the entire forced-WavePeek branch produced 0/9. The task is difficult because it combines an LFSR, CDC, valid-transfer semantics, and a counter; mandatory waveform activity did not ensure a correct architectural patch.

## 7.4. Full Task-Level Matrix

In the Luna/Terra/Sol columns, each value is written as `baseline/WavePeek`, each out of 3 attempts.

| Task | Heavy | Luna B/WP | Terra B/WP | Sol B/WP | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| monte_carlo 0006 | no | 0/0 | 2/0 | 0/0 | 2/18 |
| axis_broadcaster 0001 | no | 2/1 | 0/0 | 0/0 | 3/18 |
| heavy 2dconv-FPGA 0009 | yes | 0/1 | 1/0 | 0/1 | 3/18 |
| heavy opene902 0059 | yes | 2/3 | 1/1 | 2/3 | 12/18 |
| dual_port_memory 0001 | no | 3/3 | 2/3 | 1/3 | 15/18 |
| heavy I2SRV64 0001 | yes | 2/2 | 3/3 | 3/3 | 16/18 |
| direct_map_cache 0003 | no | 3/2 | 3/3 | 3/3 | 17/18 |
| heavy ULX3S camera 0005 | yes | 2/3 | 3/3 | 3/3 | 17/18 |
| custom_fifo 0004 | no | 3/3 | 3/3 | 3/3 | 18/18 |
| AES encryption/decryption 0005 | no | 3/3 | 3/3 | 3/3 | 18/18 |
| AES encryption/decryption 0009 | no | 3/3 | 3/3 | 3/3 | 18/18 |
| AES encryption/decryption 0012 | no | 3/3 | 3/3 | 3/3 | 18/18 |
| heavy friscv 0001 | yes | 3/3 | 3/3 | 3/3 | 18/18 |
| heavy friscv 0005 | yes | 3/3 | 3/3 | 3/3 | 18/18 |
| heavy opene902 0057 | yes | 3/3 | 3/3 | 3/3 | 18/18 |
| AES encryption/decryption 0003 | no | 3/3 | 3/3 | 3/3 | 18/18 |
| heavy opene902 0071 | yes | 3/3 | 3/3 | 3/3 | 18/18 |
| lfsr 0001 | no | 3/3 | 3/3 | 3/3 | 18/18 |



# 8. Why the Benchmark Poorly Measures WavePeek's Strong Use Case

## 8.1. Many Prompts Already Contain the Diagnosis

A substantial share of the tasks tells the agent not only the symptom, but also the specific defects, signals, expected polarity, or complete list of fixes. Examples include:

- `heavy_2dconv` lists output slicing, two missing buffer updates, overwrite instead of accumulation, and a missing center tap;
- `heavy_opene902_0059` describes four specifically inverted or incorrectly composed Boolean expressions;
- the AES and LFSR prompts specify the required algorithm in detail;
- `direct_map_cache` is a specification-driven redesign of a direct-mapped cache into a 2-way associative cache, rather than localization of an unknown temporal bug.

In such tasks, the waveform rarely contains missing information that could change the diagnosis. It serves to confirm an already stated requirement.

## 8.2. Forced Use Adds a Channel Rather Than Replacing an Expensive Baseline Channel

The baseline generally does not manually read enormous VCDs or spend significant context on an alternative waveform workflow. Consequently, WavePeek does not replace an existing expensive analysis method; it adds another one. To measure the savings or utility of a query engine, the baseline must be given the same diagnostic question and an alternative way to answer it.

## 8.3. The Ceiling Effect Hides Grade Differences

In baseline, 11 of 18 tasks produced 3/3 for all three profiles. In the WavePeek branch, 13 of 18 tasks have the same result across all profiles: 12 tasks at 3/3 and one task at 0/3. Therefore, most of the benchmark carries no information about model grade.

This produces an illogical raw baseline ranking: Terra 83.3%, Luna 81.5%, Sol 77.8%. It cannot be interpreted as evidence of the true capability ordering. Five unstable tasks and a few individual attempts determine nearly the entire difference.

## 8.4. The `heavy` Label Does Not Mean Waveform-Centric Diagnosis

| Profile | Group | Baseline | WavePeek | Delta trials |
| --- | --- | ---: | ---: | ---: |
| Luna xhigh | heavy | 18/24 | 21/24 | +3 |
| Luna xhigh | non-heavy | 26/30 | 24/30 | -2 |
| Terra xhigh | heavy | 20/24 | 19/24 | -1 |
| Terra xhigh | non-heavy | 25/30 | 24/30 | -1 |
| Sol high | heavy | 20/24 | 22/24 | +2 |
| Sol high | non-heavy | 22/30 | 24/30 | +2 |

Luna's positive post-hoc signal on heavy tasks is not reproduced by Terra and does not distinguish Sol: Sol improves on both heavy and non-heavy tasks. `heavy` describes project size/complexity, but does not guarantee that the waveform contains unknown causal information.

# 9. What the Study Establishes and What It Does Not

## 9.1. Establishes with High Confidence

1. Forced WavePeek was activated in all treatment trials.
2. Mandatory use increases resource consumption on virtually all tasks and profiles.
3. Binary runtime itself does not explain the overhead.
4. The senior profiles compress the agent loop differently: Terra reduces steps, while Sol reduces text and reasoning per step.
5. The current benchmark is saturated and concentrates errors in three tasks.
6. A blanket "always use WavePeek" policy is not justified for this workload.

## 9.2. Does Not Establish

1. That WavePeek is useless for diagnosis-hidden waveform bugs.
2. How often the model would naturally select the skill if it were not forced.
3. How effective a selective router is.
4. Whether quality with and without WavePeek is equivalent within a predefined margin.
5. Whether Sol provides greater benefit at matched `xhigh`, because Sol was run at `high`.
6. How the result generalizes to other harnesses, models, waveform formats, and real industrial projects.

## 9.3. Forced Is Not a "Utility Ceiling" for a Diagnostic Tool

In JetBrains' Caveman study, forced activation can reasonably be interpreted as an upper bound on savings: the more often the required style is applied, the greater the potential output reduction [3]. For WavePeek, the logic is different. Forced use simultaneously maximizes:

- the probability of use where a waveform is useful;
- the probability of unnecessary use where a waveform adds nothing.

Therefore, the current treatment is not a pure utility ceiling, but a **stress test of the always-use policy**.

## 9.4. The Availability Effect Was Not Measured at All

There is no "tool available, but the model decides whether it is needed" branch between the "tool unavailable" baseline and the "tool mandatory" treatment. JetBrains showed with Ponytail that a skill merely present in the skills folder may not self-activate even once [2]. For WavePeek, natural adoption may be low, reasonably selective, or erroneous—the current data do not distinguish these possibilities.

# 10. Practical Implications for WavePeek

## 10.1. Recommended Policy

> Use WavePeek when an existing or easily generated waveform can answer a specific temporal or signal-level question that may change the diagnosis or patch. Do not use it merely to formally confirm a fix already fully specified by the prompt, and do not apply it as a mandatory ritual to structural or specification-driven tasks.

Minimum routing check before activation:

1. Is there a concrete unknown: first divergence point, handshake acceptance, FSM transition, sampled value, CDC transfer, protocol event?
2. Is a waveform available, or can one be obtained without substantial separate engineering work?
3. Can the answer actually change the patch?
4. Can a bounded query be formulated with a known scope, signal set, or time window?

If the answers to 1-3 are negative, WavePeek should be skipped.

## 10.2. Skill Changes

1. **Shorten the canonical fast path.** One compact recipe: find dump -> `info` -> find scope/signals -> one targeted query -> stop condition.
2. **Do not require help before every nontrivial call.** Help should be a fallback for syntax uncertainty, not a mandatory step.
3. **Explicitly define skip conditions.** The skill should permit the answer "the waveform adds no information" without artificial activation.
4. **Add a stop rule.** After answering the original diagnostic question, do not continue broad exploration without a new uncertainty.
5. **Separate diagnosis and verification.** Before a patch, use WavePeek to find the cause; after a patch, use it only to verify a specific property, rather than reinvestigating the entire design.
6. **Reduce default output.** Support bounded windows, focused signal lists, compact JSON, and a default row limit.

## 10.3. CLI Surface and Instrumentation Changes

1. Reduce the share of help/discovery through more predictable command recipes and examples in the skill itself.
2. Make the most common synchronous recipe easy to copy: clock edge + condition + payload.
3. Log intent or `reason_for_use`: what question the agent was trying to resolve.
4. Log whether use occurred before the first patch/edit and whether the diagnosis changed afterward.
5. Separately count help calls, failed name-resolution calls, truncated output, and repeated equivalent queries.
6. When a task harness is available, provide the agent with the path to a ready waveform and its provenance so that the cost of the query engine is not conflated with the cost of setting up dump generation.

# 11. Recommended Next Experiment

## 11.1. Four Branches

| Branch | What it measures |
| --- | --- |
| A. No WavePeek | clean baseline |
| B. Available, not forced | natural adoption and autonomous model routing |
| C. Selective router | realistic product policy with explicit criteria |
| D. Forced | stress test of maximum exposure and UX tax |

## 11.2. Task Stratification

1. **Diagnosis-hidden waveform tasks.** A failing test and symptom are provided, but the cause is not named. The model must find the first divergence, causal path, violated handshake, or incorrect temporal sequence.
2. **Prescriptive repairs.** The prompt already states the defect; this is the negative-control group for unnecessary waveform ritual.
3. **Static/specification controls.** An architectural or structural task in which the waveform is known not to be the main source of the answer.
4. **Pre-generated waveform tasks.** The dump and its path are ready in advance; query utility is measured without the cost of generation.
5. **Agent-generated waveform tasks.** The full end-to-end workflow is measured, including instrumentation and simulation.

## 11.3. Primary Endpoints

The following should be predefined:

- verifier score / solve rate;
- time-to-first-correct-hypothesis;
- number of incorrect hypotheses before the correct one;
- number of DUT edits before the correct hypothesis;
- fresh input, cache reads, output, and reasoning;
- wall-clock and cost proxy;
- turns, tool calls, and tool-result output;
- activation rate and reason-for-use;
- first meaningful use before/after edit;
- share of cases in which WavePeek changed the diagnosis or patch;
- help/discovery and failed-query rates.

## 11.4. Grade Comparison Design

- use the same reasoning level for all models or a full `model x reasoning` factorial design;
- retain k>=3, but specifically increase the number of distinct diagnosis-centric tasks;
- predefine the primary quality margin if the goal is non-inferiority/equivalence;
- do not base the main conclusion on a post-hoc `heavy` split;
- retain task-paired analysis and symmetric exclusion of infrastructure failures;
- publish the WavePeek usage audit trail and exact revisions.

# 12. Final Verdict

The pooled study of three GPT-5.6 profiles leads to a stronger and more general conclusion than the Luna analysis alone:

> **Mandatory WavePeek creates the same qualitative resource penalty across all model grades. Senior profiles compress the surrounding agent loop in different ways, but do not eliminate the detour or demonstrate a reliable increase in solve rate from the tool on the current benchmark.**

This is a negative result for the **"always use WavePeek"** policy, but not for the WavePeek product or for selective waveform analysis. The current CVDP subset contains too many prescriptive and saturated tasks in which the model already obtains the diagnosis from text. On such a workload, WavePeek more often becomes an expensive post hoc verification step.

The most promising product hypothesis remains open and requires a different evaluation:

> WavePeek should provide the greatest value in diagnosis-hidden tasks where the moment of first divergence, causal signal path, handshake event, or temporal sequence is unknown without the waveform, and a targeted CLI query replaces broad manual investigation.

Until such an experiment is performed, the rational decision is to **keep the tool available, improve routing and UX, abandon global forced use, and evaluate the selective policy separately**.

# Appendix A. Concise Map of Confirmed Findings

| Claim | Status | Basis |
| --- | --- | --- |
| Forced use improves quality | Not supported | pooled +1.9 pp; CI includes 0; sign p~0.55 |
| Forced use increases resource use | Supported | large paired effects and small p-values across all profiles |
| A senior model benefits more from WavePeek | Not supported | effects of +1, -2, +4 trials; no common improved task |
| A senior model runs a shorter trajectory | Partially supported | Terra uses fewer turns; Sol uses less reasoning/output, but not always fewer calls |
| The CLI itself is slow | Refuted | 1.8-3.5 s total over 54 treatment trials |
| Help/discovery is a substantial UX tax | Supported | 30-35% of WavePeek calls |
| There is a task that no model solved | Refuted for pass@any | ensemble covers 18/18 |
| All tasks are solved robustly | Refuted | 2dconv has no configuration >=2/3 |
| Heavy tasks consistently benefit | Not supported | split is not reproduced across profiles |
| WavePeek is useless for diagnosis-hidden bugs | Not studied | too few such tasks in the subset |

# Appendix B. Limitations

1. Only 18 distinct tasks; the statistical unit for paired quality analysis is the task, not 324 independent trials.
2. k=3 reduces stochastic noise, but does not replace a broad task set.
3. Sol uses `high`; Luna and Terra use `xhigh`.
4. Binary pass/fail hides partial progress and diagnosis quality.
5. The post-edit heuristic is approximate.
6. Pi cost proxy is not the actual bill.
7. The selected CVDP subset was not designed for waveform diagnosis.
8. Forced treatment may change the overall strategy more than mere tool availability.
9. Conclusions apply to WavePeek v2.2.0 and the specific skill/CLI version.
10. Real projects may have larger dumps, more complex hierarchies, other simulators, and a different baseline workflow.

# Appendix C. Sources and Artifacts

## Primary Experimental Archives

- `luna-xhigh-experiments-2026-08-10.tar.zst`
- `terra-xhigh-experiments-2026-08-10.tar.zst`
- `sol-high-experiment-2026-08-10.tar.zst`

## Normalized Derived Data

- `wavepeek-three-model-analysis.json`
- `wavepeek-three-model-trials.csv`
- `wavepeek-three-model-task-effects.csv`
- `wavepeek-three-model-quality-effects.csv`

## Methodological References

1. JetBrains AI Blog. [Does "rtk" skill really cut agent tokens by 60-90%? We tested it](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/). Paired analysis, k=3 ladder, adoption instrumentation, per-task medians, and Wilcoxon.
2. JetBrains AI Blog. [Ponytail Skill for Claude Code: Does It Really Cut Agent Code by 54%?](https://blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/). Self-activation, null-vs-equivalence distinction, ceiling/benchmark alignment.
3. JetBrains AI Blog. [Does Speaking to Agents Like Cavemen Really Save 65% of Tokens? We Test](https://blog.jetbrains.com/ai/2026/07/speak-to-ai-agents-like-cavemen-tosave-tokens/). Forced activation and the effect of small samples.
