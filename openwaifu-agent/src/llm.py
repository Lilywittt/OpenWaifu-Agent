from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from env import require_env_value


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


def _build_body(
    *,
    model_config: dict[str, Any],
    system_prompt: str,
    user_payload: dict[str, Any] | None,
    temperature: float | None,
    top_p: float | None,
    top_k: int | None,
    max_tokens: int | None,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if user_payload is not None:
        messages.append({"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)})
    body = {
        "model": model_config["model"],
        "temperature": model_config.get("temperature", 0.8) if temperature is None else temperature,
        "max_tokens": model_config.get("maxTokens", 1800) if max_tokens is None else max_tokens,
        "messages": messages,
    }
    effective_top_p = model_config.get("topP") if top_p is None else top_p
    effective_top_k = model_config.get("topK") if top_k is None else top_k
    if effective_top_p is not None:
        body["top_p"] = effective_top_p
    if effective_top_k is not None:
        body["top_k"] = effective_top_k
    return body


def _extract_response_text(payload: dict[str, Any]) -> str:
    content = payload["choices"][0]["message"]["content"]
    if isinstance(content, list):
        text = "\n".join(str(item.get("text", "")) for item in content)
    else:
        text = str(content)
    return text


def _strip_text_fence(raw: str) -> str:
    text = str(raw or "").strip().replace("\r\n", "\n")
    fenced = re.fullmatch(r"```(?:[A-Za-z0-9_-]+)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text


def _attempt_path(path: Path, attempt: int) -> Path:
    if attempt <= 1:
        return path
    return path.with_name(f"{path.stem}.attempt{attempt}{path.suffix}")


def _repair_trace_path(path: Path, parse_attempt: int) -> Path:
    base = _attempt_path(path, parse_attempt)
    return base.with_name(f"{base.stem}.repair{base.suffix}")


def _parse_error_trace_path(path: Path, parse_attempt: int) -> Path:
    base = _attempt_path(path, parse_attempt)
    return base.with_name(f"{base.stem}.parse_error.txt")


def _write_parse_error_trace(path: Path, *, raw_text: str, error: Exception) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = f"{type(error).__name__}: {error}\n\n--- RAW RESPONSE TEXT ---\n{raw_text}"
    path.write_text(payload, encoding="utf-8")


def _repair_json_text_via_model(
    *,
    project_dir: Path,
    model_config: dict[str, Any],
    broken_text: str,
    trace_request_path: Path,
    trace_response_path: Path,
) -> Any:
    repair_prompt = (
        "你是 JSON 修复器。输入是一段本应为 JSON 的文本，但语法可能损坏。"
        "在不改变原意的前提下做最小修改，把它修成合法 JSON。"
        "只返回合法 JSON，不要解释，不要补充额外字段。"
    )
    _, payload = _call_model(
        project_dir=project_dir,
        model_config=model_config,
        system_prompt=repair_prompt,
        user_payload={"brokenJson": broken_text},
        trace_request_path=trace_request_path,
        trace_response_path=trace_response_path,
        temperature=0.0,
        max_tokens=model_config.get("maxTokens", 1800),
    )
    return json.loads(extract_json_block(_extract_response_text(payload)))


def _call_model_once(
    *,
    model_config: dict[str, Any],
    api_key: str,
    system_prompt: str,
    user_payload: dict[str, Any] | None,
    trace_request_path: Path,
    trace_response_path: Path,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_tokens: int | None = None,
) -> Any:
    body = _build_body(
        model_config=model_config,
        system_prompt=system_prompt,
        user_payload=user_payload,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_tokens=max_tokens,
    )
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
    except (URLError, OSError) as error:
        try:
            opener = build_opener(ProxyHandler({}))
            with opener.open(request, timeout=model_config.get("timeoutMs", 180000) / 1000) as response:
                raw_response = response.read().decode("utf-8")
        except HTTPError as retry_error:
            raise RuntimeError(
                f"Creative model HTTP {retry_error.code}: {retry_error.read().decode('utf-8', errors='replace')}"
            ) from retry_error
        except (URLError, OSError):
            raise RuntimeError(f"Creative model transport error: {error}") from error

    trace_response_path.parent.mkdir(parents=True, exist_ok=True)
    trace_response_path.write_text(raw_response, encoding="utf-8")
    return json.loads(raw_response)


def _call_model(
    *,
    project_dir: Path,
    model_config: dict[str, Any],
    system_prompt: str,
    user_payload: dict[str, Any] | None,
    trace_request_path: Path,
    trace_response_path: Path,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_tokens: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = require_env_value(project_dir, model_config["envName"])
    retry_attempts = max(int(model_config.get("retryAttempts", 1)), 1)
    retry_base_delay_ms = max(int(model_config.get("retryBaseDelayMs", 0)), 0)
    last_error: Exception | None = None
    for attempt in range(1, retry_attempts + 1):
        try:
            payload = _call_model_once(
                model_config=model_config,
                api_key=api_key,
                system_prompt=system_prompt,
                user_payload=user_payload,
                trace_request_path=_attempt_path(trace_request_path, attempt),
                trace_response_path=_attempt_path(trace_response_path, attempt),
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                max_tokens=max_tokens,
            )
            return model_config, payload
        except Exception as error:
            last_error = error
            if attempt >= retry_attempts:
                break
            time.sleep((retry_base_delay_ms * attempt) / 1000)
    assert last_error is not None
    raise last_error


def call_json_task(
    *,
    project_dir: Path,
    model_config: dict[str, Any],
    system_prompt: str,
    user_payload: dict[str, Any] | None,
    trace_request_path: Path,
    trace_response_path: Path,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_tokens: int | None = None,
) -> Any:
    parse_retry_attempts = max(int(model_config.get("parseRetryAttempts", 1)), 1)
    parse_retry_delay_ms = max(int(model_config.get("parseRetryDelayMs", 0)), 0)
    last_error: Exception | None = None
    for parse_attempt in range(1, parse_retry_attempts + 1):
        try:
            _, payload = _call_model(
                project_dir=project_dir,
                model_config=model_config,
                system_prompt=system_prompt,
                user_payload=user_payload,
                trace_request_path=_attempt_path(trace_request_path, parse_attempt),
                trace_response_path=_attempt_path(trace_response_path, parse_attempt),
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                max_tokens=max_tokens,
            )
            raw_text = _extract_response_text(payload)
            try:
                return json.loads(extract_json_block(raw_text))
            except Exception as parse_error:
                _write_parse_error_trace(
                    _parse_error_trace_path(trace_response_path, parse_attempt),
                    raw_text=raw_text,
                    error=parse_error,
                )
                return _repair_json_text_via_model(
                    project_dir=project_dir,
                    model_config=model_config,
                    broken_text=raw_text,
                    trace_request_path=_repair_trace_path(trace_request_path, parse_attempt),
                    trace_response_path=_repair_trace_path(trace_response_path, parse_attempt),
                )
        except Exception as error:
            last_error = error
            if parse_attempt >= parse_retry_attempts:
                break
            time.sleep((parse_retry_delay_ms * parse_attempt) / 1000)
    assert last_error is not None
    raise last_error


def call_text_task(
    *,
    project_dir: Path,
    model_config: dict[str, Any],
    system_prompt: str,
    user_payload: dict[str, Any] | None,
    trace_request_path: Path,
    trace_response_path: Path,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    max_tokens: int | None = None,
) -> str:
    _, payload = _call_model(
        project_dir=project_dir,
        model_config=model_config,
        system_prompt=system_prompt,
        user_payload=user_payload,
        trace_request_path=trace_request_path,
        trace_response_path=trace_response_path,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        max_tokens=max_tokens,
    )
    return _strip_text_fence(_extract_response_text(payload))
