# Accepted four-cell smoke analysis

Run `20260809T160628Z-fbb99664` is the accepted infrastructure smoke for `cvdp_agentic_axis_broadcaster_0001`. It was launched non-interactively through `just smoke` from repository commit `e37a185f4cd3a835225ef8d377f92b9d13541614`. Harbor commit `0348989adffbb43bf0b410fd36197333239633f1` expanded exactly one task × two models × two arms × one attempt into four trials, with four-way concurrency and zero retries. All four trials completed without infrastructure exceptions and passed exact provider/model/`xhigh` validation.

The bound live preflight is `experiments/2026-08-09_160543Z_preflight_51062efd/`. For each model, one parent launched exactly one `general-purpose` child; parent and child sessions reported the same exact provider/model and `xhigh`. The smoke itself permitted but did not force delegation. Its `result.json` records SHA-256 for all 106 preflight files (proof SHA-256 `b189df65f5bb672096ba7052dacb56e41b9f37c19fdf43b7ab029c36094428d8`).

## Results

| Model | Arm | Benchmark | Runtime | Input | Output | Cache read | Subagents | WavePeek calls / duration |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.6 Luna | baseline | failed | 548.34 s | 68,564 | 25,990 | 145,408 | 1 | 0 / 0 s |
| GPT-5.6 Luna | WavePeek 2.2.0 | passed | 2,689.91 s | 189,591 | 145,683 | 1,463,808 | 0 | 13 / 0.081263 s |
| DeepSeek V4 Flash 0731 | baseline | failed | 583.81 s | 110,931 | 43,911 | 577,792 | 0 | 0 / 0 s |
| DeepSeek V4 Flash 0731 | WavePeek 2.2.0 | passed | 502.48 s | 123,140 | 36,263 | 783,104 | 0 | 13 / 0.048065 s |

Both treatment trials made successful, audited queries against retained VCD files and passed the hidden CVDP verifier. Both baseline trials produced no WavePeek calls and failed the hidden verifier. The Luna baseline delegated once; the other three cells did not delegate. Thus delegation behavior was observed and retained rather than forced or balanced after the fact.

Every cell retains its final binary patch, Git status, full verifier stdout/reward, main Pi event stream and native session, any child transcript/session, usage fields, and waveform snapshots. The initial accepted manifest referenced the generated `.cache` task dataset rather than copying it into the run. Before that cache changed, both task variants were archived under `artifacts/tasks/`; Harbor `Packager.compute_content_hash` exactly matched all accepted trial-lock digests. `tasks.json` records those content digests and archive hashes. Future runs execute directly from their retained `experiments/<date_name_id>/artifacts/inputs/tasks` snapshot. Treatment records include working directory, exact argv, start/end timestamps, duration, exit status, source and retained waveform hashes, and the pinned binary hash. WavePeek was built at commit `a27a96b557cb7b9df970fbfef65a5c8354befbc9`; binary, generated skill, exported docs, source archive, and image identities are in `artifacts/manifest.json`.

`reported_cost` is unavailable for these profiles. Raw Pi catalog calculations are retained as `pi_calculated_cost`, but they are not provider billing records and are not used as monetary conclusions—especially for subscription-backed Codex OAuth.

## Interpretation

This is an infrastructure proof, not a statistically meaningful performance result. The observed pass delta is +1 for treatment in each model's single comparison, but four trials cannot establish causality or generalize to the 18-task cohort. Luna treatment also used substantially more runtime and tokens, while DeepSeek treatment used less runtime but more input/cache-read tokens. A defensible performance claim requires the preregistered multi-attempt cohort.

The earlier four-cell run `20260809T155016Z-1eaebab4` remains journaled as rejected because its first normalizer used the wrong Harbor artifact destination and did not guarantee retention of a temporary waveform. It is excluded from the results above.

## Integrity pointers

- Manifest SHA-256: `69bffd270e29d1d21c0e03f9412c9e1f401482e62e4e647d5751a4c424cbffc4`
- Summary SHA-256: `fea7b0fd0a734a439cc4b99800b0656e2f9687ba3e06e556844e4fa1cf716573`
- Analysis SHA-256: `16785f4b5f2317d692dcf1f0c67b837825521b019dc8b46c17ee052588a80ca9`
- Run-checksum manifest SHA-256: `c1e9fd4b8caf749d061ccc37770c1a730ec45c1b7b933d827c019e9ec3ecae7a`
- `python3 scripts/lab.py verify 20260809T160628Z-fbb99664` verified all 230 retained run files and the bound live-preflight marker.
