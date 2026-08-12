# DeepSeek xhigh × WavePeek CVDP run analysis

Run: [`2026-08-11_071222Z_continuation-2026-08-11-051101z-deepseek-xhigh-f_2c7730ea`](../../experiments/2026-08-11_071222Z_continuation-2026-08-11-051101z-deepseek-xhigh-f_2c7730ea/analysis.md) ([result.json](../../experiments/2026-08-11_071222Z_continuation-2026-08-11-051101z-deepseek-xhigh-f_2c7730ea/result.json))

Model profile: `openrouter/deepseek/deepseek-v4-flash-0731`, reasoning `xhigh`.

## Executive conclusion

The raw result, **43/108 passes (39.8%)**, is not a valid estimate of model quality or WavePeek effect.

The dominant failure mode was upstream model-service instability:

- 354 assistant-generation errors occurred in 79/108 trials.
- 61/108 trials ended with a terminal provider error.
- Those terminal provider errors account for 58 of the 65 benchmark failures (89.2%).
- All 61 terminal provider-error trials were still classified as `infrastructure_status=complete`.
- All 24 AES trials (four tasks × two arms × three attempts) ended with terminal provider errors; none was a clean model attempt.

Only one trial was marked infrastructure-failed: baseline attempt 3 of `heavy_ULX3S_FPGA_Camera_Streaming_0005`, which timed out at 7200 seconds. Its patch nevertheless passed the benchmark verifier.

Therefore the headline 43/108 mostly measures provider availability and the harness classification policy.

## Raw arm-level metrics

| Arm | Passes | Terminal provider errors | Infrastructure complete | Mean input tokens | Mean cache-read tokens | Mean runtime |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 22/54 | 27/54 | 53/54 | 64,604 | 199,495 | 1,056 s |
| WavePeek | 21/54 | 34/54 | 54/54 | 108,094 | 389,850 | 1,122 s |

WavePeek produced 482 recorded CLI invocations, 311 successful meaningful queries, and only 1.761 seconds of cumulative CLI execution time.

The treatment arm generated 994 assistant messages versus 649 in baseline. Under a flaky provider, the longer tool-using trajectory has more opportunities to be interrupted. This is a plausible explanation for 34 terminal errors in treatment versus 27 in baseline.

## Provider failures

| Error type | Count |
|---|---:|
| HTTP 429 (DigitalOcean) | 305 |
| DigitalOcean stream failed | 26 |
| DigitalOcean connection closed | 10 |
| DigitalOcean incomplete transfer | 7 |
| HTTP 429 (Baidu) | 2 |
| HTTP 429 (DeepInfra) | 2 |
| HTTP 429 (StreamLake) | 1 |
| stream ended without finish_reason | 1 |

The 310 HTTP 429 errors came from the shared OpenRouter upstream pool, predominantly DigitalOcean. The remaining transport errors were also predominantly DigitalOcean stream failures.

Among trials with no assistant-generation error, 24/29 passed. Among trials with at least one such error, 19/79 passed. More importantly, among 61 trials whose final assistant message was an error, only 3 patches happened to pass.

## Clean-subset view

“Fully clean” here means: infrastructure complete and no terminal provider error.

| Arm | Fully clean trials | Passes | Pass rate |
|---|---:|---:|---:|
| baseline | 26 | 20 | 76.9% |
| WavePeek | 20 | 19 | 95.0% |
| total | 46 | 39 | 84.8% |

This subset is not random: provider outages were time-clustered and task order was fixed. It must not be promoted as the final benchmark score.

There are 16 task × attempt pairs for which both arms completed without a terminal provider error:

- WavePeek passed 16/16.
- Baseline passed 13/16.
- The three discordant pairs favored WavePeek: `heavy_2dconv-FPGA_0009` attempt 1, `heavy_I2SRV64_0001` attempt 3, and `heavy_friscv_0001` attempt 3.
- No clean matched pair favored baseline.

This is weak but positive evidence; the sample is too selected and too small for a formal treatment estimate.

## Actual cleanly completed failures

