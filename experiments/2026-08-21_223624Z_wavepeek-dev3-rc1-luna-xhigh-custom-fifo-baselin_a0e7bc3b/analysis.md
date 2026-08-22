# Experiment 2026-08-21_223624Z_wavepeek-dev3-rc1-luna-xhigh-custom-fifo-baselin_a0e7bc3b

Purpose: compare the selected CVDP cells under baseline and pinned WavePeek treatment through Harbor.

Selection: 1 task(s), 1 model profile(s), 1 arm variant(s), 1 independent attempt(s); expected trials: 1.

| Task | Model | Arm | Attempt | Infrastructure | Benchmark | Runtime (s) | Input | Output | Cache read | Subagents | WavePeek calls / successful / duration |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| cvdp_agentic_custom_fifo_0004 | openai-codex/gpt-5.6-luna | baseline | 1 | complete | True | 1981.1851 | 207634 | 38733 | 3168256 | 2 | 0 / 0 / 0.000000s |

Compact result: 1/1 infrastructure-complete, 1/1 benchmark passes among infrastructure-complete trials, 2 delegated trajectory/trajectories, 0 audited WavePeek calls, 0 successful waveform queries, and 0.000000s total WavePeek CLI time.

Trajectory observation (subagent counts by cell): openai-codex/gpt-5.6-luna baseline=2. Delegation was permitted and measured, not forced; exact paths are in summary.json.

Cost conclusion: reported provider cost is unavailable. Pi-calculated catalog values remain raw estimates, not billing evidence.

Conclusion: this output is experiment evidence; small subsets or smoke runs are not statistical evidence of a causal effect.

Raw Harbor artifacts: `experiments/2026-08-21_223624Z_wavepeek-dev3-rc1-luna-xhigh-custom-fifo-baselin_a0e7bc3b/artifacts/harbor/2026-08-21_223624Z_wavepeek-dev3-rc1-luna-xhigh-custom-fifo-baselin_a0e7bc3b`.
