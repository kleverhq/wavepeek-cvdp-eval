import json
import tempfile
import unittest
from pathlib import Path

from scripts import lab


class ResultNormalizationTests(unittest.TestCase):
    def test_completed_treatment_requires_meaningful_waveform_query(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            job = run_dir / "harbor" / "job"
            trial = job / "trial-1"
            required = [
                "agent/pi.txt",
                "agent/pi/sessions/main.jsonl",
                "agent/trajectory-index.json",
                "artifacts/final.patch",
                "artifacts/agent-runtime.json",
                "artifacts/main-session-stats.json",
                "artifacts/waveforms.json",
                "verifier/test-stdout.txt",
                "verifier/reward.txt",
                "config.json",
                "lock.json",
                "trial.log",
            ]
            for relative in required:
                path = trial / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("\n")
            commit = "a" * 40
            result = {
                "task_name": "cvdp-eval/task--wavepeek-aaaaaaaaaaaa",
                "config": {"agent": {"model_name": "provider/model"}},
                "agent_result": {
                    "metadata": {
                        "provider": "provider",
                        "model": "model",
                        "reasoning": "xhigh",
                        "usage": {"input": 1, "output": 2, "cacheRead": 3, "cacheWrite": 4},
                    }
                },
                "verifier_result": {"rewards": {"reward": 1.0}},
                "started_at": "2026-01-01T00:00:00Z",
                "finished_at": "2026-01-01T00:00:05Z",
                "exception_info": None,
            }
            (trial / "result.json").write_text(json.dumps(result))
            (trial / "artifacts/wavepeek-invocations.jsonl").write_text(
                json.dumps(
                    {
                        "started_at": "2026-01-01T00:00:01Z",
                        "subcommand": "signals",
                        "waveform_paths": ["/app/out.vcd"],
                        "exit_status": 0,
                    }
                )
                + "\n"
            )
            manifest = {
                "run_id": "run",
                "harbor_job_name": "job",
                "matrix": {
                    "trial_count": 1,
                    "tasks": ["task"],
                    "model_ids": ["provider/model"],
                    "arms": ["wavepeek"],
                    "attempts": 1,
                    "wavepeek_revisions": [commit],
                },
            }
            summary, errors = lab.normalize_run(run_dir, manifest)
            self.assertEqual(errors, [])
            normalized = summary["trials"][0]
            self.assertTrue(normalized["benchmark_pass"])
            self.assertTrue(normalized["wavepeek"]["compliant"])
            self.assertEqual(normalized["runtime_seconds"], 5.0)

    def test_analysis_pairs_each_revision_with_shared_baseline(self):
        base = {
            "task_id": "task",
            "model": "provider/model",
            "attempt": 1,
            "benchmark_pass": False,
            "runtime_seconds": 1.0,
            "infrastructure_status": "complete",
            "usage": {},
            "wavepeek": {"total_calls": 0, "compliant": None},
        }
        trials = [
            {**base, "arm": "baseline"},
            {**base, "arm": "wavepeek@one", "benchmark_pass": True, "wavepeek": {"total_calls": 1, "compliant": True}},
            {**base, "arm": "wavepeek@two", "wavepeek": {"total_calls": 2, "compliant": True}},
        ]
        analysis = lab.analyze_summary(trials)
        self.assertEqual(len(analysis["pairs"]), 2)
        self.assertEqual([pair["wavepeek_arm"] for pair in analysis["pairs"]], ["wavepeek@one", "wavepeek@two"])


if __name__ == "__main__":
    unittest.main()
