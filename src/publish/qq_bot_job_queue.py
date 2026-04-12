from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from io_utils import ensure_dir

from .state import publish_state_root


DEFAULT_MAX_PENDING_JOBS = 200


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def job_state_root(project_dir: Path) -> Path:
    return ensure_dir(publish_state_root(project_dir) / "qq_bot_jobs")


def job_db_path(project_dir: Path) -> Path:
    return job_state_root(project_dir) / "jobs.sqlite"


@contextmanager
def _connect(project_dir: Path) -> sqlite3.Connection:
    path = job_db_path(project_dir)
    ensure_dir(path.parent)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_openid TEXT NOT NULL,
            job_kind TEXT NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            source_message_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            run_id TEXT,
            error TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at, id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_openid, status)")
    conn.commit()


class QQBotJobQueue:
    def __init__(self, project_dir: Path, *, max_pending: int = DEFAULT_MAX_PENDING_JOBS) -> None:
        self.project_dir = Path(project_dir)
        self.max_pending = int(max_pending)
        with _connect(self.project_dir) as conn:
            _init_schema(conn)

    def _queue_size(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COUNT(*) AS count FROM jobs WHERE status = 'pending'").fetchone()
        return int(row["count"] if row else 0)

    def _pending_position(self, conn: sqlite3.Connection, *, created_at: str, job_id: int) -> int:
        row = conn.execute(
            """
            SELECT COUNT(*) AS position
            FROM jobs
            WHERE status = 'pending'
              AND (created_at < ? OR (created_at = ? AND id <= ?))
            """,
            (created_at, created_at, int(job_id)),
        ).fetchone()
        return int(row["position"] if row else 0)

    def _user_inflight_row(self, conn: sqlite3.Connection, user_openid: str) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE user_openid = ?
              AND status IN ('pending', 'running')
            ORDER BY CASE status WHEN 'running' THEN 0 ELSE 1 END, created_at, id
            LIMIT 1
            """,
            (user_openid,),
        ).fetchone()

    def pending_count(self) -> int:
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            return self._queue_size(conn)

    def reset_abandoned_running(self) -> int:
        now = _now()
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            cursor = conn.execute(
                "UPDATE jobs SET status='pending', updated_at=?, error=? WHERE status='running'",
                (now, "service restart"),
            )
            conn.commit()
            return int(cursor.rowcount)

    def enforce_single_inflight(self, *, reason: str = "normalized to single-flight policy") -> int:
        now = _now()
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT id, user_openid, status
                FROM jobs
                WHERE status IN ('pending', 'running')
                ORDER BY user_openid, CASE status WHEN 'running' THEN 0 ELSE 1 END, created_at, id
                """
            ).fetchall()
            kept_users: set[str] = set()
            duplicate_ids: list[int] = []
            for row in rows:
                user_openid = str(row["user_openid"] or "").strip()
                if not user_openid or user_openid in kept_users:
                    duplicate_ids.append(int(row["id"]))
                    continue
                kept_users.add(user_openid)
            if duplicate_ids:
                conn.executemany(
                    "UPDATE jobs SET status='canceled', finished_at=?, updated_at=?, error=? WHERE id=?",
                    [(now, now, str(reason or ""), int(job_id)) for job_id in duplicate_ids],
                )
            conn.commit()
            return len(duplicate_ids)

    def enqueue(
        self,
        *,
        user_openid: str,
        job_kind: str,
        payload: dict[str, Any],
        mode: str,
        source_message_id: str = "",
    ) -> dict[str, Any]:
        user_openid = str(user_openid or "").strip()
        if not user_openid:
            raise RuntimeError("missing user_openid")
        now = _now()
        payload_json = json.dumps(payload, ensure_ascii=False)
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            inflight_row = self._user_inflight_row(conn, user_openid)
            if inflight_row is not None:
                inflight_status = str(inflight_row["status"] or "").strip()
                queue_size = self._queue_size(conn)
                queue_position = 0
                if inflight_status == "pending":
                    queue_position = self._pending_position(
                        conn,
                        created_at=str(inflight_row["created_at"]),
                        job_id=int(inflight_row["id"]),
                    )
                conn.commit()
                return {
                    "accepted": False,
                    "reason": "user_inflight",
                    "jobId": int(inflight_row["id"]),
                    "inflightStatus": inflight_status,
                    "queuePosition": queue_position,
                    "queueSize": queue_size,
                }
            queue_size = self._queue_size(conn)
            if queue_size >= self.max_pending:
                conn.commit()
                return {
                    "accepted": False,
                    "reason": "queue_full",
                    "queueSize": queue_size,
                }
            created_at = now
            cursor = conn.execute(
                """
                INSERT INTO jobs (user_openid, job_kind, mode, status, payload_json, source_message_id, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    user_openid,
                    str(job_kind or "full_generation"),
                    str(mode or "experience"),
                    payload_json,
                    str(source_message_id or ""),
                    created_at,
                    now,
                ),
            )
            job_id = int(cursor.lastrowid)
            queue_position = self._pending_position(conn, created_at=created_at, job_id=job_id)
            queue_size = self._queue_size(conn)
            conn.commit()

        return {
            "accepted": True,
            "jobId": job_id,
            "queuePosition": queue_position,
            "queueSize": queue_size,
            "replaced": False,
        }

    def fetch_next_pending(self) -> dict[str, Any] | None:
        now = _now()
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at, id LIMIT 1"
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            job_id = int(row["id"])
            conn.execute(
                "UPDATE jobs SET status='running', started_at=?, updated_at=? WHERE id = ?",
                (now, now, job_id),
            )
            conn.commit()
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
            return {
                "jobId": job_id,
                "userOpenId": row["user_openid"],
                "jobKind": row["job_kind"],
                "mode": row["mode"],
                "payload": payload,
                "sourceMessageId": row["source_message_id"] or "",
            }

    def mark_completed(self, job_id: int, *, run_id: str = "") -> None:
        now = _now()
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            conn.execute(
                "UPDATE jobs SET status='completed', finished_at=?, updated_at=?, run_id=? WHERE id=?",
                (now, now, str(run_id or ""), int(job_id)),
            )
            conn.commit()

    def mark_failed(self, job_id: int, *, error: str = "", run_id: str = "") -> None:
        now = _now()
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            conn.execute(
                "UPDATE jobs SET status='failed', finished_at=?, updated_at=?, run_id=?, error=? WHERE id=?",
                (now, now, str(run_id or ""), str(error or ""), int(job_id)),
            )
            conn.commit()

    def mark_canceled(self, job_id: int, *, reason: str = "") -> None:
        now = _now()
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            conn.execute(
                "UPDATE jobs SET status='canceled', finished_at=?, updated_at=?, error=? WHERE id=?",
                (now, now, str(reason or ""), int(job_id)),
            )
            conn.commit()

    def get_user_queue_info(self, user_openid: str) -> dict[str, Any] | None:
        user_openid = str(user_openid or "").strip()
        if not user_openid:
            return None
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            row = conn.execute(
                "SELECT id, created_at FROM jobs WHERE user_openid = ? AND status = 'pending' ORDER BY created_at, id LIMIT 1",
                (user_openid,),
            ).fetchone()
            if row is None:
                return None
            job_id = int(row["id"])
            created_at = str(row["created_at"])
            queue_size = self._queue_size(conn)
            return {
                "jobId": job_id,
                "queuePosition": self._pending_position(conn, created_at=created_at, job_id=job_id),
                "queueSize": queue_size,
            }

    def get_user_inflight_info(self, user_openid: str) -> dict[str, Any] | None:
        user_openid = str(user_openid or "").strip()
        if not user_openid:
            return None
        with _connect(self.project_dir) as conn:
            _init_schema(conn)
            row = self._user_inflight_row(conn, user_openid)
            if row is None:
                return None
            status = str(row["status"] or "").strip()
            info = {
                "jobId": int(row["id"]),
                "status": status,
                "jobKind": str(row["job_kind"] or "").strip(),
                "mode": str(row["mode"] or "").strip(),
                "runId": str(row["run_id"] or "").strip(),
                "sourceMessageId": str(row["source_message_id"] or "").strip(),
            }
            if status == "pending":
                info["queuePosition"] = self._pending_position(
                    conn,
                    created_at=str(row["created_at"]),
                    job_id=int(row["id"]),
                )
                info["queueSize"] = self._queue_size(conn)
            return info
