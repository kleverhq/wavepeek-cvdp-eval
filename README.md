# WavePeek × CVDP evaluation lab

A reproducible lab for measuring whether [WavePeek](https://github.com/kleverhq/wavepeek) helps coding agents solve waveform-relevant [CVDP](https://huggingface.co/datasets/NVlabs/CVDP) hardware tasks.

Harbor is the experiment orchestrator. It expands task/model/arm/attempt matrices, runs isolated Pi agents, invokes hidden CVDP verification, and stores raw trials. This repository pins the inputs, builds the baseline and WavePeek treatment images, configures Pi delegation, and normalizes the resulting evidence.

The experiment has two arms:

- **baseline** — Pi and `general-purpose` subagents, with no WavePeek assets or instructions;
- **wavepeek** — the same environment plus one pinned WavePeek binary, skill, documentation, and audited wrapper.

## Requirements

Linux x86-64, Docker, Git, Python 3.12+, [uv](https://docs.astral.sh/uv/), [Just](https://just.systems/), HTTPS access for the first bootstrap, and roughly 20 GB for caches and images.

Pi credentials stay outside the repository. The default file is `~/.pi/agent/auth.json`; override it with:

    export WAVEPEEK_EVAL_AUTH_FILE=/secure/path/auth.json

OpenRouter may instead use `OPENROUTER_API_KEY`. See `docs/models-and-pi.md` for supported profiles and credential behavior.

## Quick start

    just bootstrap          # fetch pinned inputs and build images
    just test               # offline validation
    just dry-run smoke      # resolve the four-cell smoke without model calls
    just preflight smoke    # check credentials, Harbor, and images
    just smoke              # paid: live preflight plus four Harbor trials

Inspect retained evidence with:

    just status latest
    just analyze latest
    just verify latest

Run `just --list` for the complete command interface.

## Documentation

- [Architecture](docs/architecture.md) — components, execution flow, and source-of-truth map.
- [Running experiments](docs/experiments.md) — bootstrap, Harbor runs, selectors, revisions, and operations.
- [Models, Pi, and delegation](docs/models-and-pi.md) — profiles, credentials, Pi, and subagent policy.
- [Reproducibility and evidence](docs/reproducibility.md) — frozen inputs, arm isolation, artifacts, journal, and verification.

Experiment-specific reports live under their dated `experiments/` directory, never in `docs/`.

## License

Apache License 2.0. See `LICENSE`.
