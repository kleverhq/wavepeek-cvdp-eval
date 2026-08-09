#!/usr/bin/env python3
"""Invoke the pinned binary unchanged and append one transparent audit record."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BINARY = Path("/opt/wavepeek/bin/wavepeek.real")
WAVEFORM_SUFFIXES = {".vcd", ".fst", ".fsdb"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def waveform_paths(arguments: list[str]) -> list[str]:
    paths: list[str] = []
    for index, argument in enumerate(arguments):
        candidate = argument if index and arguments[index - 1] == "--waves" else argument
        path = Path(candidate).expanduser()
        if path.suffix.lower() in WAVEFORM_SUFFIXES or (path.exists() and path.is_file()):
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
        paths = waveform_paths(sys.argv[1:])
        retained = []
        for value in paths:
            source = Path(value)
            if not source.is_file():
                continue
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            destination = Path(log).parent / "waveforms-accessed" / f"{digest}-{source.name}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copyfile(source, destination)
            retained.append(
                {
                    "source": value,
                    "artifact": str(destination.relative_to(Path(log).parent)),
                    "sha256": digest,
                    "size": destination.stat().st_size,
                }
            )
        record = {
            "schema_version": 1,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": round(time.monotonic() - started, 6),
            "cwd": os.getcwd(),
            "argv": sys.argv[1:],
            "subcommand": next((arg for arg in sys.argv[1:] if not arg.startswith("-")), None),
            "waveform_paths": paths,
            "retained_waveforms": retained,
            "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(),
            "exit_status": result.returncode,
        }
        try:
            append_record(Path(log), record)
        except OSError as error:
            print(f"wavepeek: could not write invocation log: {error}", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
