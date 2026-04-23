from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from env import get_env_value
from io_utils import read_json
from path_policy import resolve_project_path, resolve_workspace_path


ACTIVE_PROFILE_CONFIG_PATH = Path("config") / "execution" / "active_profile.json"


def resolve_active_execution_profile_path(project_dir: Path) -> Path:
    config_path = project_dir / ACTIVE_PROFILE_CONFIG_PATH
    if not config_path.is_file():
        raise RuntimeError(f"execution active profile config does not exist: {config_path}")

    config = read_json(config_path)
    raw_path = str(config.get("profilePath", "")).strip()
    if not raw_path:
        raise RuntimeError(f"{ACTIVE_PROFILE_CONFIG_PATH.as_posix()} is missing profilePath.")

    profile_path = Path(raw_path)
    if not profile_path.is_absolute():
        profile_path = (project_dir / profile_path).resolve()

    if not profile_path.is_file():
        raise RuntimeError(f"execution profile does not exist: {profile_path}")
    return profile_path


def load_execution_profile(project_dir: Path, profile_path: Path) -> tuple[dict[str, Any], dict[str, Any], Path]:
    resolved_profile_path = profile_path if profile_path.is_absolute() else (project_dir / profile_path).resolve()
    profile = read_json(resolved_profile_path)
    template_path = (resolved_profile_path.parent / profile["templatePath"]).resolve()
    workflow_template = read_json(template_path)
    return profile, workflow_template, template_path


def resolve_checkpoint_path(project_dir: Path, profile: dict[str, Any]) -> Path:
    raw_path = str(profile.get("checkpointPath", "")).strip()
    env_name = str(profile.get("checkpointPathEnvName", "")).strip()
    if env_name:
        raw_path = get_env_value(project_dir, env_name, raw_path).strip()
    if not raw_path:
        return Path()
    checkpoint_path = Path(raw_path)
    if checkpoint_path.is_absolute():
        return checkpoint_path
    if checkpoint_path.parts and checkpoint_path.parts[0] == ".local":
        return resolve_workspace_path(project_dir, raw_path)
    return resolve_project_path(project_dir, raw_path)


def resolve_checkpoint_name(project_dir: Path, profile: dict[str, Any]) -> str:
    raw_name = str(profile.get("checkpointName", "")).strip()
    env_name = str(profile.get("checkpointNameEnvName", "")).strip()
    if env_name:
        raw_name = get_env_value(project_dir, env_name, raw_name).strip()
    return raw_name


def compute_prompt_seed(positive_prompt: str, negative_prompt: str, *, seed_salt: str = "") -> int:
    material = f"{positive_prompt}\n--\n{negative_prompt}\n--\n{seed_salt}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    return int(digest[:8], 16)


def select_image_size(profile: dict[str, Any]) -> tuple[str, int, int]:
    defaults = profile["defaults"]
    aspect_ratio = str(defaults["aspectRatio"])
    size = profile["sizeByAspectRatio"][aspect_ratio]
    return aspect_ratio, int(size["width"]), int(size["height"])


def build_execution_input(profile: dict[str, Any], prompt_package: dict[str, Any]) -> dict[str, Any]:
    aspect_ratio, width, height = select_image_size(profile)
    positive_prompt = str(prompt_package.get("positivePrompt", "")).strip()
    negative_prompt = str(prompt_package.get("negativePrompt", "")).strip()
    raw_seed = prompt_package.get("seed")
    seed_salt = str(prompt_package.get("seedSalt", "")).strip()
    try:
        seed = int(raw_seed)
    except (TypeError, ValueError):
        seed = compute_prompt_seed(positive_prompt, negative_prompt, seed_salt=seed_salt)
    defaults = profile["defaults"]
    return {
        "checkpointName": str(profile["checkpointName"]),
        "positivePrompt": positive_prompt,
        "negativePrompt": negative_prompt or str(profile.get("negativePromptFallback", "")).strip(),
        "aspectRatio": aspect_ratio,
        "width": width,
        "height": height,
        "seed": seed,
        "steps": int(defaults["steps"]),
        "cfg": float(defaults["cfg"]),
        "samplerName": str(defaults["samplerName"]),
        "scheduler": str(defaults["scheduler"]),
        "denoise": float(defaults["denoise"]),
        "batchSize": int(defaults["batchSize"]),
        "filenamePrefix": str(defaults["filenamePrefix"]),
        "seedSalt": seed_salt,
    }


def _set_node_input(workflow: dict[str, Any], node_id: str, input_name: str, value: Any) -> None:
    workflow[str(node_id)]["inputs"][input_name] = value


def build_workflow_request(
    profile: dict[str, Any],
    workflow_template: dict[str, Any],
    execution_input: dict[str, Any],
    *,
    run_id: str,
) -> dict[str, Any]:
    workflow = copy.deepcopy(workflow_template)
    nodes = profile["nodes"]

    _set_node_input(workflow, nodes["checkpoint"]["id"], nodes["checkpoint"]["input"], execution_input["checkpointName"])
    _set_node_input(workflow, nodes["positivePrompt"]["id"], nodes["positivePrompt"]["input"], execution_input["positivePrompt"])
    _set_node_input(workflow, nodes["negativePrompt"]["id"], nodes["negativePrompt"]["input"], execution_input["negativePrompt"])
    _set_node_input(workflow, nodes["latentImage"]["id"], nodes["latentImage"]["widthInput"], execution_input["width"])
    _set_node_input(workflow, nodes["latentImage"]["id"], nodes["latentImage"]["heightInput"], execution_input["height"])
    _set_node_input(workflow, nodes["latentImage"]["id"], nodes["latentImage"]["batchInput"], execution_input["batchSize"])
    _set_node_input(workflow, nodes["sampler"]["id"], nodes["sampler"]["seedInput"], execution_input["seed"])
    _set_node_input(workflow, nodes["sampler"]["id"], nodes["sampler"]["stepsInput"], execution_input["steps"])
    _set_node_input(workflow, nodes["sampler"]["id"], nodes["sampler"]["cfgInput"], execution_input["cfg"])
    _set_node_input(workflow, nodes["sampler"]["id"], nodes["sampler"]["samplerInput"], execution_input["samplerName"])
    _set_node_input(workflow, nodes["sampler"]["id"], nodes["sampler"]["schedulerInput"], execution_input["scheduler"])
    _set_node_input(workflow, nodes["sampler"]["id"], nodes["sampler"]["denoiseInput"], execution_input["denoise"])

    filename_prefix = f"{execution_input['filenamePrefix']}_{run_id}"
    _set_node_input(workflow, nodes["saveImage"]["id"], nodes["saveImage"]["input"], filename_prefix)
    return workflow
