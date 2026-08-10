# Experiment 2026-08-10_042702Z_luna-xhigh-monte-carlo-clarification_6cc7fe46

Purpose: compare the selected CVDP cells under baseline and pinned WavePeek treatment through Harbor.

Selection: 1 task(s), 1 model profile(s), 2 arm variant(s), 3 independent attempt(s); expected trials: 6.

| Task | Model | Arm | Attempt | Infrastructure | Benchmark | Runtime (s) | Input | Output | Cache read | Subagents | WavePeek calls / successful / duration |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| cvdp_agentic_monte_carlo_0006 | openai-codex/gpt-5.6-luna | baseline | 1 | complete | False | 314.173938 | 64261 | 15187 | 160768 | 0 | 0 / 0 / 0.000000s |
| cvdp_agentic_monte_carlo_0006 | openai-codex/gpt-5.6-luna | baseline | 2 | complete | False | 539.476972 | 73208 | 26652 | 355840 | 1 | 0 / 0 / 0.000000s |
| cvdp_agentic_monte_carlo_0006 | openai-codex/gpt-5.6-luna | baseline | 3 | complete | False | 645.260814 | 71026 | 30651 | 374784 | 1 | 0 / 0 / 0.000000s |
| cvdp_agentic_monte_carlo_0006 | openai-codex/gpt-5.6-luna | wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9 | 1 | complete | False | 443.841457 | 79904 | 21536 | 439296 | 1 | 20 / 14 / 0.067600s |
| cvdp_agentic_monte_carlo_0006 | openai-codex/gpt-5.6-luna | wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9 | 2 | complete | False | 470.172389 | 111746 | 22601 | 910848 | 0 | 21 / 14 / 0.064954s |
| cvdp_agentic_monte_carlo_0006 | openai-codex/gpt-5.6-luna | wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9 | 3 | complete | False | 845.826348 | 120137 | 41696 | 1033216 | 1 | 18 / 12 / 0.054506s |

Compact result: 6/6 infrastructure-complete, 0/6 benchmark passes, 4 delegated trajectory/trajectories, 59 audited WavePeek calls, 40 successful retained-waveform queries, and 0.187060s total WavePeek CLI time.

Trajectory observation (subagent counts by cell): openai-codex/gpt-5.6-luna baseline=0, openai-codex/gpt-5.6-luna baseline=1, openai-codex/gpt-5.6-luna baseline=1, openai-codex/gpt-5.6-luna wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9=1, openai-codex/gpt-5.6-luna wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9=0, openai-codex/gpt-5.6-luna wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9=1. Delegation was permitted and measured, not forced; exact paths are in summary.json.

Cost conclusion: reported provider cost is unavailable. Pi-calculated catalog values remain raw estimates, not billing evidence.

Conclusion: this output is experiment evidence; small subsets or smoke runs are not statistical evidence of a causal effect.

Raw Harbor artifacts: `experiments/2026-08-10_042702Z_luna-xhigh-monte-carlo-clarification_6cc7fe46/artifacts/harbor/2026-08-10_042702Z_luna-xhigh-monte-carlo-clarification_6cc7fe46`.


## Relationship to the full Luna experiment

This six-trial experiment is a targeted clarification of `experiments/2026-08-09_194827Z_luna-xhigh-full-3x_a0015b2a/`. It reruns all three baseline and all three WavePeek 2.2.0 attempts for `cvdp_agentic_monte_carlo_0006` after WavePeek attempt 3 in the parent experiment hit the former 3600-second agent timeout. These trials use the new 7200-second timeout and must be reported as follow-up evidence rather than silently replacing the original immutable result.
