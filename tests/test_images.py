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
        self.assertEqual(result.stdout.splitlines()[0], "wavepeek v2.2.0")

    def test_wrapper_preserves_status_and_records_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            result = docker(
                "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{directory}:/logs", "-e",
                "WAVEPEEK_INVOCATION_LOG=/logs/audit.jsonl", self.treatment,
                "wavepeek", "--version",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "wavepeek v2.2.0")
            record = json.loads(log.read_text())
            self.assertEqual(record["argv"], ["--version"])
            self.assertEqual(record["exit_status"], 0)
            self.assertGreaterEqual(record["duration_seconds"], 0)
            self.assertIn("binary_sha256", record)

    def test_wrapper_retains_queried_waveform(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.vcd").write_text(
                "$timescale 1ns $end\n$scope module top $end\n$var wire 1 ! clk $end\n"
                "$upscope $end\n$enddefinitions $end\n#0\n0!\n#1\n1!\n"
            )
            result = docker(
                "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                "-v", f"{directory}:/logs", "-e",
                "WAVEPEEK_INVOCATION_LOG=/logs/audit.jsonl", self.treatment,
                "wavepeek", "info", "--waves", "/logs/test.vcd", "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads((root / "audit.jsonl").read_text())
            self.assertEqual(len(record["retained_waveforms"]), 1)
            retained = root / record["retained_waveforms"][0]["artifact"]
            self.assertEqual(retained.read_bytes(), (root / "test.vcd").read_bytes())


if __name__ == "__main__":
    unittest.main()
