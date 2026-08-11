# Models, Pi, and delegation

## Supported profiles

A model profile fixes the provider, model ID, Pi reasoning level, credential source, and provider compatibility settings. Current profiles are in `config/models/`:

- GPT-5.6 Luna — `medium` and `xhigh`;
- GPT-5.6 Terra — `medium` and `xhigh`;
- GPT-5.6 Sol — `low` and `high`;
- DeepSeek V4 Flash 0731 — `xhigh`;
- GLM 5.2 — `xhigh`;
- Kimi K3 — `max`;
- Qwen3.8 Max — `xhigh`.

All GPT-5.6 profiles use `openai-codex`; the other models use `openrouter` with provider fallback disabled. The smoke and live preflight intentionally use only Luna `xhigh` and DeepSeek `xhigh`. Generic experiment selectors discover every locked `config/models/*.json` profile.

## Credentials

Pi credentials are external. By default, the Harbor adapter reads:

    ~/.pi/agent/auth.json

Override the location without copying credentials into the repository:

    export WAVEPEEK_EVAL_AUTH_FILE=/secure/path/auth.json

An environment-backed profile reads the named variable. The current OpenRouter profile uses:

    export OPENROUTER_API_KEY=...

The auth file must still exist during preflight, even for an environment-only selection; `{}` is sufficient when every selected profile uses an environment key.

Do not hand-author OAuth records in project documentation or configuration. Authenticate with Pi outside this repository. For each trial, `harbor_adapter.py` stages only the selected provider record as a mode-0600 container secret. The host temporary file is removed in a `finally` block; container cleanup is best-effort and the trial environment is ephemeral. Secret values must never appear in Harbor configuration or experiment artifacts.

## Add a model profile

1. Add `config/models/<profile-id>.json`. The filename stem and `id` must match:

       {
         "schema_version": 1,
         "id": "provider-model-reasoning",
         "provider": "provider",
         "model": "model-id",
         "reasoning": "high",
         "credential": {
           "type": "environment",
           "name": "PROVIDER_API_KEY"
         },
         "compat": {}
       }

2. Ensure the provider/model is represented correctly in `config/pi/models-store.json`. This is the offline Pi model catalog copied into both arm images.
3. Add the profile ID to `config/experiment.json` so the declared and discovered profile sets remain identical.
4. Intentionally rebuild images and regenerate `experiment.lock.json`, which records every profile hash:

       python3 scripts/build_images.py --update-lock

5. Validate without model calls:

       just check
       just test
       python3 scripts/lab.py preflight \
         --tasks cvdp_agentic_axis_broadcaster_0001 \
         --models <profile-id> \
         --arms baseline \
         --attempts 1

6. Run a small selected cell when live validation is intended:

       just run cvdp_agentic_axis_broadcaster_0001 \
         <profile-id> baseline 1 default profile-check

Adding a profile does not add it to the fixed smoke or `live-preflight`. Changing those gates requires an intentional code and test change in `scripts/lab.py`.

Supported reasoning values are `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`. `scripts/lab.py check` enforces the profile set and hashes in `experiment.lock.json`; `harbor_adapter.py` then rejects any provider/model/reasoning tuple that does not exactly match a configured profile.

## Pi runtime

Pi is installed in `agent/Dockerfile` at the version pinned by `experiment.lock.json`. Operators do not install or configure a separate Pi inside Harbor trials.

For each trial, `harbor/pi_runner.py` builds an isolated temporary Pi home and:

- copies the offline model catalog and strict subagent settings;
- disables telemetry, update checks, package loading, themes, prompt templates, and project extensions;
- sets project trust to `never`;
- enables only the pinned pi-subagents extension;
- enables the WavePeek skill only in the treatment image;
- retains the main event stream, native session, final response, and usage.

The Harbor adapter validates the final main and child provider/model/reasoning identities, preserves the final Git patch and status, and fails closed on fallback or incomplete evidence.

## pi-subagents policy

The policy is fixed by `config/pi/subagents.json`, `config/experiment.json`, `agent/patch-pi-subagents.py`, and `agent/common/general-purpose.md`:

- only `general-purpose` is exposed;
- built-in fallback agents are disabled;
- children inherit the parent model and reasoning;
- scheduling and nested delegation are disabled;
- maximum depth is one;
- child transcripts and persistent sessions are retained.

This is not an operator-facing extension point. A policy change requires coordinated config/runtime changes, rebuilt images, a regenerated lock, and updated trajectory tests.
