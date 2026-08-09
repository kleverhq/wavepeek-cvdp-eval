"""Pure helpers for validating and accounting Pi JSONL trajectories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def records(path: Path) -> list[dict[str, Any]]:
    result = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result


def assistant_messages(path: Path) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for record in records(path):
        if record.get("type") == "message_end":
            message = record.get("message") or {}
        elif record.get("type") in {"assistant", "message"}:
            message = record.get("message") or {}
        else:
            continue
        if message.get("role") == "assistant":
            messages.append(message)
    return messages


def usage(messages: list[dict[str, Any]]) -> dict[str, float | int | None]:
    total: dict[str, float | int | None] = {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
        "piCalculatedCost": 0.0,
        "reportedCost": None,
    }
    for message in messages:
        item = message.get("usage") or {}
        for key in ("input", "output", "cacheRead", "cacheWrite"):
            total[key] += int(item.get(key, 0) or 0)
        total["piCalculatedCost"] += float((item.get("cost") or {}).get("total", 0.0) or 0.0)
    return total


def agent_types(path: Path) -> list[str]:
    types = []
    for record in records(path):
        message = record.get("message") or {}
        for content in message.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") != "toolCall" or content.get("name") != "Agent":
                continue
            subagent_type = (content.get("arguments") or {}).get("subagent_type")
            if subagent_type:
                types.append(subagent_type)
    return types


def session_identity(path: Path) -> dict[str, str | None]:
    identity = {"provider": None, "model": None, "thinking": None}
    for record in records(path):
        if record.get("type") == "model_change":
            identity["provider"] = record.get("provider")
            identity["model"] = record.get("modelId")
        elif record.get("type") == "thinking_level_change":
            identity["thinking"] = record.get("thinkingLevel")
    return identity
