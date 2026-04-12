from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.qq_bot_job_queue import QQBotJobQueue, job_db_path


class QQBotJobQueueTests(unittest.TestCase):
    def test_enqueue_orders_by_arrival(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)

            result1 = queue.enqueue(
                user_openid="user-1",
                job_kind="full_generation",
                payload={"task": "one"},
                mode="experience",
            )
            self.assertTrue(result1["accepted"])
            self.assertEqual(result1["queuePosition"], 1)
            self.assertEqual(result1["queueSize"], 1)

            result2 = queue.enqueue(
                user_openid="user-2",
                job_kind="full_generation",
                payload={"task": "two"},
                mode="experience",
            )
            self.assertTrue(result2["accepted"])
            self.assertEqual(result2["queuePosition"], 2)
            self.assertEqual(result2["queueSize"], 2)

    def test_enqueue_blocks_second_pending_job_for_same_user(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)

            first = queue.enqueue(
                user_openid="user-1",
                job_kind="full_generation",
                payload={"task": "one"},
                mode="experience",
            )
            queue.enqueue(
                user_openid="user-2",
                job_kind="full_generation",
                payload={"task": "two"},
                mode="experience",
            )
            blocked = queue.enqueue(
                user_openid="user-1",
                job_kind="scene_draft_to_image",
                payload={"task": "three"},
                mode="developer",
            )

            self.assertTrue(first["accepted"])
            self.assertFalse(blocked["accepted"])
            self.assertEqual(blocked["reason"], "user_inflight")
            self.assertEqual(blocked["inflightStatus"], "pending")
            self.assertEqual(blocked["queuePosition"], 1)
            self.assertEqual(blocked["queueSize"], 2)
            info = queue.get_user_queue_info("user-1")
            self.assertIsNotNone(info)
            self.assertEqual(info["queueSize"], 2)

    def test_enqueue_blocks_same_user_while_running(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)

            queue.enqueue(
                user_openid="user-1",
                job_kind="full_generation",
                payload={"task": "one"},
                mode="experience",
            )
            task = queue.fetch_next_pending()
            self.assertIsNotNone(task)

            blocked = queue.enqueue(
                user_openid="user-1",
                job_kind="full_generation",
                payload={"task": "two"},
                mode="experience",
            )

            self.assertFalse(blocked["accepted"])
            self.assertEqual(blocked["reason"], "user_inflight")
            self.assertEqual(blocked["inflightStatus"], "running")
            self.assertEqual(queue.pending_count(), 0)

    def test_fetch_next_pending_marks_running_and_can_reset(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)

            queue.enqueue(
                user_openid="user-1",
                job_kind="full_generation",
                payload={"task": "one"},
                mode="experience",
            )
            task = queue.fetch_next_pending()
            self.assertIsNotNone(task)
            self.assertEqual(task["userOpenId"], "user-1")
            self.assertEqual(queue.pending_count(), 0)

            recovered = queue.reset_abandoned_running()
            self.assertEqual(recovered, 1)
            self.assertEqual(queue.pending_count(), 1)

    def test_enforce_single_inflight_cancels_duplicate_nonterminal_jobs(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)
            db_path = job_db_path(project_dir)
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    """
                    INSERT INTO jobs (user_openid, job_kind, mode, status, payload_json, source_message_id, created_at, updated_at)
                    VALUES (?, ?, ?, 'running', '{}', '', '2026-04-10T10:00:00', '2026-04-10T10:00:00')
                    """,
                    ("user-1", "full_generation", "experience"),
                )
                conn.execute(
                    """
                    INSERT INTO jobs (user_openid, job_kind, mode, status, payload_json, source_message_id, created_at, updated_at)
                    VALUES (?, ?, ?, 'pending', '{}', '', '2026-04-10T10:01:00', '2026-04-10T10:01:00')
                    """,
                    ("user-1", "scene_draft_to_image", "developer"),
                )
                conn.commit()
            finally:
                conn.close()

            normalized = queue.enforce_single_inflight(reason="normalized in test")

            self.assertEqual(normalized, 1)
            inflight = queue.get_user_inflight_info("user-1")
            self.assertIsNotNone(inflight)
            self.assertEqual(inflight["status"], "running")

    def test_single_flight_policy_holds_under_many_users_and_repeat_spam(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir, max_pending=150)

            for index in range(1, 101):
                result = queue.enqueue(
                    user_openid=f"user-{index:03d}",
                    job_kind="full_generation",
                    payload={"task": index},
                    mode="experience",
                )
                self.assertTrue(result["accepted"])

            for index in range(1, 101):
                blocked = queue.enqueue(
                    user_openid=f"user-{index:03d}",
                    job_kind="full_generation",
                    payload={"task": f"repeat-{index}"},
                    mode="experience",
                )
                self.assertFalse(blocked["accepted"])
                self.assertEqual(blocked["reason"], "user_inflight")
                self.assertEqual(blocked["inflightStatus"], "pending")

            self.assertEqual(queue.pending_count(), 100)


if __name__ == "__main__":
    unittest.main()
