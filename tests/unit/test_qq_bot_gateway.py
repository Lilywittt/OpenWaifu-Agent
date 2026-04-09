from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.qq_bot_gateway import (
    QQ_BOT_C2C_INTENT,
    build_gateway_heartbeat_payload,
    build_gateway_identify_payload,
    build_gateway_info_url,
    fetch_gateway_info,
    persist_user_openid,
)


class QQBotGatewayTests(unittest.TestCase):
    def test_build_gateway_info_url(self):
        self.assertEqual(
            build_gateway_info_url("https://api.sgroup.qq.com"),
            "https://api.sgroup.qq.com/gateway/bot",
        )

    def test_build_identify_and_heartbeat_payloads(self):
        identify = build_gateway_identify_payload(access_token="token-demo", intents=QQ_BOT_C2C_INTENT)
        self.assertEqual(identify["op"], 2)
        self.assertEqual(identify["d"]["token"], "QQBot token-demo")
        self.assertEqual(identify["d"]["intents"], QQ_BOT_C2C_INTENT)
        self.assertEqual(identify["d"]["shard"], [0, 1])

        heartbeat = build_gateway_heartbeat_payload(12)
        self.assertEqual(heartbeat, {"op": 1, "d": 12})

    def test_fetch_gateway_info_uses_auth_headers(self):
        calls = []

        def fake_request_json(url, *, headers, timeout_ms):
            calls.append({"url": url, "headers": headers, "timeoutMs": timeout_ms})
            return {"url": "wss://api.sgroup.qq.com/websocket", "shards": 1}

        with patch("publish.qq_bot_gateway._request_json", side_effect=fake_request_json):
            result = fetch_gateway_info(
                app_id="appid-demo",
                access_token="access-token-demo",
                api_base_url="https://api.sgroup.qq.com",
                timeout_ms=8000,
            )

        self.assertEqual(result["url"], "wss://api.sgroup.qq.com/websocket")
        self.assertEqual(calls[0]["url"], "https://api.sgroup.qq.com/gateway/bot")
        self.assertEqual(calls[0]["headers"]["Authorization"], "QQBot access-token-demo")
        self.assertEqual(calls[0]["headers"]["X-Union-Appid"], "appid-demo")

    def test_persist_user_openid_updates_env(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            event_path = project_dir / "event.json"
            event_path.write_text("{}", encoding="utf-8")
            (project_dir / ".env").write_text("QQ_BOT_USER_OPENID=\n", encoding="utf-8")

            latest_path = persist_user_openid(project_dir, user_openid="user_demo", event_path=event_path)

            self.assertTrue(latest_path.exists())
            self.assertIn("QQ_BOT_USER_OPENID=user_demo", (project_dir / ".env").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
