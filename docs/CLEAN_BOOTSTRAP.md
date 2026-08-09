# Clean-checkout bootstrap evidence

On 2026-08-09, commit `46ab19b` was cloned into a new empty path `/tmp/wavepeek-eval-clean` with no project cache. The host retained only ordinary external prerequisites and Docker's content cache. The following completed without modifying tracked files:

    git clone <local-origin-at-46ab19b> /tmp/wavepeek-eval-clean
    cd /tmp/wavepeek-eval-clean
    just check
    just bootstrap
    just test
    just dry-run smoke
    git status --short --branch

Observed evidence:

    selected.jsonl: 18 rows, sha256=945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d
    CVDP tooling: 8e894cf74414ab1eaea1e2b4e80a02f123df07b6
    CVDP dataset: 5b807d945f6a99aa645f7e43a64a2115e281b4bf
    Harbor: 0348989adffbb43bf0b410fd36197333239633f1 (0.20.0)
    WavePeek: a27a96b557cb7b9df970fbfef65a5c8354befbc9
    Pi: 845d6ff1f6643aba440341cce877ce1c43ebbc39
    pi-subagents: 2966cd5a33c0640de9698b56a39c11f83207a835
    dataset ... files=45
    runner_environment 7095f5ba952d66cd68fd9d15e1375e06cb8d63a0c249add91b8c0e7464110594
    trials=4 tasks=1 models=2 arm_variants=2 attempts=1
    ## master...origin/master

Bootstrap downloaded and verified all 45 locked CVDP dataset/bundle files, reproduced the locked arm image IDs using Docker cache, created the pinned CVDP runner environment, and installed the pinned Harbor checkout. `just test` passed all 17 tests, including traditional/heavy materialization and image isolation. The smoke command was resolved but not launched, so this clean-checkout proof made no model calls.
