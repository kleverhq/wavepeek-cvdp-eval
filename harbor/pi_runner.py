#!/usr/bin/env python3
"""Run one isolated Pi RPC session and retain complete main/subagent evidence."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_ROOT = Path("/opt/cvdp-pi/config")
SUBAGENT_SOURCE = Path("/opt/cvdp-pi/general-purpose.md")
REASONING_LEVELS = {"off", "minimal", "low", "medium", "high", "xhigh", "max"}


def write_json(path: Path, value: object, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.chmod(temporary, mode)
    temporary.replace(path)


def configure(provider: str, model: str, thinking: str, profile: dict) -> Path:
    if thinking not in REASONING_LEVELS:
        raise RuntimeError(f"unsupported Pi reasoning level: {thinking}")
    agent_dir = Path(f"/tmp/cvdp-pi-{os.getuid()}")
    shutil.rmtree(agent_dir, ignore_errors=True)
    agent_dir.mkdir(mode=0o700)
    model_name = f"{provider}/{model}"
    write_json(
        agent_dir / "settings.json",
        {
            "defaultProvider": provider,
            "defaultModel": model,
            "defaultThinkingLevel": thinking,
            "enabledModels": [model_name],
            "defaultProjectTrust": "never",
            "enableInstallTelemetry": False,
            "enableAnalytics": False,
            "packages": [],
            "extensions": [],
            "skills": [],
            "prompts": [],
            "themes": [],
        },
    )
    subagents = json.loads((CONFIG_ROOT / "pi" / "subagents.json").read_text())
    write_json(agent_dir / "subagents.json", subagents)
    agents = agent_dir / "agents"
    agents.mkdir()
    agent_definition = SUBAGENT_SOURCE.read_text().replace("__INHERIT_PARENT_THINKING__", thinking)
    (agents / "general-purpose.md").write_text(agent_definition)
    shutil.copyfile(CONFIG_ROOT / "pi" / "models-store.json", agent_dir / "models-store.json")

    auth_path = agent_dir / "auth.json"
    source = Path("/run/secrets/pi-auth.json")
    auth = json.loads(source.read_text()) if source.is_file() else {}
    record = auth.get(provider)
    if not record:
        raise RuntimeError(f"missing credential for {provider}")
    write_json(auth_path, {provider: record})

    provider_config = {}
    if profile.get("compat"):
        provider_config["modelOverrides"] = {model: {"compat": profile["compat"]}}
    write_json(agent_dir / "models.json", {"providers": {provider: provider_config}})
    return agent_dir


def command(provider: str, model: str, thinking: str, session: Path) -> list[str]:
    result = [
        "pi",
        "--mode",
        "rpc",
        "--no-approve",
        "--session",
        str(session),
        "--session-dir",
        "/logs/agent/pi/sessions",
        "--provider",
        provider,
        "--model",
        model,
        "--thinking",
        thinking,
        "--models",
        f"{provider}/{model}:{thinking}",
        "--no-extensions",
        "--extension",
        "/opt/pi-subagents/src/index.ts",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
    ]
    if skill := os.environ.get("EXPERIMENT_SKILL"):
        result.extend(["--skill", skill])
    return result


def send(process: subprocess.Popen[str], message: dict) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def main() -> int:
    provider = os.environ["CVDP_EVAL_PROVIDER"]
    model = os.environ["CVDP_EVAL_MODEL"]
    thinking = os.environ["CVDP_EVAL_THINKING"]
    profile = json.loads(os.environ["CVDP_EVAL_MODEL_PROFILE"])
    if (profile.get("provider"), profile.get("model"), profile.get("reasoning")) != (provider, model, thinking):
        raise RuntimeError("resolved model profile does not match requested provider/model/reasoning")
    instruction = sys.stdin.read()
    if not instruction:
        raise RuntimeError("empty Harbor instruction")

    logs = Path("/logs/agent")
    pi_logs = logs / "pi"
    artifacts = Path("/logs/artifacts")
    for path in (logs, pi_logs / "sessions", pi_logs / "subagent-sessions", pi_logs / "tmp", artifacts):
        path.mkdir(parents=True, exist_ok=True)
    agent_dir = configure(provider, model, thinking, profile)
    os.environ.update(
        {
            "HOME": str(agent_dir.parent / "home"),
            "PI_CODING_AGENT_DIR": str(agent_dir),
            "PI_CODING_AGENT_SESSION_DIR": str(pi_logs / "subagent-sessions"),
            "PI_SUBAGENTS_CONFIG_CWD": str(agent_dir),
            "TMPDIR": str(pi_logs / "tmp"),
            "PI_OFFLINE": "1",
            "PI_TELEMETRY": "0",
            "PI_SKIP_VERSION_CHECK": "1",
        }
    )
    Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)
    runtime = {
        "schema_version": 1,
        "provider": provider,
        "model": model,
        "reasoning": thinking,
        "pi_version": subprocess.run(["pi", "--version"], text=True, capture_output=True, check=True).stdout.strip(),
        "pi_subagents_commit": "2966cd5a33c0640de9698b56a39c11f83207a835",
        "treatment_skill_available": bool(os.environ.get("EXPERIMENT_SKILL")),
    }
    write_json(artifacts / "agent-runtime.json", runtime, 0o644)

    session = pi_logs / "sessions" / "main.jsonl"
    stderr_file = (logs / "pi-stderr.log").open("w")
    process = subprocess.Popen(
        command(provider, model, thinking, session),
        cwd="/app",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_file,
        text=True,
        bufsize=1,
    )
    send(process, {"id": "task", "type": "prompt", "message": instruction})

    settled = False
    pending = set()
    records: dict[str, dict] = {}
    last_assistant: dict | None = None
    with (logs / "pi.txt").open("w") as output:
        assert process.stdout is not None
        for line in process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                output.write(line)
                output.flush()
                print(line, end="", flush=True)
                continue
            if event.get("type") != "message_update":
                compact = json.dumps(event, separators=(",", ":"))
                output.write(compact + "\n")
                output.flush()
                print(compact, flush=True)
            message = event.get("message") or {}
            if event.get("type") == "message_end" and message.get("role") == "assistant":
                last_assistant = message
            if event.get("type") == "agent_settled" and not settled:
                settled = True
                pending = {"state", "final", "stats"}
                send(process, {"id": "state", "type": "get_state"})
                send(process, {"id": "final", "type": "get_last_assistant_text"})
                send(process, {"id": "stats", "type": "get_session_stats"})
            event_id = event.get("id")
            if event_id in pending and event.get("type") == "response":
                records[event_id] = event
                pending.remove(event_id)
                if not pending:
                    break

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    stderr_file.close()
    if not settled:
        raise RuntimeError(f"Pi exited before agent_settled (status {process.returncode})")
    for key in ("state", "final", "stats"):
        if not records.get(key, {}).get("success"):
            raise RuntimeError(f"Pi RPC did not return successful {key} evidence")
    state = records["state"]["data"]
    if state["model"]["provider"] != provider or state["model"]["id"] != model:
        raise RuntimeError("Pi resolved a different provider/model")
    if state["thinkingLevel"] != thinking:
        raise RuntimeError("Pi resolved a different reasoning level")
    (artifacts / "final-response.txt").write_text(records["final"]["data"].get("text") or "")
    write_json(artifacts / "main-session-stats.json", records["stats"]["data"], 0o644)
    if last_assistant and last_assistant.get("stopReason") == "error":
        print(
            f"terminal assistant error: {last_assistant.get('errorMessage') or 'unknown error'}",
            file=sys.stderr,
        )
        return 75
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"pi runner error: {error}", file=sys.stderr)
        raise SystemExit(1)
