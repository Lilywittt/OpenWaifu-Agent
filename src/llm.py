from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from env import require_env_value
from io_utils import read_json


def extract_json_block(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    starts = [index for index in (text.find("{"), text.find("[")) if index != -1]
    start = min(starts, default=-1)
    if start == -1:
        raise RuntimeError("Model response did not contain JSON.")
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string = False
    escaping = False
    for index in range(start, len(text)):
        char = text[index]
        if escaping:
            escaping = False
            continue
        if char == "\\":
            escaping = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise RuntimeError("Model response JSON block was incomplete.")


def call_json_task(
    *,
    project_dir: Path,
    model_config_path: Path,
    system_prompt: str,
    user_payload: dict[str, Any],
    trace_request_path: Path,
    trace_response_path: Path,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Any:
    model_config = read_json(model_config_path)
    api_key = require_env_value(project_dir, model_config["envName"])

    body = {
        "model": model_config["model"],
        "temperature": model_config.get("temperature", 0.8) if temperature is None else temperature,
        "max_tokens": model_config.get("maxTokens", 1800) if max_tokens is None else max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
        ],
    }
    trace_request_path.parent.mkdir(parents=True, exist_ok=True)
    trace_request_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")

    url = model_config["baseUrl"].rstrip("/") + model_config["chatCompletionsPath"]
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=model_config.get("timeoutMs", 180000) / 1000) as response:
            raw_response = response.read().decode("utf-8")
    except HTTPError as error:
        raise RuntimeError(f"Creative model HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error
    except URLError as error:
        raise RuntimeError(f"Creative model transport error: {error}") from error

    trace_response_path.parent.mkdir(parents=True, exist_ok=True)
    trace_response_path.write_text(raw_response, encoding="utf-8")
    payload = json.loads(raw_response)
    content = payload["choices"][0]["message"]["content"]
    if isinstance(content, list):
        text = "\n".join(str(item.get("text", "")) for item in content)
    else:
        text = str(content)
    return json.loads(extract_json_block(text))
