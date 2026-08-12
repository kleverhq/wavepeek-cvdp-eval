#!/usr/bin/env python3
"""Invoke the pinned binary unchanged and append one transparent audit record."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BINARY = Path("/opt/wavepeek/bin/wavepeek.real")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def flagged_paths(arguments: list[str], flag: str) -> list[str]:
    values: list[str] = []
    for index, argument in enumerate(arguments):
        if argument == "--":
            break
        if index and arguments[index - 1] == flag:
            values.append(argument)
        elif argument.startswith(f"{flag}="):
            values.append(argument.split("=", 1)[1])

    paths: list[str] = []
    for value in values:
        path = Path(value).expanduser()
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved not in paths:
            paths.append(resolved)
    return paths


def append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(record, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, data)
    finally:
        os.close(descriptor)


def main() -> int:
    started_at = now()
    started = time.monotonic()
    result = subprocess.run([str(BINARY), *sys.argv[1:]])
    finished_at = now()
    log = os.environ.get("WAVEPEEK_INVOCATION_LOG")
    if log:
        try:
            waveforms = flagged_paths(sys.argv[1:], "--waves")
            sources = flagged_paths(sys.argv[1:], "--source")
            record = {
                "schema_version": 1,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": round(time.monotonic() - started, 6),
                "cwd": os.getcwd(),
                "argv": sys.argv[1:],
                "subcommand": next((arg for arg in sys.argv[1:] if not arg.startswith("-")), None),
                "waveform_paths": waveforms,
                "source_paths": sources,
                "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(),
                "exit_status": result.returncode,
            }
            append_record(Path(log), record)
        except Exception:
            pass
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
