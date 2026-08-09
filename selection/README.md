# CVDP waveform-suitable subset

This directory freezes the first-stage CVDP selection inputs and the selected task manifest. It does not contain solutions or golden patches.

## Fixed source

The audit uses CVDP tooling commit `8e894cf74414ab1eaea1e2b4e80a02f123df07b6` and CVDP v1.1.0 dataset commit `5b807d945f6a99aa645f7e43a64a2115e281b4bf`. `sources.lock.json` records checksums for the three no-commercial JSONL files, the heavy-repository manifest, and all 40 sanitized Git bundles. It also records the exact selection image ID `sha256:b4225673ee3ecc81b6e383ada63929b6b916f75502a85323f5b5d73b29340af2`; the probe refuses a different image.

Only no-solution dataset files are fetched. The generated `subset.jsonl` still contains the evaluator harness required by CVDP, so it is ignored by Git and is never mounted into an agent container.

## Scope and method

The audit covers all 469 open-source code-generation rows that CVDP can run as an agent:

- 92 traditional agentic rows;
- 75 heavy agentic rows;
- 302 non-agentic generation rows supported through `--force-agentic`.

The 123 comprehension rows are excluded because they do not ask the agent to change code. Commercial rows are out of the current simulator scope.

Static review identified 102 tasks with plausible temporal value. Three traditional tasks were then removed because their visible context contained no existing verification material, leaving 99 mechanical probe candidates. None of the 302 forced-agentic rows contains an existing visible testbench, so none passed the same criterion.

The probe uses only agent-visible files. It never mounts the hidden harness or a golden patch. Traditional contexts are compiled with Icarus Verilog in the pinned CVDP simulator image. Heavy contexts are checked out from the sanitized bundles exactly as CVDP exposes them: for ordinary CVDP heavy repositories, only the contents of `external/` are visible. A small shared probe adds waveform dumping but contains no task IDs, expected values, or hidden stimuli.

A task passes only if the requested target source exists, at least one target module is present in the elaborated testbench hierarchy, the visible material compiles, bounded simulation finishes and advances beyond time zero, and a VCD with hierarchy and signals is produced. A timed-out simulation is rejected and its Docker container is killed. Probe workspaces are reset before use and removed afterward. The probe deliberately does not add per-task build adapters. Tasks that require custom repository-specific setup are excluded from the main cohort; this keeps the benchmark simple, prevents task-specific help from leaking into the experiment, and follows KISS/YAGNI.

## Result

Of 99 mechanical candidates:

- 18 passed with a visible simulation and waveform;
- 35 had no generic visible simulation flow;
- 20 did not contain the requested target source before the agent edit;
- 9 failed compilation before simulation;
- 8 heavy contexts had no agent-visible verification material;
- 5 simulated without producing a valid nonzero-time waveform;
- 3 exceeded the bounded simulation timeout;
- 1 did not expose a target or testbench module that could be elaborated.

The frozen subset contains 18 tasks: 10 traditional and 8 heavy. By category, 15 are debugging tasks (`cid016`) and 3 are RTL modification tasks (`cid004`). The preliminary review called out 54 especially strong debugging candidates; 15 of that category survived the stricter agent-visible compile, elaboration, bounded simulation, and waveform checks.

### Traditional

- `cvdp_agentic_AES_encryption_decryption_0003`
- `cvdp_agentic_AES_encryption_decryption_0005`
- `cvdp_agentic_AES_encryption_decryption_0009`
- `cvdp_agentic_AES_encryption_decryption_0012`
- `cvdp_agentic_axis_broadcaster_0001`
- `cvdp_agentic_custom_fifo_0004`
- `cvdp_agentic_direct_map_cache_0003`
- `cvdp_agentic_dual_port_memory_0001`
- `cvdp_agentic_lfsr_0001`
- `cvdp_agentic_monte_carlo_0006`

### Heavy

- `cvdp_agentic_heavy_2dconv-FPGA_0009`
- `cvdp_agentic_heavy_I2SRV64_0001`
- `cvdp_agentic_heavy_ULX3S_FPGA_Camera_Streaming_0005`
- `cvdp_agentic_heavy_friscv_0001`
- `cvdp_agentic_heavy_friscv_0005`
- `cvdp_agentic_heavy_opene902_0057`
- `cvdp_agentic_heavy_opene902_0059`
- `cvdp_agentic_heavy_opene902_0071`

`selected.jsonl` is the compact experiment input intended for version control. `semantic_review.jsonl` contains the pre-model temporal review. `smoke_selection.json` freezes the selected traditional-task probe durations and the deterministic minimum-duration/lexical tie-break winner used by the four-cell smoke test. `inspected.jsonl`, `probes.jsonl`, and `subset.jsonl` are deterministic or rerunnable generated artifacts and are not committed.

## Reproduce

From the repository root:

    python3 scripts/bootstrap.py --component cvdp --verify --heavy-bundles
    python3 scripts/audit_selection.py --all-open-source-generation
    python3 scripts/probe_selection.py
    python3 scripts/audit_selection.py --freeze
    python3 scripts/audit_selection.py --check-reproducible

The expected summary is:

    inspected=469 native=167 forced=302 semantic_candidates=99 selected=18

The selected manifest SHA-256 is:

    945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d
