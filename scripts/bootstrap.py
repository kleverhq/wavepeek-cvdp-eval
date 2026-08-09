#!/usr/bin/env python3
"""Fetch and verify the pinned CVDP sources used by the selection audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "selection" / "sources.lock.json"
RUNNER_REQUIREMENTS = ROOT / "config" / "cvdp-runner-requirements.txt"
PUBLIC_DIR = "cvdp_v1.1.0_agentic_heavy_code_generation_public"
CORE_FILES = {
    "cvdp_v1.1.0_agentic_code_generation_no_commercial.jsonl",
    "cvdp_v1.1.0_agentic_heavy_code_generation_no_commercial.jsonl",
    "cvdp_v1.1.0_nonagentic_code_generation_no_commercial.jsonl",
    f"{PUBLIC_DIR}/manifest.txt",
    f"{PUBLIC_DIR}/README.md",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"command failed: {' '.join(command)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def fetch_tooling(cache: Path, repository: str, commit: str, verify: bool) -> None:
    target = cache / "tooling"
    if not target.exists():
        target.mkdir(parents=True)
        run(["git", "init", "-q"], target)
        run(["git", "remote", "add", "origin", repository], target)
        run(["git", "fetch", "-q", "--depth", "1", "origin", commit], target)
        run(["git", "checkout", "-q", "--detach", "FETCH_HEAD"], target)
    actual = run(["git", "rev-parse", "HEAD"], target)
    if actual != commit:
        raise RuntimeError(f"tooling commit mismatch: expected {commit}, got {actual}")
    dirty = run(["git", "status", "--porcelain", "--untracked-files=no"], target)
    if dirty:
        raise RuntimeError("tooling checkout has modified tracked files")
    if verify:
        run(["git", "fsck", "--no-progress", "--connectivity-only"], target)
    print(f"tooling {actual}")


def ensure_runner_environment(cache: Path) -> None:
    environment = cache / "venv"
    python = environment / "bin" / "python"
    marker = environment / ".requirements.sha256"
    expected = sha256(RUNNER_REQUIREMENTS)
    if not python.exists():
        run([sys.executable, "-m", "venv", str(environment)])
    if not marker.exists() or marker.read_text().strip() != expected:
        run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(RUNNER_REQUIREMENTS)])
        marker.write_text(expected + "\n")
    run([str(python), "-c", "import nltk, numpy, pydantic, yaml"])
    print(f"runner_environment {expected}")


def source_path(relative: str, dataset_source: Path | None, heavy_source: Path | None) -> Path | None:
    if relative.startswith(PUBLIC_DIR + "/") and heavy_source:
        candidate = heavy_source / Path(relative).name
        if candidate.exists():
            return candidate
    if dataset_source:
        candidate = dataset_source / relative
        if candidate.exists():
            return candidate
    return None


def fetch_file(
    relative: str,
    expected: str,
    target: Path,
    base_url: str,
    dataset_source: Path | None,
    heavy_source: Path | None,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha256(target) == expected:
        print(f"verified {relative}")
        return

    local_source = source_path(relative, dataset_source, heavy_source)
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.unlink(missing_ok=True)
    if local_source:
        shutil.copyfile(local_source, temporary)
    else:
        print(f"downloading {relative}")
        with urllib.request.urlopen(base_url + relative, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, 1024 * 1024)

    actual = sha256(temporary)
    if actual != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"checksum mismatch for {relative}: expected {expected}, got {actual}")
    temporary.replace(target)
    print(f"verified {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=["cvdp"], default="cvdp")
    parser.add_argument("--all", action="store_true", help="prepare all frozen inputs, runner dependencies, and agent images")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache" / "cvdp")
    parser.add_argument("--dataset-source", type=Path, help="optional local mirror of the dataset snapshot")
    parser.add_argument("--heavy-source-dir", type=Path, help="optional local directory containing heavy bundles")
    parser.add_argument("--heavy-bundles", action="store_true", help="also fetch all 40 heavy repository bundles")
    parser.add_argument("--verify", action="store_true", help="accepted for an explicit verify-after-fetch command")
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text())
    tooling = lock["tooling"]
    dataset = lock["dataset"]
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    fetch_tooling(args.cache_dir, tooling["repository"], tooling["commit"], args.verify)
    base_url = f"{dataset['repository']}/resolve/{dataset['commit']}/"
    wanted = set(dataset["files"]) if args.heavy_bundles or args.all else CORE_FILES
    for relative in sorted(wanted):
        fetch_file(
            relative,
            dataset["files"][relative],
            args.cache_dir / "dataset" / relative,
            base_url,
            args.dataset_source,
            args.heavy_source_dir,
        )

    ensure_runner_environment(args.cache_dir)
    if args.all:
        run([sys.executable, str(ROOT / "scripts" / "build_images.py")])
    print(f"dataset {dataset['commit']} files={len(wanted)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, urllib.error.URLError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
