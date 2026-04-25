from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm import _build_body


class LlmBodyTests(unittest.TestCase):
    def test_build_body_keeps_sampling_params_when_thinking_is_disabled(self):
        body = _build_body(
            model_config={
                "model": "deepseek-v4-pro",
                "thinking": {"type": "disabled"},
                "temperature": 0.8,
                "topP": 0.9,
                "topK": 50,
                "maxTokens": 1800,
            },
            system_prompt="system",
            user_payload={"foo": "bar"},
            temperature=None,
            top_p=None,
            top_k=None,
            max_tokens=None,
        )

        self.assertEqual(body["model"], "deepseek-v4-pro")
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertEqual(body["temperature"], 0.8)
        self.assertEqual(body["top_p"], 0.9)
        self.assertEqual(body["top_k"], 50)
        self.assertNotIn("reasoning_effort", body)

    def test_build_body_uses_reasoning_effort_when_thinking_is_enabled(self):
        body = _build_body(
            model_config={
                "model": "deepseek-v4-pro",
                "thinking": {"type": "enabled"},
                "reasoningEffort": "high",
                "temperature": 0.8,
                "topP": 0.9,
                "topK": 50,
                "maxTokens": 4096,
            },
            system_prompt="system",
            user_payload={"foo": "bar"},
            temperature=None,
            top_p=None,
            top_k=None,
            max_tokens=None,
        )

        self.assertEqual(body["model"], "deepseek-v4-pro")
        self.assertEqual(body["thinking"], {"type": "enabled"})
        self.assertEqual(body["reasoning_effort"], "high")
        self.assertNotIn("temperature", body)
        self.assertNotIn("top_p", body)
        self.assertNotIn("top_k", body)


if __name__ == "__main__":
    unittest.main()
