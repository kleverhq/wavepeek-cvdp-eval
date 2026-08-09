#!/usr/bin/env python3
"""Validate frozen inputs and materialize CVDP tasks for Harbor."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / "selection" / "selected.jsonl"
SOURCES_LOCK = ROOT / "selection" / "sources.lock.json"
EXPERIMENT_LOCK = ROOT / "experiment.lock.json"
CONFIG = ROOT / "config" / "experiment.json"
CACHE = ROOT / ".cache"
EXPERIMENTS = ROOT / "experiments"
SELECTED_SHA256 = "945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d"
HARBOR_COMMIT = "0348989adffbb43bf0b410fd36197333239633f1"
WAVEPEEK_INSTRUCTION = (
    "Use the installed WavePeek skill and CLI to inspect waveform behavior while "
    "solving this task. You must run WavePeek meaningfully against a task waveform "
    "before finalizing the solution."
)
REQUIRED_MODEL_IDS = {
    "openai-codex-gpt-5.6-luna-xhigh": "openai-codex/gpt-5.6-luna",
    "openrouter-deepseek-v4-flash-0731-xhigh": "openrouter/deepseek/deepseek-v4-flash-0731",
}


def load_model_profiles() -> dict[str, dict]:
    profiles = {}
    for path in sorted((ROOT / "config" / "models").glob("*.json")):
        profile = json.loads(path.read_text())
        profiles[profile["id"]] = profile
    return profiles


MODEL_PROFILES = load_model_profiles()
MODEL_IDS = {
    key: f"{profile['provider']}/{profile['model']}"
    for key, profile in MODEL_PROFILES.items()
}
SMOKE_MODELS = list(REQUIRED_MODEL_IDS)
HARBOR_SOURCE = CACHE / "harbor" / "source"
JOURNAL = EXPERIMENTS / "JOURNAL.jsonl"


def new_experiment_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "experiment"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")
    return f"{timestamp}_{slug}_{secrets.token_hex(4)}"


def experiment_artifacts(experiment_id: str) -> Path:
    return EXPERIMENTS / experiment_id / "artifacts"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result.stdout.strip()


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{number}: {error}") from error
    return rows


def selected_rows() -> list[dict]:
    actual = sha256(SELECTION)
    if actual != SELECTED_SHA256:
        raise ValueError(
            f"selected.jsonl digest mismatch: expected {SELECTED_SHA256}, got {actual}"
        )
    rows = read_jsonl(SELECTION)
    ids = [row.get("id") for row in rows]
    if len(rows) != 18 or len(ids) != len(set(ids)):
        raise ValueError("selected.jsonl must contain exactly 18 unique tasks")
    if any(row.get("execution_mode") != "native" for row in rows):
        raise ValueError("every selected task must use native execution mode")
    if sum(row.get("split") == "traditional" for row in rows) != 10:
        raise ValueError("selected.jsonl must contain 10 traditional tasks")
    if sum(row.get("split") == "heavy" for row in rows) != 8:
        raise ValueError("selected.jsonl must contain 8 heavy tasks")
    return rows


def check() -> None:
    rows = selected_rows()
    source_lock = json.loads(SOURCES_LOCK.read_text())
    experiment_lock = json.loads(EXPERIMENT_LOCK.read_text())
    config = json.loads(CONFIG.read_text())

    configured_profiles = set(MODEL_PROFILES)
    if set(config["models"]) != configured_profiles:
        raise ValueError("config/experiment.json models must match config/models profiles")
    locked_profiles = set(experiment_lock["model_configs"])
    if locked_profiles != configured_profiles:
        raise ValueError(
            f"model profile lock mismatch: configured={sorted(MODEL_PROFILES)}, locked={sorted(locked_profiles)}"
        )

    pinned_files = {
        SOURCES_LOCK: experiment_lock["cvdp"]["sources_lock_sha256"],
        ROOT / experiment_lock["cvdp"]["runner_requirements_path"]: experiment_lock["cvdp"]["runner_requirements_sha256"],
        CONFIG: experiment_lock["experiment_config_sha256"],
        ROOT / experiment_lock["pi"]["model_catalog_path"]: experiment_lock["pi"]["model_catalog_sha256"],
        ROOT / experiment_lock["pi_subagents"]["project_isolation_patch"]: experiment_lock["pi_subagents"]["project_isolation_patch_sha256"],
        ROOT / experiment_lock["pi_subagents"]["settings_path"]: experiment_lock["pi_subagents"]["settings_sha256"],
    }
    for profile_id, expected in experiment_lock["model_configs"].items():
        pinned_files[ROOT / "config" / "models" / f"{profile_id}.json"] = expected
    for path, expected in pinned_files.items():
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"pinned file digest mismatch for {path.relative_to(ROOT)}: expected {expected}, got {actual}")

    expected_revisions = {
        "CVDP tooling": source_lock["tooling"]["commit"],
        "CVDP dataset": source_lock["dataset"]["commit"],
        "Harbor": config["harbor_commit"],
        "WavePeek": experiment_lock["wavepeek"]["commit"],
        "Pi": experiment_lock["pi"]["commit"],
        "pi-subagents": experiment_lock["pi_subagents"]["commit"],
    }
    for name, revision in expected_revisions.items():
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError(f"{name} revision is not a full lowercase Git SHA: {revision}")
    if config["harbor_commit"] != HARBOR_COMMIT:
        raise ValueError("unexpected Harbor revision")
    if experiment_lock["wavepeek"]["commit"] != "a27a96b557cb7b9df970fbfef65a5c8354befbc9":
        raise ValueError("WavePeek 2.2.0 commit mismatch")
    if experiment_lock["wavepeek"]["version_output"] != "wavepeek v2.2.0":
        raise ValueError("WavePeek version output mismatch")
    if experiment_lock["cvdp"]["selected_manifest_sha256"] != SELECTED_SHA256:
        raise ValueError("experiment lock has the wrong selected manifest digest")

    profiles = {}
    for path in sorted((ROOT / "config" / "models").glob("*.json")):
        profile = json.loads(path.read_text())
        profiles[profile["id"]] = f"{profile['provider']}/{profile['model']}"
    if profiles != MODEL_IDS:
        raise ValueError(f"model profile discovery mismatch: {profiles}")
    for profile_id, expected_model in REQUIRED_MODEL_IDS.items():
        if profiles.get(profile_id) != expected_model or MODEL_PROFILES[profile_id]["reasoning"] != "xhigh":
            raise ValueError(f"required model profile mismatch: {profile_id}")
    if json.loads((ROOT / "config" / "models" / "openrouter-deepseek-v4-flash-0731-xhigh.json").read_text())["compat"]["openRouterRouting"]["allow_fallbacks"] is not False:
        raise ValueError("OpenRouter fallbacks must be disabled")

    subagents = config["subagents"]
    required = {
        "fallbackSubagent": "none",
        "disableDefaultAgents": True,
        "scopeModels": True,
        "schedulingEnabled": False,
        "maxSubagentDepth": 1,
        "outputTranscript": True,
    }
    if any(subagents.get(key) != value for key, value in required.items()):
        raise ValueError("pi-subagents policy is not strict")

    print(f"selected.jsonl: {len(rows)} rows, sha256={SELECTED_SHA256}")
    for name, revision in expected_revisions.items():
        print(f"{name}: {revision}")
    print("inputs: verified")


def dataset_dir() -> Path:
    return CACHE / "cvdp" / "dataset"


def verified_source_lock() -> dict:
    expected = json.loads(EXPERIMENT_LOCK.read_text())["cvdp"]["sources_lock_sha256"]
    actual = sha256(SOURCES_LOCK)
    if actual != expected:
        raise ValueError(f"sources.lock.json digest mismatch: expected {expected}, got {actual}")
    return json.loads(SOURCES_LOCK.read_text())


def full_row(selection: dict) -> dict:
    filename = {
        "traditional": "cvdp_v1.1.0_agentic_code_generation_no_commercial.jsonl",
        "heavy": "cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl",
    }[selection["split"]]
    path = dataset_dir() / filename
    if not path.is_file():
        raise RuntimeError(f"missing CVDP input {path}; run `just bootstrap` first")
    expected = verified_source_lock()["dataset"]["files"][filename]
    if sha256(path) != expected:
        raise ValueError(f"pinned CVDP dataset file digest mismatch: {filename}")
    for row in read_jsonl(path):
        if row.get("id") == selection["id"]:
            if hashlib.sha256(row["prompt"].encode()).hexdigest() != selection["prompt_sha256"]:
                raise ValueError(f"prompt digest mismatch for {selection['id']}")
            return row
    raise ValueError(f"selected task is absent from its pinned CVDP split: {selection['id']}")


def copy_visible(selection: dict, row: dict, destination: Path) -> None:
    if selection["split"] == "traditional":
        for relative, content in row["context"].items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        return

    repository = selection["repository"]
    bundle = dataset_dir() / "cvdp_v1.1.0_agentic_heavy_code_generation_public" / f"{repository['repo']}.bundle"
    if not bundle.is_file():
        raise RuntimeError(f"missing sanitized heavy bundle {bundle}; run `just bootstrap` first")
    relative_bundle = bundle.relative_to(dataset_dir()).as_posix()
    expected = verified_source_lock()["dataset"]["files"][relative_bundle]
    if sha256(bundle) != expected:
        raise ValueError(f"pinned heavy bundle digest mismatch: {relative_bundle}")
    with tempfile.TemporaryDirectory(dir=CACHE) as directory:
        checkout = Path(directory) / "repository"
        run(["git", "clone", "--quiet", str(bundle), str(checkout)])
        run(["git", "checkout", "--quiet", "--detach", repository["commit"]], checkout)
        external = checkout / "external"
        if not external.is_dir():
            raise ValueError(f"heavy repository has no agent-visible external/ root: {selection['id']}")
        shutil.copytree(external, destination, dirs_exist_ok=True, symlinks=False)


def verifier_script() -> str:
    return """#!/bin/sh