| Trial | Task | Arm | Attempt | Failure |
|---|---|---|---:|---|
| `cvdp_agentic_heavy_2dconv-FPGA_0__5Yxngts` | `heavy_2dconv-FPGA_0009` | baseline | 1 | Baseline: неверная signed/saturation арифметика; 7/9 verifier tests failed. |
| `cvdp_agentic_heavy_2dconv-FPGA_0__NwpVUuT` | `heavy_2dconv-FPGA_0009` | baseline | 2 | Baseline: частично исправил арифметику, но остались off-by-one/saturation ошибки; 3/9 tests failed. |
| `cvdp_agentic_heavy_2dconv-FPGA_0__cYv2nfQ` | `heavy_2dconv-FPGA_0009` | baseline | 3 | Baseline: выход схлопнулся к -1; 9/9 tests failed. |
| `cvdp_agentic_heavy_I2SRV64_0001__mkbia3z` | `heavy_I2SRV64_0001` | baseline | 3 | Baseline: неверная длительность/фаза response-done pulses; 2/4 tests failed. |
| `cvdp_agentic_heavy_friscv_0001__tRgu849` | `heavy_friscv_0001` | baseline | 3 | Baseline: переписал блок в 2-state FSM и сломал ожидаемый ready timing; собственная проверка дала ложную уверенность. |
| `cvdp_agentic_heavy_opene902_0059__QbMhszV` | `heavy_opene902_0059` | baseline | 3 | Baseline: не восстановил условие ctrl_dp_ldst_info_buf_reuse; 1/6 tests failed. |
| `cvdp_agentic_heavy_opene902_0059__omXuppX` | `heavy_opene902_0059` | wavepeek | 2 | WavePeek: 29 вызовов (21 meaningful), но то же условие ctrl_dp_ldst_info_buf_reuse осталось неверным; 1/6 tests failed. |

The real model-level failure pattern is therefore narrow:

1. Signed arithmetic, saturation, and cycle alignment in the convolution task.
2. Pulse/handshake timing in DCache arbiter and APB interconnect.
3. One subtle Boolean condition in `cr_lsu_ctrl`.
4. False confidence from custom/visible checks that did not match the hidden verifier.

## WavePeek usage friction

### 1. Schema and JSON-shape friction

The model never invoked `wavepeek schema`.

It did invoke top-level/help commands, and the installed skill explicitly routes exact machine-output questions to help/docs/schema. Nevertheless it repeatedly guessed the JSON shape and piped output into ad hoc Python snippets.

At least 26 WavePeek-containing shell calls across 12 trials ended in downstream parser exceptions:

- `JSONDecodeError`: 12 calls / 7 trials
- `KeyError`: 5 calls / 4 trials
- `TypeError`: 6 calls / 4 trials
- `AttributeError`: 4 calls / 3 trials

Typical incorrect assumptions included `data.rows`, `data.samples`, dictionary `.get()` on an array, and `row.signals` versus the actual command-specific row shape.

This reproduces the previous finding: a global schema endpoint is not an affordance agents use voluntarily. Exact compact examples need to be visible directly in the router skill or command help.

### 2. Command grammar and naming friction

Recorded non-zero WavePeek process exits: 86/482 (17.8%).

Observed mistakes included:

- bare time tokens such as `100000`;
- splitting a token into `0 s`;
- using `210ns` against a dump whose precision is `1s`;
- omitting mandatory `--when` for `extract generic`;
- using invalid capture values such as `matches` and `mismatch`;
- using invalid literals such as `i_valid=='1'`;
- mixing scoped and canonical names;
- querying undumped array/intermediate signals;
- using full nested names like `dut.cnt` while `--scope` required relative names.

WavePeek's fatal diagnostics were generally specific and actionable. The larger problem was that the model often guessed syntax instead of consulting the already-installed help path mandated by the skill.

### 3. Shell-pipeline friction

The model repeatedly used `2>/dev/null`, `2>&1 | head`, and hand-written Python consumers. A WavePeek fatal error leaves stdout empty by design; the downstream JSON parser then reports only `JSONDecodeError`, obscuring the original useful diagnostic.

One recorded `wavepeek -h | head -20` invocation made the real binary exit with status 101, consistent with an unhandled broken pipe. The shell pipeline still appeared successful. This is a genuine CLI robustness issue worth fixing.

### 4. Query thrashing

Some successful trajectories used 30–44 WavePeek calls; one aborted AES trajectory used 65. Repeated or near-repeated queries were common while the model adjusted scope, shape, and post-processing assumptions.

