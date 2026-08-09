"""Minimal Harbor Pi extension for strict pi-subagents evidence and accounting."""

from __future__ import annotations

import base64
import json
import os
import shlex
import tempfile
from pathlib import Path
from typing import override

from harbor.agents.installed.pi import Pi
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from scripts.trajectory import agent_types, assistant_messages, session_identity, usage

PI_VERSION = "0.83.0"
PI_SUBAGENTS_COMMIT = "2966cd5a33c0640de9698b56a39c11f83207a835"
RUNNER = "/opt/cvdp-pi/harbor-pi-runner.py"


class ReproduciblePi(Pi):
    """Use Harbor's Pi lifecycle while retaining and accounting for subagents."""

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        result = await self.exec_as_agent(
            environment,
            command=(
                "set -e; "
                "test \"$(pi --version)\" = '0.83.0'; "
                "test -f /opt/pi-subagents/src/index.ts; "
                "grep -q 'return readSettingsFile(globalPath())' /opt/pi-subagents/src/settings.ts; "
                "grep -q 'PI_SUBAGENTS_CONFIG_CWD' /opt/pi-subagents/src/agent-runner.ts; "
                f"test -x {RUNNER}"
            ),
        )
        if result.return_code:
            raise RuntimeError("task image does not contain the pinned Pi/pi-subagents runtime")

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        if not self.model_name or "/" not in self.model_name:
            raise ValueError("model name must be provider/model")
        provider, model = self.model_name.split("/", 1)
        thinking = str(self._flag_kwargs.get("thinking") or "")
        if thinking != "xhigh":
            raise ValueError(f"experiment requires xhigh reasoning, got {thinking!r}")
        if (provider, model) not in {
            ("openai-codex", "gpt-5.6-luna"),
            ("openrouter", "deepseek/deepseek-v4-flash-0731"),
        }:
            raise ValueError(f"uncommitted model profile: {self.model_name}")

        encoded = base64.b64encode(instruction.encode()).decode()
        auth_source = Path(os.environ.get("WAVEPEEK_EVAL_AUTH_FILE", "~/.pi/agent/auth.json")).expanduser()
        auth_records = json.loads(auth_source.read_text()) if auth_source.is_file() else {}
        if provider == "openrouter" and (key := self._get_env("OPENROUTER_API_KEY")):
            provider_record = {"type": "api_key", "key": key}
        else:
            provider_record = auth_records.get(provider)
        if not provider_record:
            raise RuntimeError(f"missing external credential for {provider}")
        with tempfile.NamedTemporaryFile("w", prefix="cvdp-auth-", suffix=".json", delete=False) as secret:
            json.dump({provider: provider_record}, secret)
            secret_path = Path(secret.name)
        secret_path.chmod(0o600)
        try:
            await environment.upload_file(secret_path, "/run/secrets/pi-auth.json")
        finally:
            secret_path.unlink(missing_ok=True)
        secured = await environment.exec(
            command="chown 1000:1000 /run/secrets/pi-auth.json && chmod 600 /run/secrets/pi-auth.json",
            user=0,
        )
        if secured.return_code:
            raise RuntimeError("could not securely stage the selected provider credential")

        env = {
            "CVDP_EVAL_PROVIDER": provider,
            "CVDP_EVAL_MODEL": model,
            "CVDP_EVAL_THINKING": thinking,
        }
        treatment = await environment.exec(
            command="test -f /opt/wavepeek/skills/wavepeek/SKILL.md"
        )
        if treatment.return_code == 0:
            env["EXPERIMENT_SKILL"] = "/opt/wavepeek/skills/wavepeek/SKILL.md"
            env["WAVEPEEK_INVOCATION_LOG"] = "/logs/artifacts/wavepeek-invocations.jsonl"
        try:
            result = await self.exec_as_agent(
                environment,
                command=f"printf %s {shlex.quote(encoded)} | base64 -d | python3 {RUNNER}",
                env=env,
            )
        finally:
            await environment.exec(command="rm -f /run/secrets/pi-auth.json", user=0)
        if result.return_code:
            raise RuntimeError(f"Pi runner failed with status {result.return_code}")
        patch = await environment.exec(
            command=(
                "git --git-dir=/opt/cvdp-baseline --work-tree=/app add -N -A && "
                "git --git-dir=/opt/cvdp-baseline --work-tree=/app diff --binary HEAD > /logs/artifacts/final.patch && "
                "git --git-dir=/opt/cvdp-baseline --work-tree=/app status --porcelain=v1 > /logs/artifacts/git-status.txt"
            ),
            user=0,
        )
        if patch.return_code:
            raise RuntimeError("could not retain final agent patch")

    @override
    def populate_context_post_run(self, context: AgentContext) -> None:
        main = self.logs_dir / "pi.txt"
        if not main.is_file():
            raise RuntimeError("Pi main event trajectory is missing")
        transcript_root = self.logs_dir / "pi" / "tmp"
        transcripts = sorted(transcript_root.rglob("*.output")) if transcript_root.exists() else []
        session_root = self.logs_dir / "pi" / "subagent-sessions"
        child_sessions = sorted(session_root.rglob("*.jsonl")) if session_root.exists() else []

        main_messages = assistant_messages(main)
        child_messages = [message for path in transcripts for message in assistant_messages(path)]
        all_messages = main_messages + child_messages
        expected_provider, expected_model = self.model_name.split("/", 1)
        mismatches = [
            {"provider": message.get("provider"), "model": message.get("model")}
            for message in all_messages
            if message.get("provider") != expected_provider or message.get("model") != expected_model
        ]
        if not all_messages:
            raise RuntimeError("Pi trajectory contains no assistant messages")
        if mismatches:
            raise RuntimeError(f"provider/model fallback detected: {mismatches[:3]}")
        if transcripts and not child_sessions:
            raise RuntimeError("subagent transcripts exist but persistent child sessions are missing")
        main_sessions = sorted((self.logs_dir / "pi" / "sessions").rglob("*.jsonl"))
        if len(main_sessions) != 1:
            raise RuntimeError(f"expected one authoritative main session, found {len(main_sessions)}")
        identities = [session_identity(path) for path in main_sessions + child_sessions]
        expected_identity = {
            "provider": expected_provider,
            "model": expected_model,
            "thinking": "xhigh",
        }
        if any(identity != expected_identity for identity in identities):
            raise RuntimeError(f"session provider/model/reasoning mismatch: {identities}")
        requested_types = agent_types(main_sessions[0])
        if any(agent_type != "general-purpose" for agent_type in requested_types):
            raise RuntimeError(f"unexpected subagent type requested: {requested_types}")
        nested_types = [agent_type for path in transcripts for agent_type in agent_types(path)]
        if nested_types:
            raise RuntimeError(f"nested subagent delegation detected: {nested_types}")

        main_usage = usage(main_messages)
        subagent_usage = [
            {"trajectory": str(path.relative_to(self.logs_dir)), **usage(assistant_messages(path))}
            for path in transcripts
        ]
        totals = usage(all_messages)
        context.n_input_tokens = int(totals["input"]) + int(totals["cacheRead"])
        context.n_output_tokens = int(totals["output"])
        context.n_cache_tokens = int(totals["cacheRead"])
        context.cost_usd = None
        context.metadata = {
            "provider": expected_provider,
            "model": expected_model,
            "reasoning": "xhigh",
            "main_trajectory": str(main.relative_to(self.logs_dir)),
            "subagent_transcripts": [str(path.relative_to(self.logs_dir)) for path in transcripts],
            "subagent_sessions": [str(path.relative_to(self.logs_dir)) for path in child_sessions],
            "session_identities": identities,
            "requested_subagent_types": requested_types,
            "main_usage": main_usage,
            "subagent_usage": subagent_usage,
            "usage": totals,
            "oauth_cost_note": (
                "Pi usage retained; no monetary cost asserted for subscription-backed OAuth"
                if expected_provider == "openai-codex"
                else None
            ),
            "pi_version": PI_VERSION,
            "pi_subagents_commit": PI_SUBAGENTS_COMMIT,
        }
        (self.logs_dir / "trajectory-index.json").write_text(
            json.dumps(context.metadata, indent=2, sort_keys=True) + "\n"
        )
