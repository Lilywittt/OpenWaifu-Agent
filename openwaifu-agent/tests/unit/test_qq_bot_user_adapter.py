from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.adapters.qq_bot_user import publish_to_qq_bot_user


class QQBotUserAdapterTests(unittest.TestCase):
    def test_publish_to_qq_bot_user_sends_image_with_caption(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            bundle = SimpleNamespace(run_id="demo-run")
            image_path = project_dir / "runtime" / "runs" / "demo-run" / "output" / "demo.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"fake-image")

            publish_input = {
                "socialPostText": "demo social post",
                "imagePath": str(image_path),
            }
            target_config = {
                "adapter": "qq_bot_user",
                "scene": "user",
                "configPath": "config/publish/qq_bot_message.json",
                "replyMessageId": "source-message-id",
                "replyMessageSeq": 2,
            }

            with patch("publish.adapters.qq_bot_user.load_qq_bot_message_config", return_value={"scene": "user", "timeoutMs": 10000}), patch(
                "publish.adapters.qq_bot_user.resolve_qq_bot_credentials",
                return_value={
                    "appId": "appid-demo",
                    "appSecret": "secret-demo",
                    "scene": "user",
                    "targetOpenId": "user-openid-demo",
                    "accessTokenUrl": "https://bots.qq.com/app/getAppAccessToken",
                    "apiBaseUrl": "https://api.sgroup.qq.com",
                    "timeoutMs": 10000,
                },
            ), patch(
                "publish.adapters.qq_bot_user.fetch_app_access_token",
                return_value={"access_token": "access-token-demo", "expires_in": 7200},
            ), patch(
                "publish.adapters.qq_bot_user.send_local_image_message",
                return_value={
                    "id": "message-id-demo",
                    "timestamp": "2026-04-08T18:00:00+08:00",
                    "_upload": {"fileUuid": "file-uuid-demo"},
                },
            ) as send_image:
                receipt = publish_to_qq_bot_user(
                    project_dir=project_dir,
                    bundle=bundle,
                    target_id="qq_bot_user",
                    target_config=target_config,
                    publish_input=publish_input,
                )

        self.assertEqual(receipt["adapter"], "qq_bot_user")
        self.assertEqual(receipt["status"], "published")
        self.assertEqual(receipt["targetOpenId"], "user-openid-demo")
        self.assertEqual(receipt["messageId"], "message-id-demo")
        self.assertEqual(receipt["replyMode"], "passive")
        self.assertEqual(receipt["upload"]["fileUuid"], "file-uuid-demo")
        send_image.assert_called_once()
        self.assertEqual(send_image.call_args.kwargs["msg_id"], "source-message-id")
        self.assertEqual(send_image.call_args.kwargs["msg_seq"], 2)


if __name__ == "__main__":
    unittest.main()
