from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from creative.contracts import scene_draft_contract
from llm import _build_body, call_json_task, call_text_task

SCENE_PREMISE_LABEL = "\u573a\u666f\u547d\u9898"
WORLD_SCENE_LABEL = "\u573a\u666f\u6b63\u6587"
WORLD_SCENE_JSON = (
    '{"\\u573a\\u666f\\u547d\\u9898":"\\u9ec4\\u660f\\u7684\\u6cb3\\u5cb8",'
    '"\\u573a\\u666f\\u6b63\\u6587":"\\u5979\\u7ad9\\u5728\\u6865\\u8fb9\\u770b\\u6c34\\u9762\\u53cd\\u5149\\u3002"}'
)
WORLD_SCENE_JSON_MISSING_FIELD = '{"\\u573a\\u666f\\u547d\\u9898":"\\u9ec4\\u660f\\u7684\\u6cb3\\u5cb8"}'
TEXT_RESULT = "\u4eca\u5929\u98ce\u6709\u70b9\u6696\u3002"
TASK_SECTION = "<\u4efb\u52a1\u533a>"
JSON_SECTION = "<\u8fd4\u56de\u683c\u5f0f>"
TEXT_SECTION = "<\u8f93\u51fa\u8981\u6c42>"
WORLD_JSON_NOTICE = "\u8bf7\u53ea\u8fd4\u56de\u7b26\u5408\u4e0b\u5217\u9aa8\u67b6\u7684\u5408\u6cd5 JSON\u3002"
SOCIAL_POST_TEXT_INSTRUCTION = "\u76f4\u63a5\u8f93\u51fa\u6700\u7ec8\u793e\u5a92\u6587\u6848\u6b63\u6587\u3002"
TEXT_NO_JSON = "\u4e0d\u8981\u8f93\u51fa JSON\u3002"


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

    def test_call_json_task_applies_stage_protocol_and_validates_contract(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            request_path = project_dir / "trace" / "request.json"
            response_path = project_dir / "trace" / "response.json"
            model_config = {"envName": "IGNORED", "model": "demo", "parseRetryAttempts": 1}

            with patch(
                "llm._call_model",
                return_value=(
                    model_config,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": WORLD_SCENE_JSON
                                }
                            }
                        ]
                    },
                ),
            ) as mocked_call:
                payload = call_json_task(
                    project_dir=project_dir,
                    model_config=model_config,
                    system_prompt="world prompt",
                    stage_id="creative.world_design",
                    output_contract=scene_draft_contract(),
                    user_payload={"foo": "bar"},
                    trace_request_path=request_path,
                    trace_response_path=response_path,
                )

            self.assertEqual(payload[SCENE_PREMISE_LABEL], "\u9ec4\u660f\u7684\u6cb3\u5cb8")
            self.assertEqual(payload[WORLD_SCENE_LABEL], "\u5979\u7ad9\u5728\u6865\u8fb9\u770b\u6c34\u9762\u53cd\u5149\u3002")
            system_prompt = mocked_call.call_args.kwargs["system_prompt"]
            self.assertIn(TASK_SECTION, system_prompt)
            self.assertIn("world prompt", system_prompt)
            self.assertIn(JSON_SECTION, system_prompt)
            self.assertIn(WORLD_JSON_NOTICE, system_prompt)
            self.assertIn(f'"{SCENE_PREMISE_LABEL}": ""', system_prompt)
            self.assertIn(f'"{WORLD_SCENE_LABEL}": ""', system_prompt)

    def test_call_json_task_rejects_payload_that_breaks_contract(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            request_path = project_dir / "trace" / "request.json"
            response_path = project_dir / "trace" / "response.json"
            model_config = {"envName": "IGNORED", "model": "demo", "parseRetryAttempts": 1}

            with patch(
                "llm._call_model",
                return_value=(
                    model_config,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": WORLD_SCENE_JSON_MISSING_FIELD
                                }
                            }
                        ]
                    },
                ),
            ):
                with self.assertRaises(RuntimeError) as context:
                    call_json_task(
                        project_dir=project_dir,
                        model_config=model_config,
                        system_prompt="world prompt",
                        stage_id="creative.world_design",
                        output_contract=scene_draft_contract(),
                        user_payload={"foo": "bar"},
                        trace_request_path=request_path,
                        trace_response_path=response_path,
                    )

            self.assertIn("missing required keys", str(context.exception))

    def test_call_text_task_applies_stage_protocol(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            request_path = project_dir / "trace" / "request.json"
            response_path = project_dir / "trace" / "response.json"
            model_config = {"envName": "IGNORED", "model": "demo"}

            with patch(
                "llm._call_model",
                return_value=(
                    model_config,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": f"```text\n{TEXT_RESULT}\n```"
                                }
                            }
                        ]
                    },
                ),
            ) as mocked_call:
                result = call_text_task(
                    project_dir=project_dir,
                    model_config=model_config,
                    system_prompt="social prompt",
                    stage_id="social_post.default",
                    user_payload=None,
                    trace_request_path=request_path,
                    trace_response_path=response_path,
                )

            self.assertEqual(result, TEXT_RESULT)
            system_prompt = mocked_call.call_args.kwargs["system_prompt"]
            self.assertIn(TASK_SECTION, system_prompt)
            self.assertIn("social prompt", system_prompt)
            self.assertIn(TEXT_SECTION, system_prompt)
            self.assertIn(SOCIAL_POST_TEXT_INSTRUCTION, system_prompt)
            self.assertIn(TEXT_NO_JSON, system_prompt)


if __name__ == "__main__":
    unittest.main()
