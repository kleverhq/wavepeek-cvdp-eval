# Experiment 2026-08-10_072737Z_terra-xhigh-aes0012-verifier-clarification_964a66d9

Purpose: compare the selected CVDP cells under baseline and pinned WavePeek treatment through Harbor.

Selection: 1 task(s), 1 model profile(s), 2 arm variant(s), 3 independent attempt(s); expected trials: 6.

| Task | Model | Arm | Attempt | Infrastructure | Benchmark | Runtime (s) | Input | Output | Cache read | Subagents | WavePeek calls / successful / duration |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| cvdp_agentic_AES_encryption_decryption_0012 | openai-codex/gpt-5.6-terra | baseline | 1 | complete | True | 397.933143 | 32873 | 13519 | 173056 | 0 | 0 / 0 / 0.000000s |
| cvdp_agentic_AES_encryption_decryption_0012 | openai-codex/gpt-5.6-terra | baseline | 2 | complete | True | 538.231068 | 76170 | 21905 | 586240 | 0 | 0 / 0 / 0.000000s |
| cvdp_agentic_AES_encryption_decryption_0012 | openai-codex/gpt-5.6-terra | baseline | 3 | complete | True | 514.611649 | 59799 | 17502 | 464896 | 0 | 0 / 0 / 0.000000s |
| cvdp_agentic_AES_encryption_decryption_0012 | openai-codex/gpt-5.6-terra | wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9 | 1 | complete | True | 437.643405 | 53600 | 16024 | 350720 | 0 | 11 / 6 / 0.031409s |
| cvdp_agentic_AES_encryption_decryption_0012 | openai-codex/gpt-5.6-terra | wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9 | 2 | complete | True | 554.23572 | 100678 | 23524 | 1018368 | 1 | 19 / 12 / 0.064007s |
| cvdp_agentic_AES_encryption_decryption_0012 | openai-codex/gpt-5.6-terra | wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9 | 3 | complete | True | 514.483294 | 63694 | 17644 | 615424 | 0 | 12 / 6 / 0.030175s |

Compact result: 6/6 infrastructure-complete, 6/6 benchmark passes, 1 delegated trajectory/trajectories, 42 audited WavePeek calls, 24 successful retained-waveform queries, and 0.125591s total WavePeek CLI time.

Trajectory observation (subagent counts by cell): openai-codex/gpt-5.6-terra baseline=0, openai-codex/gpt-5.6-terra baseline=0, openai-codex/gpt-5.6-terra baseline=0, openai-codex/gpt-5.6-terra wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9=0, openai-codex/gpt-5.6-terra wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9=1, openai-codex/gpt-5.6-terra wavepeek@a27a96b557cb7b9df970fbfef65a5c8354befbc9=0. Delegation was permitted and measured, not forced; exact paths are in summary.json.

Cost conclusion: reported provider cost is unavailable. Pi-calculated catalog values remain raw estimates, not billing evidence.

Conclusion: this output is experiment evidence; small subsets or smoke runs are not statistical evidence of a causal effect.

Raw Harbor artifacts: `experiments/2026-08-10_072737Z_terra-xhigh-aes0012-verifier-clarification_964a66d9/artifacts/harbor/2026-08-10_072737Z_terra-xhigh-aes0012-verifier-clarification_964a66d9`.


## Relationship to the full Terra experiment

This six-trial experiment is a targeted clarification of `experiments/2026-08-10_044313Z_terra-xhigh-full-3x_50674f54/`. It reruns all three baseline and all three WavePeek 2.2.0 attempts for `cvdp_agentic_AES_encryption_decryption_0012` after baseline attempt 1 in the parent experiment hit the former 600-second verifier timeout. These trials retain the 7200-second agent timeout and use a 1800-second verifier timeout. They are follow-up evidence and do not replace the immutable parent result.
