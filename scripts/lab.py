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
    && chown -R 1000:1000 /app /run/secrets \
    && chmod -R u+rwX,go+rX /app
USER 1000:1000
WORKDIR /app
'''


def materialize(task_id: str, arm: str, output_root: Path | None = None) -> Path:
    if arm not in {"baseline", "wavepeek"}:
        raise ValueError("arm must be baseline or wavepeek")
    selection = next((row for row in selected_rows() if row["id"] == task_id), None)
    if selection is None:
        raise ValueError(f"task is not in the frozen selection: {task_id}")
    row = full_row(selection)
    lock = json.loads(EXPERIMENT_LOCK.read_text())
    image = lock["images"][arm]["tag"]
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
    else:
        task_ids = split_selector(args.tasks, [row["id"] for row in rows], "task")
        model_keys = split_selector(args.models, list(MODEL_IDS), "model")
        arms = split_selector(args.arms, ["baseline", "wavepeek"], "arm")
        attempts = int(args.attempts)
    if attempts < 1:
        raise ValueError("attempts must be positive")
    count = len(task_ids) * len(model_keys) * len(arms) * attempts
    if smoke and count != 4:
        raise ValueError(f"smoke matrix must contain exactly four trials, resolved {count}")
    return {
        "tasks": task_ids,
        "models": model_keys,
        "model_ids": [MODEL_IDS[key] for key in model_keys],
        "arms": arms,
        "attempts": attempts,
        "concurrency": min(json.loads(CONFIG.read_text())["default_concurrency"], count),
        "trial_count": count,
        "reasoning": "xhigh",
        "wavepeek_revisions": [json.loads(EXPERIMENT_LOCK.read_text())["wavepeek"]["commit"]],
    }


def materialize_dataset(matrix: dict) -> Path:
    short = matrix["wavepeek_revisions"][0][:12]
    root = CACHE / "harbor" / "datasets" / short
    temporary = root.with_name(root.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    for task_id in matrix["tasks"]:
        for arm in matrix["arms"]:
            materialize(task_id, arm, temporary)
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
    for arm in matrix["arms"]:
        expected = lock["images"][arm]["id"]
        actual = run(["docker", "image", "inspect", lock["images"][arm]["tag"], "--format", "{{.Id}}"])
        if actual != expected:
            raise RuntimeError(f"{arm} image mismatch: expected {expected}, got {actual}")
    print(
        f"preflight: trials={matrix['trial_count']} tasks={len(matrix['tasks'])} "
        f"models={len(matrix['models'])} arms={len(matrix['arms'])} attempts={matrix['attempts']}"
    )


def append_journal(record: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream, fcntl.LOCK_UN)


def execute_job(manifest: dict, command: list[str]) -> int:
    run_dir = ROOT / "runs" / manifest["run_id"]
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT) + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    result = subprocess.run(command, cwd=ROOT, env=environment)
    manifest["status"] = "harbor_complete" if result.returncode == 0 else "harbor_failed"
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest["harbor_exit_status"] = result.returncode
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    append_journal(
        {
            "run_id": manifest["run_id"],
            "created_at": manifest["created_at"],
            "finished_at": manifest["finished_at"],
            "status": manifest["status"],
            "trial_count": manifest["matrix"]["trial_count"],
            "manifest": str(manifest_path.relative_to(ROOT)),
            "manifest_sha256": sha256(manifest_path),
        }
    )
    return result.returncode


def add_matrix_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--selector", choices=["smoke"])
    parser.add_argument("--tasks", default="all")
    parser.add_argument("--models", default="all")
    parser.add_argument("--arms", default="all")
    parser.add_argument("--attempts", default="1")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("task_id")
    materialize_parser.add_argument("arm", choices=["baseline", "wavepeek"])
    subparsers.add_parser("harbor-bootstrap")
    for name in ("job", "preflight", "run"):
        matrix_parser = subparsers.add_parser(name)
        add_matrix_arguments(matrix_parser)
        matrix_parser.add_argument("--name", default="experiment")
        if name == "job":
            matrix_parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "check":
        check()
    elif args.command == "materialize":
        materialize(args.task_id, args.arm)
    elif args.command == "harbor-bootstrap":
        harbor_bootstrap()
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
                    f"models={len(matrix['models'])} arms={len(matrix['arms'])} attempts={matrix['attempts']}"
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
