from __future__ import annotations

import importlib
import json
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..io_utils import ensure_dir, read_json
from ..paths import resolve_project_path
from ..process_utils import is_process_alive


@dataclass(frozen=True)
class ImageBridgeTask:
    task_type: str
    user_openid: str
    source_message_id: str = ""
    reply_event_id: str = ""
    scene_text: str = ""


class OpenWaifuAgentBridge:
    def __init__(self, project_dir: Path, *, log: Callable[[str], None] | None = None):
        self.project_dir = project_dir
        self.config = self._load_config()
        self.agent_dir = resolve_project_path(project_dir, str(self.config.get("projectDir", "../openwaifu-agent")))
        self.agent_src_dir = self.agent_dir / "src"
        self.max_queue_size = max(int(self.config.get("maxQueueSize", 1)), 1)
        self._queue: queue.Queue[ImageBridgeTask] = queue.Queue(maxsize=self.max_queue_size)
        self._worker_started = False
        self._worker_lock = threading.Lock()
        self._log = log
        self._last_status = "idle"
        self._last_error = ""

    def _load_config(self) -> dict[str, Any]:
        payload = read_json(self.project_dir / "config" / "image_bridge.json")
        if not isinstance(payload, dict):
            raise RuntimeError("config/image_bridge.json must be a JSON object.")
        return payload

    @property
    def reject_when_legacy_service_running(self) -> bool:
        return bool(self.config.get("rejectWhenLegacyQqServiceRunning", True))

    def legacy_service_lock_path(self) -> Path:
        return self.agent_dir / "runtime" / "service_state" / "publish" / "qq_bot_generate_service" / "service.lock.json"

    def legacy_service_pid(self) -> int:
        path = self.legacy_service_lock_path()
        if not path.exists():
            return 0
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return 0
        try:
            return int(payload.get("pid", 0) or 0)
        except Exception:
            return 0

    def legacy_service_running(self) -> bool:
        pid = self.legacy_service_pid()
        return bool(pid and is_process_alive(pid))

    def preflight(self) -> dict[str, Any]:
        agent_exists = self.agent_dir.exists()
        src_exists = self.agent_src_dir.exists()
        legacy_pid = self.legacy_service_pid()
        legacy_running = self.legacy_service_running()
        ok = agent_exists and src_exists and not (self.reject_when_legacy_service_running and legacy_running)
        reason = ""
        if not agent_exists:
            reason = f"openwaifu-agent directory does not exist: {self.agent_dir}"
        elif not src_exists:
            reason = f"openwaifu-agent src directory does not exist: {self.agent_src_dir}"
        elif self.reject_when_legacy_service_running and legacy_running:
            reason = f"openwaifu-agent QQ service is running with pid {legacy_pid}"
        return {
            "ok": ok,
            "provider": self.config.get("provider", "openwaifu-agent"),
            "agentDir": str(self.agent_dir),
            "legacyServicePid": legacy_pid,
            "legacyServiceRunning": legacy_running,
            "reason": reason,
        }

    def assert_preflight_ok(self) -> None:
        result = self.preflight()
        if not result["ok"]:
            raise RuntimeError(str(result["reason"]))

    def stop_legacy_service(self, *, timeout_seconds: float = 30.0) -> bool:
        script = self.agent_dir / "run_qq_bot_service.py"
        if not script.exists():
            raise RuntimeError(f"openwaifu-agent QQ service script does not exist: {script}")
        result = subprocess.run(
            [sys.executable, str(script), "stop"],
            cwd=str(self.agent_dir),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        self._append_event(
            {
                "type": "legacy_service_stop_invoked",
                "returnCode": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
            }
        )
        deadline = time.time() + max(float(timeout_seconds), 1.0)
        while time.time() < deadline:
            if not self.legacy_service_running():
                return True
            time.sleep(0.5)
        return not self.legacy_service_running()

    def status_text(self) -> str:
        queue_size = self._queue.qsize()
        if self._last_error:
            return f"生图桥接：{self._last_status}，队列 {queue_size}，最近错误：{self._last_error}"
        return f"生图桥接：{self._last_status}，队列 {queue_size}"

    def enqueue_default_generation(self, *, user_openid: str, source_message_id: str = "", reply_event_id: str = "") -> bool:
        return self._enqueue(
            ImageBridgeTask(
                task_type="full_generation",
                user_openid=user_openid,
                source_message_id=source_message_id,
                reply_event_id=reply_event_id,
            )
        )

    def enqueue_scene_generation(
        self,
        *,
        user_openid: str,
        scene_text: str,
        source_message_id: str = "",
        reply_event_id: str = "",
    ) -> bool:
        return self._enqueue(
            ImageBridgeTask(
                task_type="scene_draft_to_image",
                user_openid=user_openid,
                source_message_id=source_message_id,
                reply_event_id=reply_event_id,
                scene_text=scene_text,
            )
        )

    def validate_scene_draft_text(self, scene_text: str) -> dict[str, Any]:
        self.assert_preflight_ok()
        return self._parse_scene_draft(scene_text)

    def _enqueue(self, task: ImageBridgeTask) -> bool:
        self.assert_preflight_ok()
        self._ensure_worker()
        try:
            self._queue.put_nowait(task)
        except queue.Full:
            return False
        self._last_status = "queued"
        self._append_event({"type": "image_task_queued", "taskType": task.task_type, "userOpenId": task.user_openid})
        return True

    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if self._worker_started:
                return
            thread = threading.Thread(target=self._worker_loop, daemon=True)
            thread.start()
            self._worker_started = True

    def _worker_loop(self) -> None:
        while True:
            task = self._queue.get()
            try:
                self._run_task(task)
            except Exception as exc:  # noqa: BLE001
                self._last_status = "error"
                self._last_error = str(exc)[:300]
                self._append_event(
                    {
                        "type": "image_task_failed",
                        "taskType": task.task_type,
                        "userOpenId": task.user_openid,
                        "error": str(exc),
                    }
                )
            finally:
                self._queue.task_done()

    def _prepare_imports(self) -> None:
        src = str(self.agent_src_dir)
        if src not in sys.path:
            sys.path.insert(0, src)

    def _run_task(self, task: ImageBridgeTask) -> None:
        self.assert_preflight_ok()
        self._prepare_imports()
        self._last_status = "running"
        self._last_error = ""
        self._append_event({"type": "image_task_started", "taskType": task.task_type, "userOpenId": task.user_openid})

        executor = importlib.import_module("publish.qq_bot_executor")
        runtime_layout = importlib.import_module("runtime_layout")
        workbench_store = importlib.import_module("workbench.store")
        stage_protocols = importlib.import_module("test_pipeline")

        bundle = executor.create_generation_bundle(
            self.agent_dir,
            task_type=task.task_type,
            user_openid=task.user_openid,
        )
        payload: dict[str, Any] = {
            "userOpenId": task.user_openid,
            "sourceMessageId": task.source_message_id,
            "replyEventId": task.reply_event_id,
            "taskType": task.task_type,
        }
        if task.task_type == "scene_draft_to_image":
            scene_draft = self._parse_scene_draft(task.scene_text)
            scene_draft_path = self._persist_scene_draft(task.user_openid, scene_draft)
            payload["sceneDraft"] = scene_draft
            payload["sceneDraftPath"] = str(scene_draft_path)

        def task_log(message: str) -> None:
            self._last_status = str(message or "").strip() or "running"
            if self._log is not None:
                self._log(f"[image-bridge] {message}")
            self._append_event(
                {
                    "type": "image_task_log",
                    "runId": str(bundle.run_id),
                    "message": str(message),
                }
            )

        result = executor.run_generation_task(
            project_dir=self.agent_dir,
            bundle=bundle,
            task=payload,
            log=task_log,
            should_abort=lambda: False,
        )
        summary = result["summary"]
        runtime_layout.update_latest(
            self.agent_dir,
            bundle,
            {
                "runId": bundle.run_id,
                "creativePackagePath": summary["creativePackagePath"],
                "socialPostPackagePath": summary["socialPostPackagePath"],
                "promptPackagePath": summary["promptPackagePath"],
                "executionPackagePath": summary["executionPackagePath"],
                "publishPackagePath": summary["publishPackagePath"],
                "summaryPath": str(bundle.output_dir / "run_summary.json"),
                "sceneDraftPremiseZh": summary.get("sceneDraftPremiseZh", ""),
            },
        )
        source_kind = (
            getattr(stage_protocols, "SOURCE_KIND_SCENE_DRAFT_TEXT")
            if task.task_type == "scene_draft_to_image"
            else getattr(stage_protocols, "SOURCE_KIND_LIVE_SAMPLING")
        )
        workbench_store.ensure_runtime_run_index_record(
            self.agent_dir,
            bundle.run_id,
            status="completed",
            request={
                "sourceKind": source_kind,
                "endStage": getattr(stage_protocols, "END_STAGE_IMAGE"),
                "label": "Roleplay Agent 系统指令生图",
                "ownerId": "private",
                "ownerDisplay": "QQ Roleplay",
            },
        )
        self._last_status = "idle"
        self._append_event(
            {
                "type": "image_task_completed",
                "runId": str(bundle.run_id),
                "taskType": task.task_type,
                "userOpenId": task.user_openid,
                "generatedImagePath": summary.get("generatedImagePath", ""),
            }
        )

    def _parse_scene_draft(self, scene_text: str) -> dict[str, Any]:
        self._prepare_imports()
        text = str(scene_text or "").strip()
        if not text:
            raise RuntimeError("scene draft is empty.")
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        scene_module = importlib.import_module("publish.qq_bot_scene_draft")
        return dict(scene_module.parse_scene_draft_message(text))

    def _persist_scene_draft(self, user_openid: str, scene_draft: dict[str, Any]) -> Path:
        self._prepare_imports()
        scene_module = importlib.import_module("publish.qq_bot_scene_draft")
        return Path(scene_module.persist_scene_draft_message(self.agent_dir, user_openid=user_openid, scene_draft=scene_draft))

    def _append_event(self, payload: dict[str, Any]) -> None:
        path = self.project_dir / "runtime" / "service_state" / "image_bridge" / "events.jsonl"
        ensure_dir(path.parent)
        event = {
            "recordedAt": datetime.now().isoformat(timespec="seconds"),
            **payload,
        }
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
