from __future__ import annotations

import ctypes
import json
import os
import uuid
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from io_utils import ensure_dir, normalize_spaces
from runtime_layout import runtime_root


OWNER_TYPE_LABELS = {
    "qq_bot_service": "QQ 私聊服务",
    "content_workbench": "内容测试工作台",
    "run_product": "完整产品脚本",
    "run_generate_product": "生成层脚本",
    "product_pipeline": "本地产品链路",
}


def shared_state_root(project_dir: Path) -> Path:
    return ensure_dir(runtime_root(project_dir) / "service_state" / "shared")


def generation_slot_path(project_dir: Path) -> Path:
    return shared_state_root(project_dir) / "generation_slot.json"


def owner_type_label(owner_type: str) -> str:
    normalized = normalize_spaces(owner_type)
    return OWNER_TYPE_LABELS.get(normalized, normalized or "其他本地任务")


def _is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        process_query_limited_information = 0x1000
        synchronize = 0x00100000
        still_active = 259
        access_mask = process_query_limited_information | synchronize
        try:
            kernel32 = ctypes.windll.kernel32
            open_process = kernel32.OpenProcess
            open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            open_process.restype = wintypes.HANDLE
            get_exit_code_process = kernel32.GetExitCodeProcess
            get_exit_code_process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            get_exit_code_process.restype = wintypes.BOOL
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [wintypes.HANDLE]
            close_handle.restype = wintypes.BOOL

            handle = open_process(access_mask, False, int(pid))
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if not get_exit_code_process(handle, ctypes.byref(exit_code)):
                    return False
                return int(exit_code.value) == still_active
            finally:
                close_handle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    except BaseException:
        return False
    return True


def describe_generation_slot_holder(holder: dict[str, Any] | None) -> str:
    if not isinstance(holder, dict):
        return "其他本地任务"
    owner_label = owner_type_label(str(holder.get("ownerType", "")))
    custom_label = normalize_spaces(str(holder.get("ownerLabel", "")))
    if custom_label and custom_label != owner_label:
        return f"{owner_label}（{custom_label}）"
    return owner_label


def build_generation_slot_busy_message(holder: dict[str, Any] | None) -> str:
    owner_text = describe_generation_slot_holder(holder)
    lines = [f"本机当前正被{owner_text}占用，暂时不能开始新的内容任务。"]
    if isinstance(holder, dict):
        run_id = normalize_spaces(str(holder.get("runId", "")))
        started_at = normalize_spaces(str(holder.get("startedAt", "")))
        if run_id:
            lines.append(f"当前 runId：{run_id}")
        if started_at:
            lines.append(f"占用开始时间：{started_at}")
    lines.append("请等待当前任务完成、失败返回或被中断后再试。")
    return "\n".join(lines)


def _normalize_holder_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "pid": int(payload.get("pid", 0) or 0),
        "token": normalize_spaces(str(payload.get("token", ""))),
        "ownerType": normalize_spaces(str(payload.get("ownerType", ""))),
        "ownerLabel": normalize_spaces(str(payload.get("ownerLabel", ""))),
        "runId": normalize_spaces(str(payload.get("runId", ""))),
        "startedAt": normalize_spaces(str(payload.get("startedAt", ""))),
        "metadata": payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {},
    }
    normalized["ownerTypeLabel"] = owner_type_label(normalized["ownerType"])
    normalized["holderText"] = describe_generation_slot_holder(normalized)
    normalized["busyMessage"] = build_generation_slot_busy_message(normalized)
    return normalized


def read_generation_slot(project_dir: Path, *, cleanup_stale: bool = True) -> dict[str, Any] | None:
    path = generation_slot_path(project_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        if cleanup_stale:
            try:
                path.unlink()
            except OSError:
                pass
        return None
    if not isinstance(payload, dict):
        if cleanup_stale:
            try:
                path.unlink()
            except OSError:
                pass
        return None
    normalized = _normalize_holder_payload(payload)
    if normalized["pid"] <= 0 or not _is_process_alive(normalized["pid"]):
        if cleanup_stale:
            try:
                path.unlink()
            except OSError:
                pass
        return None
    return normalized


class GenerationSlotBusyError(RuntimeError):
    def __init__(self, holder: dict[str, Any] | None):
        self.holder = _normalize_holder_payload(holder or {})
        self.user_summary = build_generation_slot_busy_message(self.holder).splitlines()[0]
        self.user_details = build_generation_slot_busy_message(self.holder).splitlines()[1:]
        super().__init__(build_generation_slot_busy_message(self.holder))


@dataclass(frozen=True)
class GenerationSlotLease:
    project_dir: Path
    token: str
    payload: dict[str, Any]

    def release(self) -> bool:
        path = generation_slot_path(self.project_dir)
        if not path.exists():
            return False
        try:
            current_payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            current_payload = {}
        if normalize_spaces(str(current_payload.get("token", ""))) != self.token:
            return False
        try:
            path.unlink()
        except OSError:
            return False
        return True


def acquire_generation_slot(
    project_dir: Path,
    *,
    owner_type: str,
    owner_label: str = "",
    run_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> GenerationSlotLease:
    project_dir = Path(project_dir).resolve()
    path = generation_slot_path(project_dir)
    metadata_payload = dict(metadata or {})
    for _ in range(3):
        holder = read_generation_slot(project_dir, cleanup_stale=True)
        if holder is not None:
            raise GenerationSlotBusyError(holder)
        token = uuid.uuid4().hex
        payload = {
            "pid": os.getpid(),
            "token": token,
            "ownerType": normalize_spaces(owner_type),
            "ownerLabel": normalize_spaces(owner_label),
            "runId": normalize_spaces(run_id),
            "startedAt": datetime.now().isoformat(timespec="seconds"),
            "metadata": metadata_payload,
        }
        ensure_dir(path.parent)
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except FileExistsError:
            continue
        return GenerationSlotLease(project_dir=project_dir, token=token, payload=_normalize_holder_payload(payload))
    raise GenerationSlotBusyError(read_generation_slot(project_dir, cleanup_stale=True))


@contextmanager
def occupy_generation_slot(
    project_dir: Path,
    *,
    owner_type: str,
    owner_label: str = "",
    run_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> Iterator[GenerationSlotLease]:
    lease = acquire_generation_slot(
        project_dir,
        owner_type=owner_type,
        owner_label=owner_label,
        run_id=run_id,
        metadata=metadata,
    )
    try:
        yield lease
    finally:
        lease.release()
