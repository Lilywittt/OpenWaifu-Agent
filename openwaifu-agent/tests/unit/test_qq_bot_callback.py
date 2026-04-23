from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.qq_bot_callback import (
    build_callback_verification_response,
    extract_user_openid,
    persist_user_openid,
)


class QQBotCallbackTests(unittest.TestCase):
    def test_build_callback_verification_response_contains_plain_token_and_signature(self):
        response = build_callback_verification_response(
            app_secret="Y2KTP8h4EAtPhmdL",
            payload={"d": {"plain_token": "plain-demo", "event_ts": "1750407202"}, "op": 13},
        )
        self.assertEqual(response["plain_token"], "plain-demo")
        self.assertTrue(response["signature"])

    def test_extract_user_openid_reads_c2c_payload(self):
        self.assertEqual(
            extract_user_openid({"d": {"author": {"user_openid": "user_demo"}}}),
            "user_demo",
        )

    def test_persist_user_openid_updates_latest_file_and_env(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            env_path = project_dir / ".env"
            env_path.write_text("QQ_BOT_USER_OPENID=\n", encoding="utf-8")
            event_path = project_dir / "event.json"
            event_path.write_text("{}", encoding="utf-8")

            latest_path = persist_user_openid(project_dir, user_openid="user_demo", event_path=event_path)

            self.assertTrue(latest_path.exists())
            self.assertIn("QQ_BOT_USER_OPENID=user_demo", env_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