set -eu
mkdir -p /app/rundir /logs/verifier
python3 - <<'PY'
import os
import subprocess
from pathlib import Path

env = os.environ.copy()
for raw in Path('/tests/src/.env').read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    env[key.strip()] = value.strip()
env['PYTHONPATH'] = '/tests/src'
result = subprocess.run(
    ['pytest', '-s', '--log-cli-level=INFO', '-o', 'cache_dir=/app/rundir/.cache', '/tests/src/test_runner.py', '-v'],
    cwd='/app/rundir', env=env,
)
Path('/logs/verifier/reward.txt').write_text('1\\n' if result.returncode == 0 else '0\\n')
PY
"""


def task_toml(
    name: str,
    task_id: str,
    arm: str,
    agent_timeout: int = 3600,
    verifier_timeout: int = 600,
) -> str:
    return f'''schema_version = "1.4"

[task]
name = "cvdp-eval/{name}"
version = "1.0.0"
authors = []
keywords = ["cvdp", "hardware-debug", "{arm}"]

[metadata]
author_name = "CVDP integration"
author_email = ""
difficulty = "unknown"
category = "hardware-verification"
tags = ["{task_id}", "{arm}"]

[verifier]
timeout_sec = {float(verifier_timeout)}

[agent]
timeout_sec = {float(agent_timeout)}

[environment]
build_timeout_sec = 1800.0
cpus = 4
memory_mb = 8192
storage_mb = 20480
gpus = 0
mcp_servers = []

[verifier.env]

[solution.env]
'''


def environment_dockerfile(image: str) -> str:
    return f'''FROM {image}
USER root
ENTRYPOINT []
CMD ["/bin/sh"]
RUN rm -rf /code /src && mkdir -p /app /run/secrets \
    && ln -s /app /code && ln -s /tests/src /src
COPY workspace/ /app/
COPY harbor-pi-runner.py /opt/cvdp-pi/harbor-pi-runner.py
RUN chmod 0755 /opt/cvdp-pi/harbor-pi-runner.py \
    && git init --separate-git-dir=/opt/cvdp-baseline /app \
    && git --git-dir=/opt/cvdp-baseline --work-tree=/app config user.name cvdp-eval \
    && git --git-dir=/opt/cvdp-baseline --work-tree=/app config user.email cvdp-eval@invalid \
    && git --git-dir=/opt/cvdp-baseline --work-tree=/app add -A \
    && git --git-dir=/opt/cvdp-baseline --work-tree=/app commit -q --allow-empty -m baseline \
    && chown -R 1000:1000 /app /run/secrets \
    && chmod -R u+rwX,go+rX /app \
    && chmod -R a-w /opt/cvdp-baseline
USER 1000:1000
WORKDIR /app
'''


def materialize(
    task_id: str,
    arm: str,
    output_root: Path | None = None,
    treatment_lock: dict | None = None,
    agent_timeout: int = 3600,
    verifier_timeout: int = 600,
) -> Path:
    if arm not in {"baseline", "wavepeek"}:
        raise ValueError("arm must be baseline or wavepeek")
    selection = next((row for row in selected_rows() if row["id"] == task_id), None)
    if selection is None:
        raise ValueError(f"task is not in the frozen selection: {task_id}")
    row = full_row(selection)
    default_lock = json.loads(EXPERIMENT_LOCK.read_text())
    lock = treatment_lock or default_lock
    image = (default_lock if arm == "baseline" else lock)["images"][arm]["tag"]
    short = lock["wavepeek"]["commit"][:12]
    arm_id = "baseline" if arm == "baseline" else f"wavepeek-{short}"
    root = output_root or CACHE / "harbor" / "tasks" / short
    destination = root / f"{task_id}--{arm_id}"
    temporary = destination.with_name(destination.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    (temporary / "environment" / "workspace").mkdir(parents=True)
    (temporary / "tests").mkdir(parents=True)

    copy_visible(selection, row, temporary / "environment" / "workspace")
    for target_file in selection["target_files"]:
        if not (temporary / "environment" / "workspace" / target_file).is_file():
            raise ValueError(f"selected target file is not agent-visible: {task_id}:{target_file}")
    for relative, content in row["harness"].items():
        target = temporary / "tests" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    prompt = row["prompt"]
    instruction = row["system_message"] + "\n\n" + prompt
    if arm == "wavepeek":
        instruction += "\n\n" + WAVEPEEK_INSTRUCTION
    (temporary / "instruction.md").write_text(instruction)
    (temporary / "task.toml").write_text(
        task_toml(destination.name, task_id, arm_id, agent_timeout, verifier_timeout)
    )
    (temporary / "environment" / "Dockerfile").write_text(environment_dockerfile(image))
    shutil.copyfile(ROOT / "harbor" / "pi_runner.py", temporary / "environment" / "harbor-pi-runner.py")
    test_script = temporary / "tests" / "test.sh"
    test_script.write_text(verifier_script())
    test_script.chmod(0o755)
    metadata = {
        "schema_version": 1,
        "task_id": task_id,
        "arm": arm,
        "prompt_sha256": selection["prompt_sha256"],
        "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
        "wavepeek_commit": lock["wavepeek"]["commit"] if arm == "wavepeek" else None,
        "source_split": selection["split"],
    }
    (temporary / "task-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    forbidden_names = {"solution", "golden.patch", "patch.json"}
    if any(path.name.lower() in forbidden_names for path in temporary.rglob("*")):
        raise ValueError("generated task contains a forbidden solution artifact")
    if arm == "baseline":
        baseline_text = "\n".join(
            path.read_text(errors="ignore")
            for path in temporary.rglob("*")
            if path.is_file() and path.name not in {"task-metadata.json"}
        ).lower()
        if "wavepeek" in baseline_text:
            raise ValueError("baseline task contains a WavePeek reference")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(destination, ignore_errors=True)
    temporary.replace(destination)
    print(destination)
    return destination


def harbor_bootstrap() -> None:
    if not HARBOR_SOURCE.exists():
        HARBOR_SOURCE.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", "https://github.com/harbor-framework/harbor.git", str(HARBOR_SOURCE)])
    if not (HARBOR_SOURCE / ".git").is_dir():
        raise RuntimeError(f"Harbor cache is not a Git checkout: {HARBOR_SOURCE}")
    run(["git", "fetch", "--quiet", "origin", HARBOR_COMMIT], HARBOR_SOURCE)
    run(["git", "checkout", "--quiet", "--detach", HARBOR_COMMIT], HARBOR_SOURCE)
    if run(["git", "status", "--porcelain"], HARBOR_SOURCE):
        raise RuntimeError("pinned Harbor checkout is dirty")
    run(["uv", "sync", "--no-dev"], HARBOR_SOURCE)
    version = run(["uv", "run", "--no-dev", "harbor", "--version"], HARBOR_SOURCE)
    print(f"Harbor: {HARBOR_COMMIT} ({version})")


def resolve_wavepeek_revision(spec: str) -> dict:
    default = json.loads(EXPERIMENT_LOCK.read_text())
    if spec == "default":
        return default
    if "#" in spec:
        source, revision = spec.rsplit("#", 1)
    elif re.fullmatch(r"[0-9a-f]{40}", spec):
        source, revision = default["wavepeek"]["repository"], spec
    else:
        source, revision = spec, "HEAD"
    local = Path(source).expanduser()
    if local.is_dir():
        checkout = local.resolve()
        if run(["git", "status", "--porcelain"], checkout):
            raise ValueError(f"local WavePeek checkout is dirty: {checkout}")
    else:
        cache_key = hashlib.sha256(source.encode()).hexdigest()[:16]
        checkout = CACHE / "wavepeek" / "sources" / cache_key
        if not checkout.exists():
            checkout.parent.mkdir(parents=True, exist_ok=True)
            run(["git", "clone", "--quiet", source, str(checkout)])
        run(["git", "fetch", "--quiet", "origin"], checkout)
    try:
        commit = run(["git", "rev-parse", f"{revision}^{{commit}}"], checkout)
    except RuntimeError:
        if local.is_dir():
            raise
        commit = run(["git", "rev-parse", f"origin/{revision}^{{commit}}"], checkout)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError(f"could not resolve WavePeek revision {spec}")
    if commit == default["wavepeek"]["commit"]:
        return default
    manifest = CACHE / "wavepeek" / commit / "manifest.json"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_images.py"),
        "--wavepeek-repo", str(checkout),
        "--wavepeek-sha", commit,
        "--allow-unlocked",
        "--output-manifest", str(manifest),
    ]
    run(command, ROOT)
    resolved = json.loads(manifest.read_text())
    if resolved["wavepeek"]["commit"] != commit:
        raise RuntimeError("candidate WavePeek build manifest commit mismatch")
    return resolved


def split_selector(value: str, allowed: list[str], label: str) -> list[str]:
    if value == "all":
        return allowed
    requested = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(requested) - set(allowed))
    if not requested or unknown:
        raise ValueError(f"invalid {label} selector; unknown={unknown}, allowed={allowed}")
    return requested


def resolve_matrix(args: argparse.Namespace) -> dict:
    rows = selected_rows()
    smoke = getattr(args, "selector", None) == "smoke"
    if smoke:
        task_ids = ["cvdp_agentic_axis_broadcaster_0001"]
        model_keys = SMOKE_MODELS
        arms = ["baseline", "wavepeek"]
        attempts = 1
        revision_specs = ["default"]
    else:
        task_ids = split_selector(args.tasks, [row["id"] for row in rows], "task")
        model_keys = split_selector(args.models, list(MODEL_IDS), "model")
        arms = split_selector(args.arms, ["baseline", "wavepeek"], "arm")
        attempts = int(args.attempts)
        revision_specs = [item.strip() for item in args.revisions.split(",") if item.strip()]
    if attempts < 1:
        raise ValueError("attempts must be positive")
    config = json.loads(CONFIG.read_text())
    concurrency = int(getattr(args, "concurrency", None) or config["default_concurrency"])
    agent_timeout = int(getattr(args, "agent_timeout", None) or config["agent_timeout_seconds"])
    verifier_timeout = int(getattr(args, "verifier_timeout", None) or config["evaluator_timeout_seconds"])
    if min(concurrency, agent_timeout, verifier_timeout) < 1:
        raise ValueError("concurrency and timeouts must be positive")
    reasoning_by_profile = {
        key: MODEL_PROFILES[key]["reasoning"]
        for key in model_keys
    }
    treatment_locks = [resolve_wavepeek_revision(spec) for spec in revision_specs] if "wavepeek" in arms else []
    commits = [lock["wavepeek"]["commit"] for lock in treatment_locks]
    if len(commits) != len(set(commits)):
        raise ValueError(f"WavePeek revision selectors resolve to duplicate commits: {commits}")
    arm_variants = int("baseline" in arms) + len(treatment_locks)
    count = len(task_ids) * len(model_keys) * arm_variants * attempts
    if smoke and count != 4:
        raise ValueError(f"smoke matrix must contain exactly four trials, resolved {count}")
    return {
        "tasks": task_ids,
        "models": model_keys,
        "model_ids": [MODEL_IDS[key] for key in model_keys],
        "arms": arms,
        "arm_variants": arm_variants,
        "attempts": attempts,
        "concurrency": min(concurrency, count),
        "agent_timeout_seconds": agent_timeout,
        "verifier_timeout_seconds": verifier_timeout,
        "trial_count": count,
        "reasoning": next(iter(set(reasoning_by_profile.values()))) if len(set(reasoning_by_profile.values())) == 1 else "mixed",
        "reasoning_by_profile": reasoning_by_profile,
        "wavepeek_revisions": commits,
        "wavepeek_selectors": [
            {
                "requested": spec,
                "resolved_commit": lock["wavepeek"]["commit"],
                "repository": lock["wavepeek"]["repository"],
            }
            for spec, lock in zip(revision_specs, treatment_locks)
        ],
        "wavepeek_builds": treatment_locks,
    }


def materialize_dataset(matrix: dict) -> Path:
    identity = hashlib.sha256(
        json.dumps(
            {"tasks": matrix["tasks"], "arms": matrix["arms"], "revisions": matrix["wavepeek_revisions"]},
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    root = CACHE / "harbor" / "datasets" / identity
    temporary = root.with_name(root.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    for task_id in matrix["tasks"]:
        if "baseline" in matrix["arms"]:
            materialize(
                task_id, "baseline", temporary,
                agent_timeout=matrix.get("agent_timeout_seconds", 3600),
                verifier_timeout=matrix.get("verifier_timeout_seconds", 600),
            )
        if "wavepeek" in matrix["arms"]:
            for treatment_lock in matrix["wavepeek_builds"]:
                materialize(
                    task_id, "wavepeek", temporary, treatment_lock,
                    matrix.get("agent_timeout_seconds", 3600),
                    matrix.get("verifier_timeout_seconds", 600),
                )
    root.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(root, ignore_errors=True)
    temporary.replace(root)
    return root


def resolved_job(matrix: dict, name: str) -> tuple[dict, list[str]]:
    source_dataset = materialize_dataset(matrix)
    run_id = new_experiment_id(name)
    experiment_dir = EXPERIMENTS / run_id
    run_dir = experiment_dir / "artifacts"
    harbor_dir = run_dir / "harbor"
    execution_dataset = run_dir / "inputs" / "tasks"
    job_config_path = run_dir / "harbor-job.json"
    job_config = {
        "job_name": run_id,
        "jobs_dir": str(harbor_dir),
        "n_attempts": matrix["attempts"],
        "n_concurrent_trials": matrix["concurrency"],
        "retry": {"max_retries": 0},
        "agents": [
            {
                "name": "harbor_adapter:ReproduciblePi",
                "model_name": MODEL_IDS[profile_id],
                "kwargs": {
                    "version": "0.83.0",
                    "thinking": MODEL_PROFILES[profile_id]["reasoning"],
                },
            }
            for profile_id in matrix["models"]
        ],
        "datasets": [{"path": str(execution_dataset)}],
    }
    command = [
        "uv", "run", "--no-dev", "--project", str(HARBOR_SOURCE),
        "harbor", "jobs", "start", "--config", str(job_config_path),
    ]
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_dir": str(experiment_dir.relative_to(ROOT)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "resolved",
        "matrix": matrix,
        "task_dataset_source": str(source_dataset.relative_to(ROOT)),
        "task_dataset": str(execution_dataset.relative_to(ROOT)),
        "retained_task_dataset": str(execution_dataset.relative_to(run_dir)),
        "harbor_commit": HARBOR_COMMIT,
        "harbor_job_dir": str(harbor_dir.relative_to(ROOT)),
        "harbor_job_name": run_id,
        "harbor_job_config": str(job_config_path.relative_to(run_dir)),
        "resolved_harbor_job": job_config,
        "agent": "harbor_adapter:ReproduciblePi",
        "pi_commit": json.loads(EXPERIMENT_LOCK.read_text())["pi"]["commit"],
        "pi_subagents_commit": json.loads(EXPERIMENT_LOCK.read_text())["pi_subagents"]["commit"],
        "selection_sha256": SELECTED_SHA256,
        "command": command,
    }
    return manifest, command


def check_credentials(matrix: dict) -> Path:
    auth = Path(os.environ.get("WAVEPEEK_EVAL_AUTH_FILE", "~/.pi/agent/auth.json")).expanduser().resolve()
    if not auth.is_file():
        raise RuntimeError(f"Pi credential file is missing: {auth}")
    records = json.loads(auth.read_text())
    missing = []
    for key in matrix["models"]:
        profile = MODEL_PROFILES[key]
        provider = profile["provider"]
        credential = profile.get("credential") or {}
        environment_name = credential.get("name") if credential.get("type") == "environment" else None
        if provider not in records and not (environment_name and os.environ.get(environment_name)):
            missing.append(provider)
    missing = sorted(set(missing))
    if missing:
        raise RuntimeError(f"credential file is missing provider records: {missing}")
    return auth


def preflight(matrix: dict) -> None:
    check()
    check_credentials(matrix)
    harbor_bootstrap()
    lock = json.loads(EXPERIMENT_LOCK.read_text())
    image_records = []
    if "baseline" in matrix["arms"]:
        image_records.append(("baseline", lock["images"]["baseline"]))
    image_records.extend(
        (f"wavepeek@{candidate['wavepeek']['commit']}", candidate["images"]["wavepeek"])
        for candidate in matrix["wavepeek_builds"]
    )
    for label, image in image_records:
        expected = image["id"]
        actual = run(["docker", "image", "inspect", image["tag"], "--format", "{{.Id}}"])
        if actual != expected:
            raise RuntimeError(f"{label} image mismatch: expected {expected}, got {actual}")
    print(
        f"preflight: trials={matrix['trial_count']} tasks={len(matrix['tasks'])} "
        f"models={len(matrix['models'])} arm_variants={matrix['arm_variants']} attempts={matrix['attempts']}"
    )


def preflight_identity() -> str:
    lock = json.loads(EXPERIMENT_LOCK.read_text())
    value = {
        "harbor": HARBOR_COMMIT,
        "images": lock["images"],
        "pi": lock["pi"],
        "pi_subagents": lock["pi_subagents"],
        "models": REQUIRED_MODEL_IDS,
        "reasoning": "xhigh",
        "runtime_files": {
            "harbor/pi_runner.py": sha256(ROOT / "harbor" / "pi_runner.py"),
            "harbor_adapter.py": sha256(ROOT / "harbor_adapter.py"),
            "scripts/lab.py": sha256(ROOT / "scripts" / "lab.py"),
            "scripts/trajectory.py": sha256(ROOT / "scripts" / "trajectory.py"),
        },
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def materialize_live_preflight(identity: str) -> Path:
    root = CACHE / "harbor" / "live-preflight" / identity
    if root.is_dir():
        return root
    temporary = root.with_name(root.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    (temporary / "environment" / "workspace").mkdir(parents=True)
    (temporary / "tests").mkdir(parents=True)
    lock = json.loads(EXPERIMENT_LOCK.read_text())
    (temporary / "instruction.md").write_text(
        "Call the Agent tool exactly once using subagent_type general-purpose. "
        "Ask that subagent to reply only READY. After it returns, reply only READY. "
        "Do not edit any files."
    )
    (temporary / "task.toml").write_text(task_toml("live-model-preflight", "live-model-preflight", "baseline"))
    (temporary / "environment" / "Dockerfile").write_text(environment_dockerfile(lock["images"]["baseline"]["tag"]))
    shutil.copyfile(ROOT / "harbor" / "pi_runner.py", temporary / "environment" / "harbor-pi-runner.py")
    test = temporary / "tests" / "test.sh"
    test.write_text("#!/bin/sh\nset -eu\nprintf '1\\n' > /logs/verifier/reward.txt\n")
    test.chmod(0o755)
    root.parent.mkdir(parents=True, exist_ok=True)
    temporary.replace(root)
    return root


def preflight_job_dir(record: dict) -> Path:
    job_dir = Path(record["job_dir"])
    if job_dir.is_dir():
        return job_dir
    relocated = list(EXPERIMENTS.glob(f"*/artifacts/harbor/{job_dir.name}"))
    return relocated[0] if len(relocated) == 1 else job_dir


def valid_preflight_record(record: dict) -> bool:
    job_dir = preflight_job_dir(record)
    return (
        record.get("status") == "passed"
        and bool(record.get("evidence"))
        and all(
            (job_dir / relative).is_file() and sha256(job_dir / relative) == expected
            for relative, expected in record.get("evidence", {}).items()
        )
    )


def archived_preflight_marker(identity: str) -> Path | None:
    for marker in sorted(EXPERIMENTS.glob("*/preflight.json"), reverse=True):
        record = json.loads(marker.read_text())
        if record.get("identity") == identity and valid_preflight_record(record):
            return marker
    return None


def live_preflight(force: bool = False) -> None:
    matrix = {
        "tasks": ["live-model-preflight"],
        "models": SMOKE_MODELS,
        "model_ids": [REQUIRED_MODEL_IDS[key] for key in SMOKE_MODELS],
        "arms": ["baseline"],
        "arm_variants": 1,
        "attempts": 1,
        "concurrency": 2,
        "trial_count": 2,
        "reasoning": "xhigh",
        "wavepeek_revisions": [],
        "wavepeek_builds": [],
    }
    preflight(matrix)
    identity = preflight_identity()
    marker = None if force else archived_preflight_marker(identity)
    if marker:
        print(f"live preflight: reused {preflight_job_dir(json.loads(marker.read_text()))}")
        return
    task = materialize_live_preflight(identity)
    run_id = new_experiment_id("preflight")
    experiment_dir = EXPERIMENTS / run_id
    root = experiment_dir / "artifacts"
    job_name = run_id
    command = [
        "uv", "run", "--no-dev", "--project", str(HARBOR_SOURCE), "harbor", "run",
        "--path", str(task),
        "--agent", "harbor_adapter:ReproduciblePi",
    ]
    for model in (REQUIRED_MODEL_IDS[key] for key in SMOKE_MODELS):
        command.extend(["--model", model])
    command.extend(
        [
            "--agent-kwarg", "version=0.83.0",
            "--agent-kwarg", "thinking=xhigh",
            "--n-attempts", "1",
            "--n-concurrent", "2",
            "--max-retries", "0",
            "--jobs-dir", str(root / "harbor"),
            "--job-name", job_name,
        ]
    )
    root.mkdir(parents=True)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT) + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    result = subprocess.run(command, cwd=ROOT, env=environment)
    job_dir = root / "harbor" / job_name
    errors = []
    trial_dirs = sorted(path for path in job_dir.iterdir() if path.is_dir() and (path / "result.json").is_file()) if job_dir.is_dir() else []
    if result.returncode or len(trial_dirs) != 2:
        errors.append(f"Harbor status={result.returncode}, trials={len(trial_dirs)}")
    observed_models = set()
    for trial_dir in trial_dirs:
        trial_result = json.loads((trial_dir / "result.json").read_text())
        metadata = (trial_result.get("agent_result") or {}).get("metadata") or {}
        model = (trial_result.get("config", {}).get("agent", {}) or {}).get("model_name")
        observed_models.add(model)
        if trial_result.get("exception_info"):
            errors.append(f"{trial_dir.name}: {trial_result['exception_info']['exception_type']}")
        if metadata.get("reasoning") != "xhigh" or metadata.get("requested_subagent_types") != ["general-purpose"]:
            errors.append(f"{trial_dir.name}: parent/subagent identity proof failed")
        if not metadata.get("subagent_transcripts") or not metadata.get("subagent_sessions"):
            errors.append(f"{trial_dir.name}: subagent trajectory/session missing")
    if observed_models != set(REQUIRED_MODEL_IDS.values()):
        errors.append(f"model set mismatch: {sorted(observed_models)}")
    evidence = {
        str(path.relative_to(job_dir)): sha256(path)
        for path in sorted(job_dir.rglob("*"))
        if path.is_file()
    }
    record = {
        "schema_version": 1,
        "identity": identity,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed" if errors else "passed",
        "errors": errors,
        "job_dir": str(job_dir),
        "models": sorted(observed_models),
        "evidence": evidence,
    }
    marker = experiment_dir / "preflight.json"
    journal_record = {
        "event": "live_preflight",
        "experiment": str(experiment_dir.relative_to(ROOT)),
        "created_at": record["created_at"],
        "status": record["status"],
        "identity": identity,
        "models": record["models"],
        "errors": errors,
        "artifacts": str(root.relative_to(ROOT)),
        "evidence_files": len(evidence),
    }
    (experiment_dir / "result.json").write_text(
        json.dumps(journal_record, indent=2, sort_keys=True) + "\n"
    )
    append_journal(journal_record)
    marker.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if errors:
        raise RuntimeError(f"live model/subagent preflight failed: {errors}")
    print(f"live preflight: passed {job_dir}")


def append_journal(record: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream, fcntl.LOCK_UN)


def parse_jsonl_optional(path: Path) -> list[dict]:
    return read_jsonl(path) if path.is_file() else []


def compliant_wavepeek_record(record: dict, artifact_root: Path) -> bool:
    if record.get("exit_status") != 0 or record.get("subcommand") not in {"info", "scope", "signal", "change", "value", "extract"}:
        return False
    waveform_paths = record.get("waveform_paths") or []
    retained = record.get("retained_waveforms") or []
    if not waveform_paths or not retained:
        return False
    if not all(str(path).lower().endswith((".vcd", ".vcd.gz", ".fst", ".fsdb")) for path in waveform_paths):
        return False
    root = artifact_root.resolve()
    for item in retained:
        relative = Path(str(item.get("artifact", "")))
        if relative.is_absolute() or ".." in relative.parts or not item.get("sha256"):
            return False
        target = (artifact_root / relative).resolve()
        if root not in target.parents or not target.is_file() or sha256(target) != item["sha256"]:
            return False
    return True


def elapsed_seconds(result: dict) -> float | None:
    started = result.get("started_at")
    finished = result.get("finished_at")
    if not started or not finished:
        return None
    return (datetime.fromisoformat(finished.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()


def analyze_summary(trials: list[dict]) -> dict:
    cells = []
    for trial in sorted(trials, key=lambda item: (item["model"], item["arm"], item["attempt"])):
        usage_data = trial.get("usage") or {}
        cells.append(
            {
                "task_id": trial["task_id"],
                "model": trial["model"],
                "arm": trial["arm"],
                "attempt": trial["attempt"],
                "infrastructure_status": trial["infrastructure_status"],
                "benchmark_pass": trial["benchmark_pass"],
                "runtime_seconds": trial["runtime_seconds"],
                "input_tokens": usage_data.get("input"),
                "output_tokens": usage_data.get("output"),
                "cache_read_tokens": usage_data.get("cacheRead"),
                "cache_write_tokens": usage_data.get("cacheWrite"),
                "reported_cost": usage_data.get("reportedCost"),
                "pi_calculated_cost": usage_data.get("piCalculatedCost"),
                "wavepeek_calls": trial["wavepeek"]["total_calls"],
                "wavepeek_successful_queries": trial["wavepeek"]["successful_meaningful_calls"],
                "wavepeek_duration_seconds": trial["wavepeek"]["total_duration_seconds"],
                "wavepeek_compliant": trial["wavepeek"]["compliant"],
            }
        )
    pairs = []
    grouped: dict[tuple[str, str], list[dict]] = {}
    for trial in trials:
        grouped.setdefault((trial["task_id"], trial["model"]), []).append(trial)
    for (task_id, model), group in sorted(grouped.items()):
        baseline = [trial for trial in group if trial["arm"] == "baseline"]
        treatment_arms = sorted({trial["arm"] for trial in group if trial["arm"].startswith("wavepeek@")})
        for treatment_arm in treatment_arms:
            treatment = [trial for trial in group if trial["arm"] == treatment_arm]
            if not baseline:
                continue
            baseline_runtimes = [trial["runtime_seconds"] for trial in baseline if trial["runtime_seconds"] is not None]
            treatment_runtimes = [trial["runtime_seconds"] for trial in treatment if trial["runtime_seconds"] is not None]
            baseline_rate = sum(bool(trial["benchmark_pass"]) for trial in baseline) / len(baseline)
            treatment_rate = sum(bool(trial["benchmark_pass"]) for trial in treatment) / len(treatment)
            pairs.append(
                {
                    "task_id": task_id,
                    "model": model,
                    "wavepeek_arm": treatment_arm,
                    "baseline_attempts": len(baseline),
                    "wavepeek_attempts": len(treatment),
                    "baseline_pass_rate": baseline_rate,
                    "wavepeek_pass_rate": treatment_rate,
                    "pass_rate_delta": treatment_rate - baseline_rate,
                    "baseline_mean_runtime_seconds": sum(baseline_runtimes) / len(baseline_runtimes) if baseline_runtimes else None,
                    "wavepeek_mean_runtime_seconds": sum(treatment_runtimes) / len(treatment_runtimes) if treatment_runtimes else None,
                    "wavepeek_calls": sum(trial["wavepeek"]["total_calls"] for trial in treatment),
                    "pairing_note": "Attempts are independent replicates; no arbitrary one-to-one pairing is asserted.",
                }
            )
    return {
        "schema_version": 1,
        "scope_note": "Infrastructure smoke only; four trials are not statistical evidence of a causal effect.",
        "cells": cells,
        "pairs": pairs,
    }


def render_analysis_markdown(manifest: dict, trials: list[dict]) -> str:
    lines = [
        f"# Experiment {manifest['run_id']}",
        "",
        "Purpose: compare the selected CVDP cells under baseline and pinned WavePeek treatment through Harbor.",
        "",
        f"Selection: {len(manifest['matrix']['tasks'])} task(s), {len(manifest['matrix']['models'])} model profile(s), "
        f"{manifest['matrix']['arm_variants']} arm variant(s), {manifest['matrix']['attempts']} independent attempt(s); "
        f"expected trials: {manifest['matrix']['trial_count']}.",
        "",
        "| Task | Model | Arm | Attempt | Infrastructure | Benchmark | Runtime (s) | Input | Output | Cache read | Subagents | WavePeek calls / successful / duration |",
        "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for trial in sorted(trials, key=lambda item: (item["task_id"], item["model"], item["arm"], item["attempt"])):
        usage_data = trial.get("usage") or {}
        lines.append(
            f"| {trial['task_id']} | {trial['model']} | {trial['arm']} | {trial['attempt']} | "
            f"{trial['infrastructure_status']} | {trial['benchmark_pass']} | {trial['runtime_seconds']} | "
            f"{usage_data.get('input')} | {usage_data.get('output')} | {usage_data.get('cacheRead')} | "
            f"{len(trial['trajectories']['subagents'])} | {trial['wavepeek']['total_calls']} / "
            f"{trial['wavepeek']['successful_meaningful_calls']} / {trial['wavepeek']['total_duration_seconds']:.6f}s |"
        )
    complete = sum(trial["infrastructure_status"] == "complete" for trial in trials)
    passes = sum(bool(trial["benchmark_pass"]) for trial in trials)
    delegated = sum(len(trial["trajectories"]["subagents"]) for trial in trials)
    calls = sum(trial["wavepeek"]["total_calls"] for trial in trials)
    successful_queries = sum(trial["wavepeek"]["successful_meaningful_calls"] for trial in trials)
    wavepeek_duration = sum(trial["wavepeek"]["total_duration_seconds"] for trial in trials)
    reported_costs = [trial["usage"].get("reportedCost") for trial in trials if trial.get("usage") and trial["usage"].get("reportedCost") is not None]
    delegation_observations = ", ".join(
        f"{trial['model']} {trial['arm']}={len(trial['trajectories']['subagents'])}"
        for trial in sorted(trials, key=lambda item: (item["model"], item["arm"], item["attempt"]))
    )
    lines.extend(
        [
            "",
            f"Compact result: {complete}/{len(trials)} infrastructure-complete, {passes}/{len(trials)} benchmark passes, "
            f"{delegated} delegated trajectory/trajectories, {calls} audited WavePeek calls, "
            f"{successful_queries} successful retained-waveform queries, and {wavepeek_duration:.6f}s total WavePeek CLI time.",
            "",
            f"Trajectory observation (subagent counts by cell): {delegation_observations}. Delegation was permitted and measured, not forced; exact paths are in summary.json.",
            "",
            (
                f"Cost conclusion: provider-reported total is {sum(reported_costs):.8f}."
                if reported_costs
                else "Cost conclusion: reported provider cost is unavailable. Pi-calculated catalog values remain raw estimates, not billing evidence."
            ),
            "",
            "Conclusion: this output is experiment evidence; small subsets or smoke runs are not statistical evidence of a causal effect.",
            "",
            f"Raw Harbor artifacts: `{manifest['harbor_job_dir']}/{manifest['harbor_job_name']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def normalize_run(run_dir: Path, manifest: dict) -> tuple[dict, list[str]]:
    job_dir = run_dir / "harbor" / manifest["harbor_job_name"]
    errors: list[str] = []
    if not job_dir.is_dir():
        return {"schema_version": 1, "trials": []}, [f"missing Harbor job directory: {job_dir}"]
    trial_dirs = sorted(
        path for path in job_dir.iterdir()
        if path.is_dir() and (path / "result.json").is_file()
    )
    if len(trial_dirs) != manifest["matrix"]["trial_count"]:
        errors.append(f"expected {manifest['matrix']['trial_count']} trials, found {len(trial_dirs)}")
    attempt_counts: dict[tuple[str, str, str], int] = {}
    trials = []
    for trial_dir in trial_dirs:
        result = json.loads((trial_dir / "result.json").read_text())
        task_name = result["task_name"].split("/", 1)[-1]
        task_id, variant = task_name.split("--", 1)
        if variant == "baseline":
            arm = "baseline"
        else:
            prefix = variant.removeprefix("wavepeek-")
            matches = [commit for commit in manifest["matrix"]["wavepeek_revisions"] if commit.startswith(prefix)]
            if len(matches) != 1:
                errors.append(f"{trial_dir.name}: treatment variant does not resolve uniquely: {variant}")
                arm = f"wavepeek@{prefix}"
            else:
                arm = f"wavepeek@{matches[0]}"
        model = (result.get("config", {}).get("agent", {}) or {}).get("model_name")
        key = (task_id, model, arm)
        attempt_counts[key] = attempt_counts.get(key, 0) + 1
        attempt = attempt_counts[key]
        agent_metadata = (result.get("agent_result") or {}).get("metadata") or {}
        artifact_prefix = Path("artifacts/logs/artifacts")
        artifact_root = trial_dir / artifact_prefix
        invocations = parse_jsonl_optional(artifact_root / "wavepeek-invocations.jsonl")
        successful = [
            record for record in invocations
            if compliant_wavepeek_record(record, artifact_root)
        ]
        required = [
            "agent/pi.txt",
            "agent/pi/sessions/main.jsonl",
            "agent/trajectory-index.json",
            "artifacts/logs/artifacts/final.patch",
            "artifacts/logs/artifacts/agent-runtime.json",
            "artifacts/logs/artifacts/main-session-stats.json",
            "artifacts/logs/artifacts/waveforms.json",
            "verifier/test-stdout.txt",
            "verifier/reward.txt",
            "config.json",
            "lock.json",
            "result.json",
            "trial.log",
        ]
        missing = [relative for relative in required if not (trial_dir / relative).is_file()]
        exception = result.get("exception_info")
        if exception:
            errors.append(
                f"{trial_dir.name}: infrastructure exception "
                f"{exception.get('exception_type')}: {exception.get('exception_message')}"
            )
        elif missing:
            errors.append(f"{trial_dir.name}: missing required evidence: {missing}")
        reward = ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        trial = {
            "trial_name": trial_dir.name,
            "raw_path": str(trial_dir.relative_to(run_dir)),
            "task_id": task_id,
            "model": model,
            "arm": arm,
            "attempt": attempt,
            "infrastructure_status": "complete" if not exception and not missing else "failed",
            "exception": exception,
            "benchmark_pass": reward == 1 or reward == 1.0,
            "reward": reward,
            "runtime_seconds": elapsed_seconds(result),
            "usage": agent_metadata.get("usage"),
            "main_usage": agent_metadata.get("main_usage"),
            "subagent_usage": agent_metadata.get("subagent_usage"),
            "provider_model_reasoning": {
                "provider": agent_metadata.get("provider"),
                "model": agent_metadata.get("model"),
                "reasoning": agent_metadata.get("reasoning"),
            },
            "trajectories": {
                "main": agent_metadata.get("main_trajectory"),
                "subagents": agent_metadata.get("subagent_transcripts") or [],
                "subagent_sessions": agent_metadata.get("subagent_sessions") or [],
            },
            "patch": str(artifact_prefix / "final.patch"),
            "verifier_output": "verifier/test-stdout.txt",
            "waveforms": str(artifact_prefix / "waveforms.json"),
            "wavepeek": {
                "total_calls": len(invocations),
                "successful_meaningful_calls": len(successful),
                "total_duration_seconds": sum(float(record.get("duration_seconds", 0) or 0) for record in invocations),
                "compliant": bool(successful) if arm.startswith("wavepeek@") else None,
                "first_successful_call": successful[0]["started_at"] if successful else None,
                "audit": str(artifact_prefix / "wavepeek-invocations.jsonl") if invocations else None,
            },
            "missing_evidence": missing,
        }
        if arm.startswith("wavepeek@") and not trial["wavepeek"]["compliant"] and not exception:
            errors.append(f"{trial_dir.name}: treatment did not successfully query a waveform with WavePeek")
        trials.append(trial)
    expected_cells = {
        (task_id, model, arm, attempt)
        for task_id in manifest["matrix"]["tasks"]
        for model in manifest["matrix"]["model_ids"]
        for arm in (
            (["baseline"] if "baseline" in manifest["matrix"]["arms"] else [])
            + [f"wavepeek@{commit}" for commit in manifest["matrix"]["wavepeek_revisions"]]
        )
        for attempt in range(1, manifest["matrix"]["attempts"] + 1)
    }
    observed_cells = {
        (trial["task_id"], trial["model"], trial["arm"], trial["attempt"])
        for trial in trials
    }
    if observed_cells != expected_cells:
        errors.append(
            "trial cell mismatch: "
            f"missing={sorted(expected_cells - observed_cells)}, "
            f"unexpected={sorted(observed_cells - expected_cells)}"
        )
    summary = {
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "expected_trials": manifest["matrix"]["trial_count"],
        "observed_trials": len(trials),
        "trials": trials,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (run_dir / "analysis.json").write_text(json.dumps(analyze_summary(trials), indent=2, sort_keys=True) + "\n")
    (run_dir / "analysis.md").write_text(render_analysis_markdown(manifest, trials))
    return summary, errors


def write_checksums(run_dir: Path) -> None:
    output = run_dir / "run-checksums.json"
    entries = {
        path.relative_to(run_dir).as_posix(): sha256(path)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path != output
    }
    output.write_text(json.dumps({"schema_version": 1, "files": entries}, indent=2, sort_keys=True) + "\n")


def execute_job(manifest: dict, command: list[str]) -> int:
    experiment_dir = EXPERIMENTS / manifest["run_id"]
    run_dir = experiment_dir / "artifacts"
    run_dir.mkdir(parents=True, exist_ok=False)
    retained_sources = []
    for build in manifest["matrix"]["wavepeek_builds"]:
        source = ROOT / build["wavepeek"]["source_artifact"]
        if source.is_file():
            destination = run_dir / "sources" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            retained_sources.append(
                {
                    "commit": build["wavepeek"]["commit"],
                    "path": str(destination.relative_to(run_dir)),
                    "sha256": sha256(destination),
                }
            )
        else:
            raise RuntimeError(f"WavePeek source artifact is missing: {source}")
    manifest["retained_wavepeek_sources"] = retained_sources
    task_source = ROOT / manifest.get("task_dataset_source", manifest["task_dataset"])
    retained_tasks = ROOT / manifest["task_dataset"]
    if not task_source.is_dir():
        raise RuntimeError(f"resolved Harbor task dataset is missing: {task_source}")
    shutil.copytree(task_source, retained_tasks)
    manifest["retained_task_dataset"] = str(retained_tasks.relative_to(run_dir))
    preflight_marker = archived_preflight_marker(preflight_identity())
    if preflight_marker:
        live = json.loads(preflight_marker.read_text())
        retained_marker = run_dir / "inputs" / "live-preflight.json"
        retained_marker.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(preflight_marker, retained_marker)
        manifest["live_preflight"] = {
            "identity": live.get("identity"),
            "status": live.get("status"),
            "job_dir": live.get("job_dir"),
            "marker": str(retained_marker.relative_to(run_dir)),
            "marker_sha256": sha256(preflight_marker),
        }
    job_config_path = run_dir / manifest["harbor_job_config"]
    job_config_path.write_text(
        json.dumps(manifest["resolved_harbor_job"], indent=2, sort_keys=True) + "\n"
    )
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT) + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    result = subprocess.run(command, cwd=ROOT, env=environment)
    manifest["status"] = "harbor_complete" if result.returncode == 0 else "harbor_failed"
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest["harbor_exit_status"] = result.returncode
    summary, audit_errors = normalize_run(run_dir, manifest)
    manifest["audit_errors"] = audit_errors
    if audit_errors:
        manifest["status"] = "audit_failed"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    write_checksums(run_dir)
    journal_record = {
            "event": "experiment",
            "experiment": str(experiment_dir.relative_to(ROOT)),
            "run_id": manifest["run_id"],
            "created_at": manifest["created_at"],
            "finished_at": manifest["finished_at"],
            "status": manifest["status"],
            "trial_count": manifest["matrix"]["trial_count"],
            "observed_trials": summary["observed_trials"],
            "purpose": "Compare selected CVDP cells under baseline and pinned WavePeek treatment through Harbor.",
            "selection": {
                "tasks": manifest["matrix"]["tasks"],
                "models": manifest["matrix"]["models"],
                "arms": manifest["matrix"]["arms"],
                "wavepeek_revisions": manifest["matrix"]["wavepeek_revisions"],
                "attempts": manifest["matrix"]["attempts"],
            },
            "compact_results": {
                "infrastructure_complete": sum(trial["infrastructure_status"] == "complete" for trial in summary["trials"]),
                "benchmark_passes": sum(bool(trial["benchmark_pass"]) for trial in summary["trials"]),
                "wavepeek_calls": sum(trial["wavepeek"]["total_calls"] for trial in summary["trials"]),
                "wavepeek_successful_queries": sum(trial["wavepeek"]["successful_meaningful_calls"] for trial in summary["trials"]),
                "wavepeek_duration_seconds": sum(trial["wavepeek"]["total_duration_seconds"] for trial in summary["trials"]),
                "reported_cost": (
                    sum(trial["usage"]["reportedCost"] for trial in summary["trials"] if trial.get("usage") and trial["usage"].get("reportedCost") is not None)
                    if any(trial.get("usage") and trial["usage"].get("reportedCost") is not None for trial in summary["trials"])
                    else None
                ),
            },
            "trajectory_observations": {
                "delegated_trajectories": sum(len(trial["trajectories"]["subagents"]) for trial in summary["trials"]),
                "by_cell": [
                    {
                        "task": trial["task_id"],
                        "model": trial["model"],
                        "arm": trial["arm"],
                        "attempt": trial["attempt"],
                        "subagents": len(trial["trajectories"]["subagents"]),
                    }
                    for trial in summary["trials"]
                ],
            },
            "conclusion": "Infrastructure evidence retained; statistical interpretation depends on selected cohort and attempts.",
            "raw_artifacts": str((run_dir / "harbor" / manifest["harbor_job_name"]).relative_to(ROOT)),
            "analysis": str((run_dir / "analysis.md").relative_to(ROOT)),
            "manifest": str(manifest_path.relative_to(ROOT)),
            "manifest_sha256": sha256(manifest_path),
            "checksums_sha256": sha256(run_dir / "run-checksums.json"),
        }
    shutil.copyfile(run_dir / "analysis.md", experiment_dir / "analysis.md")
    (experiment_dir / "result.json").write_text(
        json.dumps(journal_record, indent=2, sort_keys=True) + "\n"
    )
    append_journal(journal_record)
    return result.returncode or bool(audit_errors)


def resolve_run_path(value: str) -> Path:
    candidates = sorted(
        path / "artifacts"
        for path in EXPERIMENTS.iterdir()
        if path.is_dir() and (path / "artifacts" / "manifest.json").is_file()
    ) if EXPERIMENTS.is_dir() else []
    if value == "latest":
        if not candidates:
            raise ValueError("no experiment directories exist")
        return candidates[-1]
    direct = EXPERIMENTS / value / "artifacts"
    if (direct / "manifest.json").is_file():
        return direct
    matches = [
        path for path in candidates
        if json.loads((path / "manifest.json").read_text()).get("run_id") == value
    ]
    if len(matches) != 1:
        raise ValueError(f"experiment does not exist: {value}")
    return matches[0]


def resume_run(value: str) -> int:
    parent_dir = resolve_run_path(value)
    parent = json.loads((parent_dir / "manifest.json").read_text())
    matrix = parent["matrix"]
    preflight(matrix)
    manifest, command = resolved_job(matrix, f"continuation-{parent['run_id']}")
    manifest["parent_run"] = {
        "run_id": parent["run_id"],
        "manifest": str((parent_dir / "manifest.json").relative_to(ROOT)),
        "manifest_sha256": sha256(parent_dir / "manifest.json"),
        "reason": "explicit infrastructure continuation; parent evidence remains immutable",
    }
    return execute_job(manifest, command)


def verify_run(value: str) -> None:
    run_dir = resolve_run_path(value)
    checksum_path = run_dir / "run-checksums.json"
    checksums = json.loads(checksum_path.read_text())["files"]
    actual_files = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path != checksum_path
    }
    if actual_files != set(checksums):
        raise ValueError(
            f"run file set mismatch: missing={sorted(set(checksums) - actual_files)}, "
            f"unexpected={sorted(actual_files - set(checksums))}"
        )
    mismatches = [
        relative for relative, expected in checksums.items()
        if sha256(run_dir / relative) != expected
    ]
    if mismatches:
        raise ValueError(f"run checksum mismatch: {mismatches}")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    live = manifest.get("live_preflight")
    if live:
        marker = run_dir / live["marker"] if live.get("marker") else archived_preflight_marker(live["identity"])
        marker = marker or CACHE / "live-preflight.json"
        marker_valid = marker.is_file() and sha256(marker) == live["marker_sha256"]
        if not marker_valid:
            if manifest.get("status") != "audit_failed":
                raise ValueError("bound live-preflight marker is missing or changed")
            print("warning: rejected diagnostic predates retained preflight markers")
        else:
            preflight_record = json.loads(marker.read_text())
            job_dir = preflight_job_dir(preflight_record)
            bad = [
                relative for relative, expected in preflight_record["evidence"].items()
                if not (job_dir / relative).is_file() or sha256(job_dir / relative) != expected
            ]
            if bad:
                raise ValueError(f"live-preflight evidence mismatch: {bad}")
    print(f"experiment integrity verified: {run_dir.parent.name} files={len(checksums)}")


def show_status(value: str) -> None:
    run_dir = resolve_run_path(value)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    summary = json.loads((run_dir / "summary.json").read_text()) if (run_dir / "summary.json").is_file() else {"trials": []}
    print(f"run={manifest['run_id']} status={manifest['status']} expected={manifest['matrix']['trial_count']} observed={len(summary['trials'])}")
    for trial in summary["trials"]:
        print(
            f"{trial['model']} {trial['arm']} attempt={trial['attempt']} "
            f"infrastructure={trial['infrastructure_status']} pass={trial['benchmark_pass']} "
            f"wavepeek_calls={trial['wavepeek']['total_calls']}"
        )


def regenerate_analysis(value: str) -> None:
    run_dir = resolve_run_path(value)
    path = run_dir / "analysis.json"
    if not path.is_file():
        raise ValueError(f"experiment has no retained analysis: {run_dir.parent.name}")
    print(path.read_text(), end="")


def add_matrix_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--selector", choices=["smoke"])
    parser.add_argument("--tasks", default="all")
    parser.add_argument("--models", default="all")
    parser.add_argument("--arms", default="all")
    parser.add_argument("--attempts", default="1")
    parser.add_argument("--revisions", default="default", help="comma-separated SHA, path[#ref], or URL#ref")
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--agent-timeout", type=int)
    parser.add_argument("--verifier-timeout", type=int)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("task_id")
    materialize_parser.add_argument("arm", choices=["baseline", "wavepeek"])
    subparsers.add_parser("harbor-bootstrap")
    live_parser = subparsers.add_parser("live-preflight")
    live_parser.add_argument("--force", action="store_true")
    for name in ("job", "preflight", "run"):
        matrix_parser = subparsers.add_parser(name)
        add_matrix_arguments(matrix_parser)
        matrix_parser.add_argument("--name")
        if name == "job":
            matrix_parser.add_argument("--dry-run", action="store_true")
    for name in ("status", "analyze", "resume", "verify"):
        run_parser = subparsers.add_parser(name)
        run_parser.add_argument("run", nargs="?", default="latest")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "check":
        check()
    elif args.command == "materialize":
        materialize(args.task_id, args.arm)
    elif args.command == "harbor-bootstrap":
        harbor_bootstrap()
    elif args.command == "live-preflight":
        live_preflight(args.force)
    elif args.command == "status":
        show_status(args.run)
    elif args.command == "analyze":
        regenerate_analysis(args.run)
    elif args.command == "resume":
        return resume_run(args.run)
    elif args.command == "verify":
        verify_run(args.run)
    elif args.command in {"job", "preflight", "run"}:
        matrix = resolve_matrix(args)
        if args.command == "preflight":
            preflight(matrix)
        else:
            manifest, command = resolved_job(matrix, args.name or args.selector or "experiment")
            if args.command == "job":
                print(json.dumps(manifest, indent=2, sort_keys=True))
                print(
                    f"trials={matrix['trial_count']} tasks={len(matrix['tasks'])} "
                    f"models={len(matrix['models'])} arm_variants={matrix['arm_variants']} attempts={matrix['attempts']}"
                )
            else:
                preflight(matrix)
                return execute_job(manifest, command)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
