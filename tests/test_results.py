import hashlib
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
                "artifacts/logs/artifacts/final.patch",
                "artifacts/logs/artifacts/agent-runtime.json",
                "artifacts/logs/artifacts/main-session-stats.json",
                "artifacts/logs/artifacts/waveforms.json",
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
            retained_waveform = trial / "artifacts/logs/artifacts/waveforms/out.vcd"
            retained_waveform.parent.mkdir(parents=True, exist_ok=True)
            retained_waveform.write_bytes(b"waveform")
            retained_hash = hashlib.sha256(retained_waveform.read_bytes()).hexdigest()
            (trial / "artifacts/logs/artifacts/wavepeek-invocations.jsonl").write_text(
                json.dumps(
                    {
                        "started_at": "2026-01-01T00:00:01Z",
                        "subcommand": "signal",
                        "waveform_paths": ["/app/out.vcd"],
                        "retained_waveforms": [{"artifact": "waveforms/out.vcd", "sha256": retained_hash}],
                        "exit_status": 0,
                    }
                )
                + "\n"
            )
            manifest = {
                "run_id": "run",
                "harbor_job_dir": "harbor",
                "harbor_job_name": "job",
                "matrix": {
                    "trial_count": 1,
                    "tasks": ["task"],
                    "models": ["profile"],
                    "model_ids": ["provider/model"],
                    "arms": ["wavepeek"],
                    "arm_variants": 1,
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

            (trial / "agent/pi.txt").write_text(
                json.dumps(
                    {
                        "type": "message_end",
                        "message": {
                            "role": "assistant",
                            "stopReason": "error",
                            "errorMessage": "429: temporarily rate-limited",
                        },
                    }
                )
                + "\n"
            )
            summary, errors = lab.normalize_run(run_dir, manifest)
            self.assertEqual(summary["trials"][0]["infrastructure_status"], "failed")
            self.assertEqual(
                summary["trials"][0]["terminal_assistant_error"],
                "429: temporarily rate-limited",
            )
            self.assertTrue(any("terminal assistant error" in error for error in errors))

            result["exception_info"] = {
                "exception_type": "AgentTimeoutError",
                "exception_message": "timed out",
            }
            (trial / "result.json").write_text(json.dumps(result))
            _, errors = lab.normalize_run(run_dir, manifest)
            self.assertTrue(any("AgentTimeoutError" in error for error in errors))

    def test_analysis_pairs_each_revision_with_shared_baseline(self):
        base = {
            "task_id": "task",
            "model": "provider/model",
            "attempt": 1,
            "benchmark_pass": False,
            "runtime_seconds": 1.0,
            "infrastructure_status": "complete",
            "usage": {},
            "wavepeek": {
                "total_calls": 0,
                "successful_meaningful_calls": 0,
                "total_duration_seconds": 0.0,
                "compliant": None,
            },
        }
        trials = [
            {**base, "arm": "baseline"},
            {
                **base,
                "arm": "wavepeek@one",
                "benchmark_pass": True,
                "wavepeek": {"total_calls": 1, "successful_meaningful_calls": 1, "total_duration_seconds": 0.1, "compliant": True},
            },
            {
                **base,
                "arm": "wavepeek@two",
                "wavepeek": {"total_calls": 2, "successful_meaningful_calls": 2, "total_duration_seconds": 0.2, "compliant": True},
            },
        ]
        trials.append({**base, "arm": "baseline", "benchmark_pass": True, "infrastructure_status": "failed"})
        analysis = lab.analyze_summary(trials)
        self.assertEqual(len(analysis["pairs"]), 2)
        self.assertEqual([pair["wavepeek_arm"] for pair in analysis["pairs"]], ["wavepeek@one", "wavepeek@two"])
        self.assertTrue(all(pair["baseline_attempts"] == 1 for pair in analysis["pairs"]))


if __name__ == "__main__":
    unittest.main()
