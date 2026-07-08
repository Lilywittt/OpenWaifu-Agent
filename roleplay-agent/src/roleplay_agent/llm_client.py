from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from .env import require_env_value
from .io_utils import write_json, write_text


def _thinking_enabled(profile: dict[str, Any]) -> bool:
    thinking = profile.get("thinking")
    return isinstance(thinking, dict) and str(thinking.get("type", "")).strip().lower() == "enabled"


def build_chat_completion_body(
    profile: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": profile["model"],
        "messages": messages,
        "max_tokens": int(profile.get("maxTokens", 1800) if max_tokens is None else max_tokens),
    }
    thinking = profile.get("thinking")
    if isinstance(thinking, dict):
        body["thinking"] = thinking
    if _thinking_enabled(profile):
        effort = str(profile.get("reasoningEffort", "")).strip()
        if effort:
            body["reasoning_effort"] = effort
        return body
    body["temperature"] = float(profile.get("temperature", 0.8) if temperature is None else temperature)
    if profile.get("topP") is not None:
        body["top_p"] = profile.get("topP")
    return body


def _request_once(*, url: str, api_key: str, body: dict[str, Any], timeout_ms: int) -> dict[str, Any]:
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
        with urlopen(request, timeout=max(timeout_ms, 1000) / 1000.0) as response:
            raw = response.read().decode("utf-8")
    except (URLError, OSError) as first_error:
        try:
            opener = build_opener(ProxyHandler({}))
            with opener.open(request, timeout=max(timeout_ms, 1000) / 1000.0) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as retry_http_error:
            body_text = retry_http_error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {retry_http_error.code}: {body_text}") from retry_http_error
        except (URLError, OSError):
            raise RuntimeError(f"LLM transport error: {first_error}") from first_error
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM response is not valid JSON: {raw[:500]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("LLM response must be a JSON object.")
    return payload


def _is_retryable_error(exc: Exception) -> bool:
    text = str(exc).casefold()
    return "transport" in text or "timed out" in text or "http 429" in text or "http 5" in text


def extract_reply_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices:
        raise RuntimeError(f"LLM response missing choices: {payload}")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, list):
        text = "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    else:
        text = str(content)
    text = text.strip()
    if not text:
        raise RuntimeError("LLM response content is empty.")
    return text


def call_chat_completion(
    *,
    project_dir: Path,
    profile: dict[str, Any],
    messages: list[dict[str, str]],
    trace_dir: Path | None,
) -> str:
    api_key = require_env_value(project_dir, str(profile["envName"]))
    body = build_chat_completion_body(profile, messages)
    url = str(profile["baseUrl"]).rstrip("/") + str(profile.get("chatCompletionsPath", "/chat/completions"))
    attempts = max(int(profile.get("retryAttempts", 1)), 1)
    delay_ms = max(int(profile.get("retryBaseDelayMs", 0)), 0)
    timeout_ms = int(profile.get("timeoutMs", 180000))
    last_error: Exception | None = None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    if trace_dir is not None:
        write_json(trace_dir / f"{stamp}.request.json", body)
    for attempt in range(1, attempts + 1):
        try:
            payload = _request_once(url=url, api_key=api_key, body=body, timeout_ms=timeout_ms)
            if trace_dir is not None:
                write_json(trace_dir / f"{stamp}.response.json", payload)
            return extract_reply_text(payload)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= attempts or not _is_retryable_error(exc):
                break
            time.sleep((delay_ms * attempt) / 1000.0)
    assert last_error is not None
    if trace_dir is not None:
        write_text(trace_dir / f"{stamp}.error.txt", f"{type(last_error).__name__}: {last_error}")
    raise last_error
