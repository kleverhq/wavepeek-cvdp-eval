import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "experiment.lock.json").read_text())


def docker(*arguments, input=None):
    return subprocess.run(
        ["docker", *arguments], input=input, text=True, capture_output=True
    )


class ImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = LOCK["images"]["baseline"]["tag"]
        cls.treatment = LOCK["images"]["wavepeek"]["tag"]
        if docker("image", "inspect", cls.baseline).returncode:
            raise unittest.SkipTest("run `just build-images` before image tests")

    def test_baseline_has_no_treatment_assets(self):
        result = docker(
            "run", "--rm", self.baseline, "sh", "-lc",
            "! command -v wavepeek && test ! -e /opt/wavepeek && ! env | grep -i wavepeek",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_treatment_assets_share_locked_identity(self):
        command = (
            "set -e; wavepeek --version; test -s /opt/wavepeek/skills/wavepeek/SKILL.md; "
            "test -n \"$(find /opt/wavepeek/docs -type f -print -quit)\""
        )
        result = docker("run", "--rm", self.treatment, "sh", "-lc", command)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "wavepeek v2.2.3")

    def test_wrapper_preserves_status_and_records_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            result = docker(
                "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{directory}:/logs", "-e",
                "WAVEPEEK_INVOCATION_LOG=/logs/audit.jsonl", self.treatment,
                "wavepeek", "--version",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "wavepeek v2.2.3")
            record = json.loads(log.read_text())
            self.assertEqual(record["argv"], ["--version"])
            self.assertEqual(record["exit_status"], 0)
            self.assertGreaterEqual(record["duration_seconds"], 0)
            self.assertIn("binary_sha256", record)

    def test_wrapper_ignores_long_non_path_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            for flag in ("--signals", "--eval", "--payload"):
                arguments = ["--version", flag, "x" * 5000]
                core = docker("run", "--rm", self.treatment, "/opt/wavepeek/bin/wavepeek.real", *arguments)
                wrapped = docker(
                    "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                    "-v", f"{directory}:/logs", "-e",
                    "WAVEPEEK_INVOCATION_LOG=/logs/audit.jsonl", self.treatment,
                    "wavepeek", *arguments,
                )
                self.assertEqual(wrapped.returncode, core.returncode)
                self.assertEqual(wrapped.stdout, core.stdout)
                self.assertEqual(wrapped.stderr, core.stderr)

            records = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(records), 3)
            self.assertTrue(all(not record["waveform_paths"] for record in records))
            self.assertTrue(all(not record["source_paths"] for record in records))

    def test_wrapper_guards_long_explicit_path(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments = ["--version", f"--waves={'x' * 5000}"]
            core = docker("run", "--rm", self.treatment, "/opt/wavepeek/bin/wavepeek.real", *arguments)
            wrapped = docker(
                "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                "-v", f"{directory}:/logs", "-e",
                "WAVEPEEK_INVOCATION_LOG=/logs/audit.jsonl", self.treatment,
                "wavepeek", *arguments,
            )
            self.assertEqual(wrapped.returncode, core.returncode)
            self.assertEqual(wrapped.stdout, core.stdout)
            self.assertEqual(wrapped.stderr, core.stderr)

    def test_wrapper_telemetry_failure_preserves_core_result(self):
        core = docker("run", "--rm", self.treatment, "/opt/wavepeek/bin/wavepeek.real", "--version")
        wrapped = docker(
            "run", "--rm", "-e", "WAVEPEEK_INVOCATION_LOG=/sys/audit.jsonl",
            self.treatment, "wavepeek", "--version",
        )
        self.assertEqual(wrapped.returncode, core.returncode)
        self.assertEqual(wrapped.stdout, core.stdout)
        self.assertEqual(wrapped.stderr, core.stderr)

    def test_wrapper_respects_option_terminator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "decoy.vcd").write_text("not a waveform")
            docker(
                "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                "-v", f"{directory}:/logs", "-e",
                "WAVEPEEK_INVOCATION_LOG=/logs/audit.jsonl", self.treatment,
                "wavepeek", "--version", "--", "--waves", "/logs/decoy.vcd",
            )
            record = json.loads((root / "audit.jsonl").read_text())
            self.assertEqual(record["waveform_paths"], [])

    def test_wrapper_records_only_explicit_file_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("test.vcd", "pi-auth.json", "decoy.txt"):
                (root / name).write_text(name)
            docker(
                "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                "-v", f"{directory}:/logs", "-e",
                "WAVEPEEK_INVOCATION_LOG=/logs/audit.jsonl", self.treatment,
                "wavepeek", "--version", "--waves", "/logs/test.vcd",
                "--source=/logs/pi-auth.json", "--signals", "/logs/decoy.txt",
            )
            record = json.loads((root / "audit.jsonl").read_text())
            self.assertEqual(record["waveform_paths"], ["/logs/test.vcd"])
            self.assertEqual(record["source_paths"], ["/logs/pi-auth.json"])
            self.assertNotIn("retained_waveforms", record)
            self.assertFalse((root / "waveforms-accessed").exists())


if __name__ == "__main__":
    unittest.main()
