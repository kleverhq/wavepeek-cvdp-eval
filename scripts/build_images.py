#!/usr/bin/env python3
"""Build and lock the two Milestone 2 agent image targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "agent" / ".build"
LOCK_PATH = ROOT / "experiment.lock.json"
CVDP_IMAGE = "nvidia/cvdp-sim:v1.0.0"
CVDP_IMAGE_ID = "sha256:b4225673ee3ecc81b6e383ada63929b6b916f75502a85323f5b5d73b29340af2"
WAVEPEEK_REPOSITORY = "https://github.com/kleverhq/wavepeek.git"
WAVEPEEK_SHA = "a27a96b557cb7b9df970fbfef65a5c8354befbc9"
PI_SUBAGENTS_REPOSITORY = "https://github.com/tintinweb/pi-subagents.git"
PI_SUBAGENTS_SHA = "2966cd5a33c0640de9698b56a39c11f83207a835"
PI_SUBAGENTS_ARCHIVE_SHA256 = "49090d5a52820dcee60666a80c0cf4dd851c7d8a8d02dc7d5446156d438ffeab"
NODE_IMAGE = "node@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94"
RUST_IMAGE = "rust@sha256:d0a4aa3ca2e1088ac0c81690914a0d810f2eee188197034edf366ed010a2b382"
PI_NPM_INTEGRITY = "sha512-uYhF+FsZxogoSX/AxBcUdiY+ZklubwaXyAoEGA2eQwsHcyEAhUYIKh/WLXe/a8+k8eTCmxb+ZN2Zo9mzQtzbWw=="
PI_GIT_COMMIT = "845d6ff1f6643aba440341cce877ce1c43ebbc39"
SOURCE_ARTIFACTS = ROOT / "artifacts" / "sources"
CVDP_IMAGE_ARTIFACT = ROOT / "artifacts" / "images" / "cvdp-sim-b4225673ee3e.tar.gz"
CVDP_IMAGE_ARTIFACT_SHA256 = "9e12c68c69f2e22e37ce78260d7c3cda5f18b82311056a16423b1e6376d61bc2"


def run(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"command failed: {' '.join(command)}\n{result.stdout}")
    return result.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checkout(repository: str, commit: str, name: str) -> tuple[Path, str]:
    local = Path(repository).expanduser()
    if local.is_dir():
        worktree = local.resolve()
        if run(["git", "status", "--porcelain"], worktree):
            raise RuntimeError(f"WavePeek working tree is dirty: {worktree}")
        try:
            source_url = run(["git", "remote", "get-url", "origin"], worktree)
        except RuntimeError:
            source_url = f"local:{worktree}"
    else:
        worktree = ROOT / ".cache" / "sources" / name
        if not worktree.exists():
            worktree.parent.mkdir(parents=True, exist_ok=True)
            run(["git", "clone", "--filter=blob:none", "--no-checkout", repository, str(worktree)])
        source_url = repository
        run(["git", "fetch", "--quiet", "origin", commit], worktree)
    if source_url.startswith("http"):
        source_url = source_url.rstrip("/").removesuffix(".git")
    resolved = run(["git", "rev-parse", f"{commit}^{{commit}}"], worktree)
    if resolved != commit:
        raise RuntimeError(f"source commit mismatch for {name}: expected {commit}, got {resolved}")
    return worktree, source_url


def archive(repository: str, commit: str, name: str, output: Path) -> tuple[str, str]:
    worktree, source_url = checkout(repository, commit, name)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    with temporary.open("wb") as stream:
        result = subprocess.run(["git", "archive", "--format=tar", commit], cwd=worktree, stdout=stream)
    if result.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"git archive failed for {name}")
    temporary.replace(output)
    return sha256(output), source_url


def member_hash(archive_path: Path, member: str) -> str:
    with tarfile.open(archive_path) as source:
        stream = source.extractfile(member)
        if stream is None:
            raise RuntimeError(f"{member} missing from {archive_path}")
        return hashlib.sha256(stream.read()).hexdigest()


def image_id(image: str) -> str:
    return run(["docker", "image", "inspect", image, "--format", "{{.Id}}"])


def copy_from_image(image: str, source: str, destination: Path) -> None:
    container = run(["docker", "create", image])
    try:
        run(["docker", "cp", f"{container}:{source}", str(destination)])
    finally:
        subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def retain_source_archive(source: Path, name: str, commit: str, digest: str) -> Path:
    SOURCE_ARTIFACTS.mkdir(parents=True, exist_ok=True)
    destination = SOURCE_ARTIFACTS / f"{name}-{commit}-{digest}.tar"
    if destination.exists() and sha256(destination) != digest:
        raise RuntimeError(f"retained source artifact checksum mismatch: {destination}")
    if not destination.exists():
        shutil.copyfile(source, destination)
    return destination


def ensure_cvdp_image() -> None:
    try:
        current = image_id(CVDP_IMAGE)
    except RuntimeError:
        current = ""
    if current != CVDP_IMAGE_ID:
        try:
            run(["docker", "pull", CVDP_IMAGE])
        except RuntimeError:
            pass
    if image_id(CVDP_IMAGE) != CVDP_IMAGE_ID:
        if not CVDP_IMAGE_ARTIFACT.exists() or sha256(CVDP_IMAGE_ARTIFACT) != CVDP_IMAGE_ARTIFACT_SHA256:
            raise RuntimeError("exact CVDP simulator image is missing from the registry and no verified local artifact was supplied")
        run(["docker", "load", "-i", str(CVDP_IMAGE_ARTIFACT)])
    if image_id(CVDP_IMAGE) != CVDP_IMAGE_ID:
        raise RuntimeError("local CVDP simulator image does not match selection/sources.lock.json")
    if CVDP_IMAGE_ARTIFACT.exists() and sha256(CVDP_IMAGE_ARTIFACT) != CVDP_IMAGE_ARTIFACT_SHA256:
        raise RuntimeError("CVDP simulator image artifact checksum mismatch")


def docker_context() -> bytes:
    paths = [
        ROOT / "agent" / "Dockerfile",
        ROOT / "agent" / "patch-pi-subagents.py",
        ROOT / "agent" / "wavepeek-wrapper.py",
        ROOT / "agent" / "common" / "general-purpose.md",
        BUILD_DIR / "treatment-source.tar",
        BUILD_DIR / "pi-subagents-source.tar",
        ROOT / "config" / "experiment.json",
        ROOT / "config" / "pi" / "models-store.json",
        ROOT / "config" / "pi" / "subagents.json",
        *sorted((ROOT / "config" / "models").glob("*.json")),
    ]
    executable = {"agent/patch-pi-subagents.py", "agent/wavepeek-wrapper.py"}
    with tempfile.TemporaryFile() as stream:
        with tarfile.open(fileobj=stream, mode="w", format=tarfile.GNU_FORMAT) as archive:
            for path in sorted(paths):
                relative = str(path.relative_to(ROOT))
                info = archive.gettarinfo(str(path), arcname=relative)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o755 if relative in executable else 0o644
                with path.open("rb") as source_file:
                    archive.addfile(info, source_file)
        stream.seek(0)
        return stream.read()


def build(
    source: str,
    commit: str,
    update_lock: bool,
    allow_unlocked: bool = False,
    output_manifest: Path | None = None,
) -> dict:
    ensure_cvdp_image()

    wavepeek_archive = BUILD_DIR / "treatment-source.tar"
    subagents_archive = BUILD_DIR / "pi-subagents-source.tar"
    wavepeek_source_hash, wavepeek_url = archive(source, commit, "wavepeek", wavepeek_archive)
    wavepeek_artifact = retain_source_archive(wavepeek_archive, "wavepeek", commit, wavepeek_source_hash)
    subagents_source_hash, subagents_url = archive(
        PI_SUBAGENTS_REPOSITORY, PI_SUBAGENTS_SHA, "pi-subagents", subagents_archive
    )
    if subagents_source_hash != PI_SUBAGENTS_ARCHIVE_SHA256:
        raise RuntimeError("pi-subagents source archive checksum mismatch")

    common_args = [
        "--build-arg", f"CVDP_SIM_IMAGE={CVDP_IMAGE}",
        "--build-arg", f"PI_NPM_INTEGRITY={PI_NPM_INTEGRITY}",
        "--build-arg", f"PI_GIT_COMMIT={PI_GIT_COMMIT}",
        "--build-arg", f"PI_SUBAGENTS_SHA={PI_SUBAGENTS_SHA}",
        "--build-arg", f"PI_SUBAGENTS_SOURCE_SHA256={subagents_source_hash}",
        "-f", "agent/Dockerfile", "-",
    ]
    context = docker_context()
    subprocess.run(["docker", "build", "--target", "baseline", "-t", "cvdp-pi-agent:baseline", *common_args], cwd=ROOT, input=context, check=True)
    treatment_tag = f"cvdp-pi-agent:wavepeek-{commit[:12]}"
    subprocess.run(
        [
            "docker", "build", "--target", "wavepeek", "-t", treatment_tag,
            "--build-arg", f"WAVEPEEK_SHA={commit}",
            "--build-arg", f"WAVEPEEK_SOURCE_SHA256={wavepeek_source_hash}",
            *common_args,
        ],
        cwd=ROOT,
        input=context,
        check=True,
    )

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        binary = temporary / "wavepeek.real"
        skill = temporary / "SKILL.md"
        docs = temporary / "docs"
        copy_from_image(treatment_tag, "/opt/wavepeek/bin/wavepeek.real", binary)
        copy_from_image(treatment_tag, "/opt/wavepeek/skills/wavepeek/SKILL.md", skill)
        copy_from_image(treatment_tag, "/opt/wavepeek/docs", docs)
        binary_hash = sha256(binary)
        skill_hash = sha256(skill)
        docs_hash = hashlib.sha256(
            b"".join(
                path.relative_to(docs).as_posix().encode() + b"\0" + path.read_bytes()
                for path in sorted(docs.rglob("*")) if path.is_file()
            )
        ).hexdigest()

    versions = run(
        [
            "docker", "run", "--rm", "--entrypoint", "sh", treatment_tag, "-lc",
            "printf 'wavepeek='; /opt/wavepeek/bin/wavepeek.real --version; "
            "printf 'pi='; pi --version; printf 'node='; node --version; printf 'npm='; npm --version",
        ]
    )
    lock = {
        "schema_version": 1,
        "cvdp": {
            "tooling_commit": "8e894cf74414ab1eaea1e2b4e80a02f123df07b6",
            "dataset_commit": "5b807d945f6a99aa645f7e43a64a2115e281b4bf",
            "sources_lock_sha256": sha256(ROOT / "selection" / "sources.lock.json"),
            "runner_requirements_path": "config/cvdp-runner-requirements.txt",
            "runner_requirements_sha256": sha256(ROOT / "config" / "cvdp-runner-requirements.txt"),
            "selected_manifest_sha256": sha256(ROOT / "selection" / "selected.jsonl"),
        },
        "simulator_image": {
            "tag": CVDP_IMAGE,
            "id": CVDP_IMAGE_ID,
            "image_artifact": str(CVDP_IMAGE_ARTIFACT.relative_to(ROOT)),
            "image_artifact_sha256": CVDP_IMAGE_ARTIFACT_SHA256,
            "dockerfile_sha256": "79049c0dff0a64d277064485bfb1706b7e3699c6181c353184452146dbf60164",
            "requirements_sha256": "e594351e5012acfb0ae6884fd213b9ac356e570ed2830c8ac9a59f0886e34514",
            "base_rootfs_layer": "sha256:123a078714d5ea9382d4d9f550753aefce8b34ec5ae11ae8273038d3bcbb943f",
            "source_commits": {
                "iverilog": "30a7d1a11b7586aa0fc868e509f04f514effc0ad",
                "yosys": "8009186e8ce840253537478cf36162346caac51c",
                "verilator": "3e4c8a51d1a1ca93f6252289e4ddc125a342ef02",
            },
            "versions": {"cocotb": "2.0.1", "pytest": "8.3.2", "iverilog": "13.0", "yosys": "0.40", "verilator": "5.038", "uv": "0.11.20"},
        },
        "node": {"version": "22.22.0", "image": NODE_IMAGE},
        "rust": {"version": "1.93.0", "image": RUST_IMAGE},
        "pi": {
            "package": "@earendil-works/pi-coding-agent",
            "version": "0.83.0",
            "commit": PI_GIT_COMMIT,
            "npm_integrity": PI_NPM_INTEGRITY,
            "model_catalog_path": "config/pi/models-store.json",
            "model_catalog_sha256": sha256(ROOT / "config" / "pi" / "models-store.json"),
        },
        "pi_subagents": {
            "repository": subagents_url,
            "commit": PI_SUBAGENTS_SHA,
            "source_archive_sha256": subagents_source_hash,
            "package_lock_sha256": member_hash(subagents_archive, "package-lock.json"),
            "project_isolation_patch": "agent/patch-pi-subagents.py",
            "project_isolation_patch_sha256": sha256(ROOT / "agent" / "patch-pi-subagents.py"),
            "settings_path": "config/pi/subagents.json",
            "settings_sha256": sha256(ROOT / "config" / "pi" / "subagents.json"),
        },
        "wavepeek": {
            "repository": wavepeek_url,
            "commit": commit,
            "source_archive_sha256": wavepeek_source_hash,
            "source_artifact": str(wavepeek_artifact.relative_to(ROOT)),
            "cargo_lock_sha256": member_hash(wavepeek_archive, "Cargo.lock"),
            "binary_sha256": binary_hash,
            "skill_sha256": skill_hash,
            "docs_sha256": docs_hash,
            "version_output": versions.splitlines()[0].removeprefix("wavepeek="),
        },
        "model_configs": {
            path.stem: sha256(path)
            for path in sorted((ROOT / "config" / "models").glob("*.json"))
        },
        "experiment_config_sha256": sha256(ROOT / "config" / "experiment.json"),
        "images": {
            "baseline": {"tag": "cvdp-pi-agent:baseline", "id": image_id("cvdp-pi-agent:baseline")},
            "wavepeek": {"tag": treatment_tag, "id": image_id(treatment_tag)},
        },
    }
    rendered = json.dumps(lock, indent=2, sort_keys=True) + "\n"
    if allow_unlocked:
        output_manifest = output_manifest or ROOT / ".cache" / "wavepeek" / commit / "manifest.json"
        output_manifest.parent.mkdir(parents=True, exist_ok=True)
        output_manifest.write_text(rendered)
    elif LOCK_PATH.exists() and not update_lock:
        if LOCK_PATH.read_text() != rendered:
            raise RuntimeError("build output differs from experiment.lock.json; inspect it and rerun with --update-lock for an intentional new experiment identity")
    elif not update_lock:
        raise RuntimeError("experiment.lock.json does not exist; use --update-lock to create it")
    else:
        LOCK_PATH.write_text(rendered)
    return lock


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wavepeek-repo", default=WAVEPEEK_REPOSITORY)
    parser.add_argument("--wavepeek-sha", default=WAVEPEEK_SHA)
    parser.add_argument("--update-lock", action="store_true", help="accept and write a new default experiment identity")
    parser.add_argument("--allow-unlocked", action="store_true", help="build a candidate without changing experiment.lock.json")
    parser.add_argument("--output-manifest", type=Path)
    args = parser.parse_args()
    if args.update_lock and args.allow_unlocked:
        raise ValueError("--update-lock and --allow-unlocked are mutually exclusive")
    if len(args.wavepeek_sha) != 40 or any(character not in "0123456789abcdef" for character in args.wavepeek_sha):
        raise ValueError("--wavepeek-sha must be a full lowercase Git SHA")
    lock = build(
        args.wavepeek_repo,
        args.wavepeek_sha,
        args.update_lock,
        args.allow_unlocked,
        args.output_manifest,
    )
    print(f"baseline={lock['images']['baseline']['id']}")
    print(f"wavepeek={lock['images']['wavepeek']['id']}")
    print(f"wavepeek_commit={lock['wavepeek']['commit']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
