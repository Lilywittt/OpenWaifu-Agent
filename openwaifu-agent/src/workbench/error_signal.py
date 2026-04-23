from __future__ import annotations

from typing import Any

from io_utils import normalize_spaces


def build_workbench_error_signal(raw_error: Any) -> dict[str, str]:
    raw = normalize_spaces(str(raw_error or ""))
    if not raw:
        return {}

    lowered = raw.casefold()
    if "insufficient balance" in lowered or ("402" in lowered and "invalid_request_error" in lowered):
        return {
            "kind": "api_balance_required",
            "title": "创意模型余额不足",
            "summary": "上游模型接口已拒绝这次请求。",
            "action": "先充值当前模型账户，或把 creative 模型切到仍可用的配置。",
            "raw": raw,
        }

    return {
        "kind": "generic",
        "title": "任务执行失败",
        "summary": raw,
        "action": "",
        "raw": raw,
    }
