# Pinned Pi arm images

`agent/Dockerfile` builds two images from one neutral `common` stage:

- `cvdp-pi-agent:baseline` contains the pinned CVDP simulator, Pi, and strict pi-subagents runtime, with no WavePeek binary, skill, docs, path, or environment marker;
- `cvdp-pi-agent:wavepeek-<sha>` adds the WavePeek binary, generated official skill, exported embedded docs, and transparent invocation wrapper from one archived Git commit.

Build the locked WavePeek 2.2.0 images with:

    just build-images

`build_images.py` accepts a clean local WavePeek checkout or repository URL and always builds a deterministic `git archive` of the exact full SHA. Pass `--update-lock` only when intentionally creating a new experiment identity. Temporary source archives are ignored; their hashes and final image IDs are recorded in `experiment.lock.json`.

Harbor-generated task Dockerfiles derive from these images, copy only the agent-visible workspace, install the generic Pi runner, and switch to unprivileged UID/GID 1000 before agent execution. Hidden CVDP tests arrive later through Harbor's `/tests` mount.
