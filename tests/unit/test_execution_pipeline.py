from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from execution.pipeline import run_execution_pipeline
from io_utils import read_json
from runtime_layout import create_run_bundle


class ExecutionPipelineTests(unittest.TestCase):
    def test_execution_pipeline_raises_clear_error_when_active_profile_config_is_missing(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            bundle = create_run_bundle(project_dir, "default", "execution-missing-active-profile")

            with self.assertRaisesRegex(RuntimeError, "execution active profile config does not exist"):
                run_execution_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default", "nowLocal": "2026-04-11T18:00:00"},
                    {"positivePrompt": "positive text", "negativePrompt": "negative text"},
                )

    def test_execution_pipeline_builds_workflow_and_materializes_image(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            checkpoint_path = project_dir / "shared" / "animagine-xl-4.0-opt.safetensors"
            checkpoint_path.parent.mkdir(parents=True)
            checkpoint_path.write_bytes(b"fake-checkpoint")

            workflow_dir = project_dir / "config" / "workflows" / "comfyui"
            workflow_dir.mkdir(parents=True)
            (workflow_dir / "animagine_xl_basic.workflow.json").write_text(
                """
{
  "3": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
  "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["3", 1]}},
  "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["3", 1]}},
  "10": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
  "13": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20, "cfg": 5.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["3", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["10", 0]}},
  "8": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 2]}},
  "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "demo", "images": ["8", 0]}}
}
                """.strip(),
                encoding="utf-8",
            )

            execution_dir = project_dir / "config" / "execution"
            execution_dir.mkdir(parents=True)
            (execution_dir / "active_profile.json").write_text(
                """
{
  "profilePath": "config/execution/comfyui_local_animagine_xl.json"
}
                """.strip(),
                encoding="utf-8",
            )
            (execution_dir / "comfyui_local_animagine_xl.json").write_text(
                f"""
{{
  "version": "1.0.0",
  "profileId": "test_profile",
  "templatePath": "../workflows/comfyui/animagine_xl_basic.workflow.json",
  "endpointEnvName": "COMFYUI_ENDPOINT",
  "checkpointPath": "{checkpoint_path.as_posix()}",
  "checkpointName": "animagine-xl-4.0-opt.safetensors",
  "request": {{
    "healthPath": "/system_stats",
    "submitPath": "/prompt",
    "historyPath": "/history/{{prompt_id}}",
    "viewPath": "/view",
    "submitTimeoutMs": 120000,
    "pollIntervalMs": 5000,
    "pollTimeoutMs": 900000,
    "downloadTimeoutMs": 120000,
    "startTimeoutMs": 180000
  }},
  "nodes": {{
    "checkpoint": {{"id": "3", "input": "ckpt_name"}},
    "positivePrompt": {{"id": "6", "input": "text"}},
    "negativePrompt": {{"id": "7", "input": "text"}},
    "latentImage": {{"id": "10", "widthInput": "width", "heightInput": "height", "batchInput": "batch_size"}},
    "sampler": {{"id": "13", "seedInput": "seed", "stepsInput": "steps", "cfgInput": "cfg", "samplerInput": "sampler_name", "schedulerInput": "scheduler", "denoiseInput": "denoise"}},
    "saveImage": {{"id": "9", "input": "filename_prefix"}},
    "output": {{"preferredNodeIds": ["9"]}}
  }},
  "defaults": {{
    "aspectRatio": "4:5",
    "steps": 28,
    "cfg": 5.6,
    "samplerName": "dpmpp_2m",
    "scheduler": "karras",
    "denoise": 1.0,
    "batchSize": 1,
    "filenamePrefix": "ig_roleplay_v3_animagine"
  }},
  "sizeByAspectRatio": {{
    "4:5": {{"width": 1024, "height": 1280}}
  }},
  "negativePromptFallback": "fallback negative"
}}
                """.strip(),
                encoding="utf-8",
            )

            bundle = create_run_bundle(project_dir, "default", "execution-pipeline")
            prompt_package = {
                "positivePrompt": "positive text",
                "negativePrompt": "negative text",
            }

            def _fake_download_image(endpoint, view_path, image_payload, destination_path, timeout_ms):
                destination_path.write_bytes(b"fake-png")

            with patch("execution.pipeline.ensure_comfyui_ready"), patch(
                "execution.pipeline.submit_workflow",
                return_value={"prompt_id": "prompt-123"},
            ), patch(
                "execution.pipeline.wait_for_prompt_completion",
                return_value={"outputs": {"9": {"images": [{"filename": "server.png", "subfolder": "", "type": "output"}]}}},
            ), patch(
                "execution.pipeline.download_image",
                side_effect=_fake_download_image,
            ):
                execution_package = run_execution_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default", "nowLocal": "2026-04-07T12:00:00"},
                    prompt_package,
                )

            execution_input = read_json(bundle.execution_dir / "00_execution_input.json")
            workflow_request = read_json(bundle.execution_dir / "01_workflow_request.json")
            execution_snapshot = read_json(bundle.execution_dir / "04_execution_package.json")

            self.assertEqual(execution_input["checkpointName"], "animagine-xl-4.0-opt.safetensors")
            self.assertEqual(execution_input["positivePrompt"], "positive text")
            self.assertEqual(execution_input["negativePrompt"], "negative text")
            self.assertEqual(workflow_request["prompt"]["3"]["inputs"]["ckpt_name"], "animagine-xl-4.0-opt.safetensors")
            self.assertEqual(workflow_request["prompt"]["6"]["inputs"]["text"], "positive text")
            self.assertEqual(workflow_request["prompt"]["7"]["inputs"]["text"], "negative text")
            self.assertEqual(workflow_request["prompt"]["10"]["inputs"]["width"], 1024)
            self.assertEqual(workflow_request["prompt"]["10"]["inputs"]["height"], 1280)
            self.assertTrue(Path(execution_snapshot["imagePath"]).exists())
            self.assertEqual(execution_package["promptId"], "prompt-123")

    def test_execution_pipeline_allows_checkpoint_env_override(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            overridden_checkpoint_path = project_dir / "comfyui" / "models" / "checkpoints" / "custom-model.safetensors"
            overridden_checkpoint_path.parent.mkdir(parents=True)
            overridden_checkpoint_path.write_bytes(b"fake-checkpoint")
            (project_dir / ".env").write_text(
                "\n".join(
                    [
                        f"COMFYUI_CHECKPOINT_PATH={overridden_checkpoint_path.as_posix()}",
                        "COMFYUI_CHECKPOINT_NAME=custom-model.safetensors",
                    ]
                ),
                encoding="utf-8",
            )

            workflow_dir = project_dir / "config" / "workflows" / "comfyui"
            workflow_dir.mkdir(parents=True)
            (workflow_dir / "animagine_xl_basic.workflow.json").write_text(
                """
{
  "3": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
  "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["3", 1]}},
  "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["3", 1]}},
  "10": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
  "13": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20, "cfg": 5.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["3", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["10", 0]}},
  "8": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 2]}},
  "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "demo", "images": ["8", 0]}}
}
                """.strip(),
                encoding="utf-8",
            )

            execution_dir = project_dir / "config" / "execution"
            execution_dir.mkdir(parents=True)
            (execution_dir / "active_profile.json").write_text(
                """
{
  "profilePath": "config/execution/comfyui_local_animagine_xl.json"
}
                """.strip(),
                encoding="utf-8",
            )
            (execution_dir / "comfyui_local_animagine_xl.json").write_text(
                """
{
  "version": "1.0.0",
  "profileId": "test_profile",
  "templatePath": "../workflows/comfyui/animagine_xl_basic.workflow.json",
  "endpointEnvName": "COMFYUI_ENDPOINT",
  "checkpointPathEnvName": "COMFYUI_CHECKPOINT_PATH",
  "checkpointNameEnvName": "COMFYUI_CHECKPOINT_NAME",
  "checkpointPath": "./missing/default.safetensors",
  "checkpointName": "default-model.safetensors",
  "request": {
    "healthPath": "/system_stats",
    "submitPath": "/prompt",
    "historyPath": "/history/{prompt_id}",
    "viewPath": "/view",
    "submitTimeoutMs": 120000,
    "pollIntervalMs": 5000,
    "pollTimeoutMs": 900000,
    "downloadTimeoutMs": 120000,
    "startTimeoutMs": 180000
  },
  "nodes": {
    "checkpoint": {"id": "3", "input": "ckpt_name"},
    "positivePrompt": {"id": "6", "input": "text"},
    "negativePrompt": {"id": "7", "input": "text"},
    "latentImage": {"id": "10", "widthInput": "width", "heightInput": "height", "batchInput": "batch_size"},
    "sampler": {"id": "13", "seedInput": "seed", "stepsInput": "steps", "cfgInput": "cfg", "samplerInput": "sampler_name", "schedulerInput": "scheduler", "denoiseInput": "denoise"},
    "saveImage": {"id": "9", "input": "filename_prefix"},
    "output": {"preferredNodeIds": ["9"]}
  },
  "defaults": {
    "aspectRatio": "4:5",
    "steps": 28,
    "cfg": 5.6,
    "samplerName": "dpmpp_2m",
    "scheduler": "karras",
    "denoise": 1.0,
    "batchSize": 1,
    "filenamePrefix": "ig_roleplay_v3_animagine"
  },
  "sizeByAspectRatio": {
    "4:5": {"width": 1024, "height": 1280}
  },
  "negativePromptFallback": "fallback negative"
}
                """.strip(),
                encoding="utf-8",
            )

            bundle = create_run_bundle(project_dir, "default", "execution-pipeline-env-override")
            prompt_package = {
                "positivePrompt": "positive text",
                "negativePrompt": "negative text",
            }

            def _fake_download_image(endpoint, view_path, image_payload, destination_path, timeout_ms):
                destination_path.write_bytes(b"fake-png")

            with patch("execution.pipeline.ensure_comfyui_ready"), patch(
                "execution.pipeline.submit_workflow",
                return_value={"prompt_id": "prompt-override"},
            ), patch(
                "execution.pipeline.wait_for_prompt_completion",
                return_value={"outputs": {"9": {"images": [{"filename": "server.png", "subfolder": "", "type": "output"}]}}},
            ), patch(
                "execution.pipeline.download_image",
                side_effect=_fake_download_image,
            ):
                execution_package = run_execution_pipeline(
                    project_dir,
                    bundle,
                    {"runMode": "default", "nowLocal": "2026-04-09T18:00:00"},
                    prompt_package,
                )

            execution_input = read_json(bundle.execution_dir / "00_execution_input.json")
            workflow_request = read_json(bundle.execution_dir / "01_workflow_request.json")
            self.assertEqual(execution_input["checkpointName"], "custom-model.safetensors")
            self.assertEqual(execution_input["checkpointPath"], str(overridden_checkpoint_path))
            self.assertEqual(workflow_request["prompt"]["3"]["inputs"]["ckpt_name"], "custom-model.safetensors")
            self.assertEqual(execution_package["checkpointName"], "custom-model.safetensors")


if __name__ == "__main__":
    unittest.main()
