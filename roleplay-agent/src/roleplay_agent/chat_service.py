from __future__ import annotations

import threading
from pathlib import Path

from .config import load_app_config, resolve_active_model_profile
from .conversation_store import append_message, clear_conversation, load_recent_messages
from .llm_client import call_chat_completion
from .memory import memory_summary_text
from .prompting import build_system_prompt, load_post_history_instructions


class CharacterChatService:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _user_lock(self, user_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(user_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[user_id] = lock
            return lock

    def reset_conversation(self, user_id: str) -> bool:
        with self._user_lock(user_id):
            return clear_conversation(self.project_dir, user_id)

    def generate_reply(self, *, user_id: str, user_text: str) -> str:
        app_config = load_app_config(self.project_dir)
        max_user_chars = int(app_config.get("maxUserMessageChars", 2000))
        max_assistant_chars = int(app_config.get("maxAssistantMessageChars", 2200))
        text = str(user_text or "").strip()
        if not text:
            return "我在，刚刚这条消息是空的。"
        if len(text) > max_user_chars:
            text = text[:max_user_chars]
        with self._user_lock(user_id):
            profile = resolve_active_model_profile(self.project_dir)
            memory_summary = memory_summary_text(self.project_dir, user_id)
            history = load_recent_messages(
                self.project_dir,
                user_id,
                limit=int(app_config.get("maxHistoryMessages", 24)),
            )
            context_text = "\n".join([*(item["content"] for item in history), text])
            prompt_bundle = build_system_prompt(
                self.project_dir,
                user_id=user_id,
                memory_summary=memory_summary,
                context_text=context_text,
            )
            messages = [{"role": "system", "content": prompt_bundle.system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": text})
            post_history = load_post_history_instructions(self.project_dir)
            if post_history:
                messages.append({"role": "system", "content": post_history})
            trace_dir = None
            if bool(app_config.get("traceRequests", True)):
                trace_dir = self.project_dir / "runtime" / "llm_traces" / user_id
            reply = call_chat_completion(
                project_dir=self.project_dir,
                profile=profile,
                messages=messages,
                trace_dir=trace_dir,
            ).strip()
            if len(reply) > max_assistant_chars:
                reply = reply[:max_assistant_chars].rstrip() + "..."
            append_message(self.project_dir, user_id, role="user", content=text)
            append_message(self.project_dir, user_id, role="assistant", content=reply)
            return reply
