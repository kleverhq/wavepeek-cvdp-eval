import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import lab


class FrozenSelectionTests(unittest.TestCase):
    def test_frozen_selection(self):
        rows = lab.selected_rows()
        self.assertEqual(len(rows), 18)
        self.assertEqual(sum(row["split"] == "traditional" for row in rows), 10)
        self.assertEqual(sum(row["split"] == "heavy" for row in rows), 8)

    def test_exact_model_profiles(self):
        lab.check()


class MaterializationTests(unittest.TestCase):
    task_id = "cvdp_agentic_axis_broadcaster_0001"

    def setUp(self):
        if not lab.dataset_dir().is_dir():
            self.skipTest("run `just bootstrap` before materialization tests")
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def tree_hash(root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(root).as_posix().encode())
                digest.update(b"\0")
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def test_arms_differ_only_by_declared_treatment(self):
        baseline = lab.materialize(self.task_id, "baseline", self.root / "baseline")
        treatment = lab.materialize(self.task_id, "wavepeek", self.root / "treatment")
        baseline_prompt = (baseline / "instruction.md").read_text()
        treatment_prompt = (treatment / "instruction.md").read_text()
        self.assertEqual(treatment_prompt, baseline_prompt + "\n\n" + lab.WAVEPEEK_INSTRUCTION)
        self.assertNotIn("wavepeek", baseline_prompt.lower())
        baseline_files = {
            path.relative_to(baseline).as_posix()
            for path in baseline.rglob("*") if path.is_file()
        }
        self.assertNotIn("solution/solve.sh", baseline_files)
        self.assertTrue((baseline / "tests/src/test_runner.py").is_file())
        self.assertFalse((baseline / "environment/workspace/tests/src/test_runner.py").exists())
        self.assertTrue((baseline / "environment/workspace/rtl/axis_broadcast.sv").is_file())

    def test_materialization_is_deterministic(self):
        first = lab.materialize(self.task_id, "baseline", self.root / "one")
        first_hash = self.tree_hash(first)
        second = lab.materialize(self.task_id, "baseline", self.root / "one")
        self.assertEqual(first_hash, self.tree_hash(second))

    def test_heavy_task_uses_sanitized_external_tree(self):
        task = lab.materialize(
            "cvdp_agentic_heavy_2dconv-FPGA_0009", "baseline", self.root / "heavy"
        )
        workspace = task / "environment/workspace"
        self.assertTrue((workspace / "src/verilog/Modules/Convolutor/Convolutor.v").is_file())
        self.assertFalse((workspace / ".git").exists())

    def test_baseline_context_has_no_treatment_reference(self):
        task = lab.materialize(self.task_id, "baseline", self.root / "scan")
        text = "\n".join(
            path.read_text(errors="ignore")
            for path in task.rglob("*")
            if path.is_file() and path.name != "task-metadata.json"
        ).lower()
        self.assertNotIn("wavepeek", text)


if __name__ == "__main__":
    unittest.main()
