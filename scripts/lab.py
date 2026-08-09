#!/usr/bin/env python3
"""Validate frozen inputs and materialize CVDP tasks for Harbor."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
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
SELECTED_SHA256 = "945c389a3f863faadfd863d22315285fa2049cac3595eb37aa33efb3b159124d"
HARBOR_COMMIT = "0348989adffbb43bf0b410fd36197333239633f1"
WAVEPEEK_INSTRUCTION = (
    "Use the installed WavePeek skill and CLI to inspect waveform behavior while "
    "solving this task. You must run WavePeek meaningfully against a task waveform "
    "before finalizing the solution."
)
MODEL_IDS = {
    "openai-codex-gpt-5.6-luna-xhigh": "openai-codex/gpt-5.6-luna",
    "openrouter-deepseek-v4-flash-0731-xhigh": "openrouter/deepseek/deepseek-v4-flash-0731",
}
HARBOR_SOURCE = CACHE / "harbor" / "source"
JOURNAL = ROOT / "docs" / "EXPERIMENT_JOURNAL.jsonl"


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
        if profile["reasoning"] != "xhigh":
            raise ValueError(f"{profile['id']} must use xhigh reasoning")
    if profiles != MODEL_IDS:
        raise ValueError(f"model profiles differ from the fixed profiles: {profiles}")
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


def task_toml(name: str, task_id: str, arm: str) -> str:
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
timeout_sec = 600.0

[agent]
timeout_sec = 3600.0

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
    (temporary / "task.toml").write_text(task_toml(destination.name, task_id, arm_id))
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
        model_keys = list(MODEL_IDS)
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
        "concurrency": min(json.loads(CONFIG.read_text())["default_concurrency"], count),
        "trial_count": count,
        "reasoning": "xhigh",
        "wavepeek_revisions": commits,
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
            materialize(task_id, "baseline", temporary)
        if "wavepeek" in matrix["arms"]:
            for treatment_lock in matrix["wavepeek_builds"]:
                materialize(task_id, "wavepeek", temporary, treatment_lock)
    root.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(root, ignore_errors=True)
    temporary.replace(root)
    return root


def resolved_job(matrix: dict, name: str) -> tuple[dict, list[str]]:
    dataset = materialize_dataset(matrix)
    digest = hashlib.sha256(json.dumps(matrix, sort_keys=True).encode()).hexdigest()[:8]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{digest}"
    run_dir = ROOT / "runs" / run_id
    harbor_dir = run_dir / "harbor"
    command = [
        "uv", "run", "--no-dev", "--project", str(HARBOR_SOURCE), "harbor", "run",
        "--path", str(dataset),
        "--agent", "harbor_adapter:ReproduciblePi",
    ]
    for model in matrix["model_ids"]:
        command.extend(["--model", model])
    command.extend(
        [
            "--agent-kwarg", "version=0.83.0",
            "--agent-kwarg", "thinking=xhigh",
            "--n-attempts", str(matrix["attempts"]),
            "--n-concurrent", str(matrix["concurrency"]),
            "--max-retries", "0",
            "--jobs-dir", str(harbor_dir),
            "--job-name", f"{name}-{run_id}",
        ]
    )
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "resolved",
        "matrix": matrix,
        "task_dataset": str(dataset.relative_to(ROOT)),
        "harbor_commit": HARBOR_COMMIT,
        "harbor_job_dir": str(harbor_dir.relative_to(ROOT)),
        "harbor_job_name": f"{name}-{run_id}",
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
    providers = {MODEL_IDS[key].split("/", 1)[0] for key in matrix["models"]}
    missing = sorted(provider for provider in providers if provider not in records and not (provider == "openrouter" and os.environ.get("OPENROUTER_API_KEY")))
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
        "models": MODEL_IDS,
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


def live_preflight(force: bool = False) -> None:
    matrix = {
        "tasks": ["live-model-preflight"],
        "models": list(MODEL_IDS),
        "model_ids": list(MODEL_IDS.values()),
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
    marker = CACHE / "live-preflight.json"
    if not force and marker.is_file():
        previous = json.loads(marker.read_text())
        previous_job = Path(previous.get("job_dir", ""))
        evidence_valid = bool(previous.get("evidence")) and all(
            (previous_job / relative).is_file() and sha256(previous_job / relative) == expected
            for relative, expected in previous.get("evidence", {}).items()
        )
        if previous.get("identity") == identity and previous.get("status") == "passed" and evidence_valid:
            print(f"live preflight: reused {previous_job}")
            return
    task = materialize_live_preflight(identity)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + identity[:8]
    root = ROOT / "preflights" / run_id
    job_name = f"live-model-preflight-{run_id}"
    command = [
        "uv", "run", "--no-dev", "--project", str(HARBOR_SOURCE), "harbor", "run",
        "--path", str(task),
        "--agent", "harbor_adapter:ReproduciblePi",
    ]
    for model in MODEL_IDS.values():
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
    if observed_models != set(MODEL_IDS.values()):
        errors.append(f"model set mismatch: {sorted(observed_models)}")
    evidence_paths = [job_dir / "lock.json", job_dir / "result.json"]
    for trial_dir in trial_dirs:
        evidence_paths.extend(
            [
                trial_dir / "result.json",
                trial_dir / "agent" / "trajectory-index.json",
                trial_dir / "agent" / "pi" / "sessions" / "main.jsonl",
            ]
        )
        evidence_paths.extend(sorted((trial_dir / "agent" / "pi" / "tmp").rglob("*.output")))
    evidence = {
        str(path.relative_to(job_dir)): sha256(path)
        for path in evidence_paths if path.is_file()
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
    marker.parent.mkdir(parents=True, exist_ok=True)
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
                "wavepeek_compliant": trial["wavepeek"]["compliant"],
            }
        )
    pairs = []
    grouped: dict[tuple[str, str, int], list[dict]] = {}
    for trial in trials:
        grouped.setdefault((trial["task_id"], trial["model"], trial["attempt"]), []).append(trial)
    for (task_id, model, attempt), group in sorted(grouped.items()):
        baseline = next((trial for trial in group if trial["arm"] == "baseline"), None)
        for treatment in sorted(
            (trial for trial in group if trial["arm"].startswith("wavepeek@")),
            key=lambda trial: trial["arm"],
        ):
            if baseline is None:
                continue
            pairs.append(
                {
                    "task_id": task_id,
                    "model": model,
                    "attempt": attempt,
                    "wavepeek_arm": treatment["arm"],
                    "baseline_pass": baseline["benchmark_pass"],
                    "wavepeek_pass": treatment["benchmark_pass"],
                    "pass_delta": int(bool(treatment["benchmark_pass"])) - int(bool(baseline["benchmark_pass"])),
                    "runtime_delta_seconds": (
                        treatment["runtime_seconds"] - baseline["runtime_seconds"]
                        if treatment["runtime_seconds"] is not None and baseline["runtime_seconds"] is not None
                        else None
                    ),
                    "wavepeek_calls": treatment["wavepeek"]["total_calls"],
                }
            )
    return {
        "schema_version": 1,
        "scope_note": "Infrastructure smoke only; four trials are not statistical evidence of a causal effect.",
        "cells": cells,
        "pairs": pairs,
    }


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
    meaningful = {"hierarchy", "signals", "get", "find", "eval"}
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
        invocations = parse_jsonl_optional(trial_dir / "artifacts" / "wavepeek-invocations.jsonl")
        successful = [
            record for record in invocations
            if record.get("exit_status") == 0
            and record.get("waveform_paths")
            and record.get("subcommand") in meaningful
        ]
        required = [
            "agent/pi.txt",
            "agent/pi/sessions/main.jsonl",
            "agent/trajectory-index.json",
            "artifacts/final.patch",
            "artifacts/agent-runtime.json",
            "artifacts/main-session-stats.json",
            "artifacts/waveforms.json",
            "verifier/test-stdout.txt",
            "verifier/reward.txt",
            "config.json",
            "lock.json",
            "result.json",
            "trial.log",
        ]
        missing = [relative for relative in required if not (trial_dir / relative).is_file()]
        exception = result.get("exception_info")
        if not exception and missing:
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
            "patch": "artifacts/final.patch",
            "verifier_output": "verifier/test-stdout.txt",
            "waveforms": "artifacts/waveforms.json",
            "wavepeek": {
                "total_calls": len(invocations),
                "successful_meaningful_calls": len(successful),
                "compliant": bool(successful) if arm.startswith("wavepeek@") else None,
                "first_successful_call": successful[0]["started_at"] if successful else None,
                "audit": "artifacts/wavepeek-invocations.jsonl" if invocations else None,
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
    run_dir = ROOT / "runs" / manifest["run_id"]
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
    preflight_marker = CACHE / "live-preflight.json"
    if preflight_marker.is_file():
        live = json.loads(preflight_marker.read_text())
        manifest["live_preflight"] = {
            "identity": live.get("identity"),
            "status": live.get("status"),
            "job_dir": live.get("job_dir"),
            "marker_sha256": sha256(preflight_marker),
        }
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
    append_journal(
        {
            "run_id": manifest["run_id"],
            "created_at": manifest["created_at"],
            "finished_at": manifest["finished_at"],
            "status": manifest["status"],
            "trial_count": manifest["matrix"]["trial_count"],
            "observed_trials": summary["observed_trials"],
            "manifest": str(manifest_path.relative_to(ROOT)),
            "manifest_sha256": sha256(manifest_path),
            "checksums_sha256": sha256(run_dir / "run-checksums.json"),
        }
    )
    return result.returncode or bool(audit_errors)


def resolve_run_path(value: str) -> Path:
    root = ROOT / "runs"
    if value == "latest":
        candidates = sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
        if not candidates:
            raise ValueError("no run directories exist")
        return candidates[-1]
    path = root / value
    if not path.is_dir():
        raise ValueError(f"run does not exist: {value}")
    return path


def resume_run(value: str) -> int:
    run_dir = resolve_run_path(value)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    job_dir = run_dir / "harbor" / manifest["harbor_job_name"]
    command = [
        "uv", "run", "--no-dev", "--project", str(HARBOR_SOURCE),
        "harbor", "jobs", "resume", "--job-path", str(job_dir),
    ]
    preflight(manifest["matrix"])
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT) + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    result = subprocess.run(command, cwd=ROOT, env=environment)
    summary, errors = normalize_run(run_dir, manifest)
    manifest["status"] = "audit_failed" if errors else ("harbor_complete" if result.returncode == 0 else "harbor_failed")
    manifest["audit_errors"] = errors
    manifest["last_resumed_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    write_checksums(run_dir)
    append_journal(
        {
            "event": "resume",
            "run_id": manifest["run_id"],
            "created_at": manifest["last_resumed_at"],
            "status": manifest["status"],
            "observed_trials": summary["observed_trials"],
            "manifest": str(manifest_path.relative_to(ROOT)),
            "manifest_sha256": sha256(manifest_path),
            "checksums_sha256": sha256(run_dir / "run-checksums.json"),
        }
    )
    return result.returncode or bool(errors)


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
    summary = json.loads((run_dir / "summary.json").read_text())
    analysis = analyze_summary(summary["trials"])
    path = run_dir / "analysis.json"
    path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    write_checksums(run_dir)
    print(path)


def add_matrix_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--selector", choices=["smoke"])
    parser.add_argument("--tasks", default="all")
    parser.add_argument("--models", default="all")
    parser.add_argument("--arms", default="all")
    parser.add_argument("--attempts", default="1")
    parser.add_argument("--revisions", default="default", help="comma-separated SHA, path[#ref], or URL#ref")


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
        matrix_parser.add_argument("--name", default="experiment")
        if name == "job":
            matrix_parser.add_argument("--dry-run", action="store_true")
    for name in ("status", "analyze", "resume"):
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
    elif args.command in {"job", "preflight", "run"}:
        matrix = resolve_matrix(args)
        if args.command == "preflight":
            preflight(matrix)
        else:
            manifest, command = resolved_job(matrix, args.name)
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