This increases model turns, tokens, and exposure to provider failure. It is not WavePeek computation cost: all 482 CLI calls together took under two seconds.

### 5. Patch pollution

31/108 final patches included generated `.vcd`, `.out`, `.log`, or similar artifacts. The largest patch was 21 MB. This is not specifically a WavePeek bug, but it adds noise, artifact size, and patch-processing overhead. Simulation outputs should be directed outside the tracked worktree or filtered from final patches.

## Per-task raw outcomes and provider-error contamination

| Task | Baseline pass | WavePeek pass | Baseline terminal errors | WavePeek terminal errors |
|---|---:|---:|---:|---:|
| `AES_encryption_decryption_0003` | 0/3 | 0/3 | 3/3 | 3/3 |
| `AES_encryption_decryption_0005` | 0/3 | 0/3 | 3/3 | 3/3 |
| `AES_encryption_decryption_0009` | 0/3 | 0/3 | 3/3 | 3/3 |
| `AES_encryption_decryption_0012` | 0/3 | 0/3 | 3/3 | 3/3 |
| `axis_broadcaster_0001` | 0/3 | 1/3 | 3/3 | 2/3 |
| `custom_fifo_0004` | 1/3 | 2/3 | 2/3 | 1/3 |
| `direct_map_cache_0003` | 2/3 | 2/3 | 1/3 | 1/3 |
| `dual_port_memory_0001` | 3/3 | 2/3 | 0/3 | 1/3 |
| `heavy_2dconv-FPGA_0009` | 0/3 | 1/3 | 0/3 | 2/3 |
| `heavy_I2SRV64_0001` | 1/3 | 2/3 | 1/3 | 1/3 |
| `heavy_ULX3S_FPGA_Camera_Streaming_0005` | 1/3 | 1/3 | 2/3 | 2/3 |
| `heavy_friscv_0001` | 1/3 | 2/3 | 1/3 | 2/3 |
| `heavy_friscv_0005` | 2/3 | 1/3 | 1/3 | 2/3 |
| `heavy_opene902_0057` | 3/3 | 2/3 | 0/3 | 2/3 |
| `heavy_opene902_0059` | 1/3 | 0/3 | 1/3 | 2/3 |
| `heavy_opene902_0071` | 2/3 | 2/3 | 1/3 | 1/3 |
| `lfsr_0001` | 3/3 | 2/3 | 1/3 | 1/3 |
| `monte_carlo_0006` | 2/3 | 1/3 | 1/3 | 2/3 |

## Recommended action order

### P0 — make the run statistically valid

1. Invalidate and rerun the 61 terminal provider-error trials. Do not rerun all 108.
2. Treat a terminal assistant `stopReason=error` with provider/rate-limit/transport metadata as infrastructure failure, not benchmark failure.
3. Retry only infrastructure-failed cells with bounded exponential backoff.
4. For OpenRouter runs, use a provider/BYOK setup with sufficient quota and record the actual serving provider. If provider fallbacks remain disabled for reproducibility, the provider must be pinned and reliable.
5. Reduce concurrency from 4 to 1–2 for a shared rate-limited pool.
6. Rerun the one timeout cell if a fully audit-clean experiment is required, despite its patch passing the verifier.

### P1 — reduce WavePeek interaction friction

1. Put exact minimal JSON examples for `value`, `change`, `property`, and `extract generic` directly in the top-level skill. Do not rely on agents calling the global schema.
2. Recommend `--jsonl` for row-oriented shell processing and include one correct parsing recipe.
3. Add a prominent rule: never suppress stderr or pipe JSON-mode output through `head`; inspect exit status and diagnostics first.
4. Handle broken pipes without Rust panic/exit 101.
5. Keep command-specific schema selection as an optional follow-up, not the primary solution.
6. Route simulation artifacts to `/tmp` or filter generated files from `final.patch`.

## Bottom line

The run does not show that DeepSeek scored roughly half of GPT-5.6, and it does not show that WavePeek hurt performance. It shows that a shared OpenRouter upstream was severely unstable and that the harness currently converts provider outages into benchmark failures.

After excluding aborted cells, the remaining evidence is compatible with a positive WavePeek effect, but the clean matched sample is only 16 pairs. The correct next step is a targeted rerun of invalid cells under reliable provider conditions.
