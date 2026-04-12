from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.qq_bot_job_queue import QQBotJobQueue
from publish.qq_bot_task_policy import accept_full_generation


class QQBotTaskPolicyTests(unittest.TestCase):
    def test_accept_full_generation_rejects_when_generation_slot_is_busy(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            queue = QQBotJobQueue(project_dir)
            service_runtime = {
                "activeRunId": None,
                "activeUserOpenId": "",
                "activeSourceMessageId": "",
                "currentStage": "",
                "reserved": False,
            }
            with patch(
                "publish.qq_bot_task_policy.read_generation_slot",
                return_value={
                    "ownerType": "content_workbench",
                    "ownerLabel": "night_store",
                    "runId": "run-001",
                    "busyMessage": "本机当前正被内容测试工作台占用，暂时不能开始新的内容任务。",
                },
            ):
                result = accept_full_generation(
                    project_dir=project_dir,
                    job_queue=queue,
                    service_runtime=service_runtime,
                    service_runtime_lock=threading.Lock(),
                    user_openid="user-001",
                )

        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "slot_busy")
        self.assertEqual(result["holder"]["ownerType"], "content_workbench")


if __name__ == "__main__":
    unittest.main()
