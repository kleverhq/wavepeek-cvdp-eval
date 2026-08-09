import json
import tempfile
import unittest
from pathlib import Path

from scripts.trajectory import agent_types, assistant_messages, session_identity, usage


class TrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "trajectory.jsonl"

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, records):
        self.path.write_text("".join(json.dumps(record) + "\n" for record in records))

    def test_usage_includes_main_and_cache_fields_exactly(self):
        self.write(
            [
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "provider": "openrouter",
                        "model": "model",
                        "usage": {
                            "input": 10,
                            "output": 3,
                            "cacheRead": 7,
                            "cacheWrite": 2,
                            "cost": {"total": 0.25},
                        },
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "provider": "openrouter",
                        "model": "model",
                        "usage": {
                            "input": 5,
                            "output": 4,
                            "cacheRead": 1,
                            "cacheWrite": 6,
                            "cost": {"total": 0.5},
                        },
                    },
                },
            ]
        )
        self.assertEqual(
            usage(assistant_messages(self.path)),
            {
                "input": 15,
                "output": 7,
                "cacheRead": 8,
                "cacheWrite": 8,
                "piCalculatedCost": 0.75,
                "reportedCost": None,
            },
        )

    def test_identity_and_agent_type(self):
        self.write(
            [
                {"type": "model_change", "provider": "openai-codex", "modelId": "gpt-5.6-luna"},
                {"type": "thinking_level_change", "thinkingLevel": "xhigh"},
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "toolCall",
                                "name": "Agent",
                                "arguments": {"subagent_type": "general-purpose"},
                            }
                        ],
                    },
                },
            ]
        )
        self.assertEqual(
            session_identity(self.path),
            {"provider": "openai-codex", "model": "gpt-5.6-luna", "thinking": "xhigh"},
        )
        self.assertEqual(agent_types(self.path), ["general-purpose"])


if __name__ == "__main__":
    unittest.main()
