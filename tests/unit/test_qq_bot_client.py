from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from io_utils import write_json
from publish.qq_bot_client import (
    build_file_endpoint,
    build_markdown_payload,
    build_media_payload,
    build_message_endpoint,
    build_message_payload,
    build_rich_media_upload_payload,
    build_text_message_payload,
    detect_image_file_type,
    fetch_app_access_token,
    load_qq_bot_message_config,
    resolve_qq_bot_credentials,
    send_local_image_message,
    send_text_message,
    upload_rich_media,
)


class QQBotClientTests(unittest.TestCase):
    def test_build_message_endpoint_supports_group_and_user(self):
        self.assertEqual(
            build_message_endpoint("https://api.sgroup.qq.com", "group", "group-openid"),
            "https://api.sgroup.qq.com/v2/groups/group-openid/messages",
        )
        self.assertEqual(
            build_message_endpoint("https://api.sgroup.qq.com", "user", "user-openid"),
            "https://api.sgroup.qq.com/v2/users/user-openid/messages",
        )
        self.assertEqual(
            build_file_endpoint("https://api.sgroup.qq.com", "user", "user-openid"),
            "https://api.sgroup.qq.com/v2/users/user-openid/files",
        )

    def test_build_text_message_payload_rejects_empty_content(self):
        with self.assertRaises(RuntimeError):
            build_text_message_payload("  ")

    def test_build_markdown_payload(self):
        markdown_payload = build_markdown_payload("## hello")
        self.assertEqual(markdown_payload["content"], "## hello")

    def test_build_media_payload_and_message_payload(self):
        media_payload = build_media_payload("file-info-demo")
        self.assertEqual(media_payload, {"file_info": "file-info-demo"})

        message_payload = build_message_payload(
            msg_type=7,
            content="caption",
            media=media_payload,
            msg_id="msg-demo",
            msg_seq=2,
        )
        self.assertEqual(message_payload["msg_type"], 7)
        self.assertEqual(message_payload["content"], "caption")
        self.assertEqual(message_payload["media"]["file_info"], "file-info-demo")
        self.assertEqual(message_payload["msg_id"], "msg-demo")
        self.assertEqual(message_payload["msg_seq"], 2)

    def test_build_rich_media_upload_payload_accepts_url_or_file_data(self):
        payload = build_rich_media_upload_payload(file_type=1, url="https://example.com/image.png", srv_send_msg=False)
        self.assertEqual(payload["file_type"], 1)
        self.assertEqual(payload["url"], "https://example.com/image.png")

        payload = build_rich_media_upload_payload(file_type=1, file_data="ZmFrZQ==", srv_send_msg=False)
        self.assertEqual(payload["file_data"], "ZmFrZQ==")

    def test_resolve_credentials_reads_env_names_from_config(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            write_json(
                project_dir / "config" / "publish" / "qq_bot_message.json",
                {
                    "appIdEnvName": "QQ_BOT_APP_ID",
                    "appSecretEnvName": "QQ_BOT_APP_SECRET",
                    "scene": "group",
                    "groupOpenIdEnvName": "QQ_BOT_GROUP_OPENID",
                },
            )
            (project_dir / ".env").write_text(
                "\n".join(
                    [
                        "QQ_BOT_APP_ID=appid-demo",
                        "QQ_BOT_APP_SECRET=secret-demo",
                        "QQ_BOT_GROUP_OPENID=group-openid-demo",
                    ]
                ),
                encoding="utf-8",
            )
            config = load_qq_bot_message_config(project_dir)
            resolved = resolve_qq_bot_credentials(project_dir, config)

            self.assertEqual(resolved["appId"], "appid-demo")
            self.assertEqual(resolved["appSecret"], "secret-demo")
            self.assertEqual(resolved["scene"], "group")
            self.assertEqual(resolved["targetOpenId"], "group-openid-demo")

    def test_fetch_access_token_and_send_text_message_use_expected_payloads(self):
        calls = []

        def fake_post(url, payload, headers, timeout_ms):
            calls.append(
                {
                    "url": url,
                    "payload": payload,
                    "headers": headers,
                    "timeoutMs": timeout_ms,
                }
            )
            if url.endswith("/getAppAccessToken"):
                return {"access_token": "access-token-demo", "expires_in": 7200}
            return {"id": "message-id-demo", "timestamp": 1234567890}

        with patch("publish.qq_bot_client._post_json", side_effect=fake_post):
            token = fetch_app_access_token(
                app_id="appid-demo",
                app_secret="secret-demo",
                access_token_url="https://bots.qq.com/app/getAppAccessToken",
                timeout_ms=10000,
            )
            message = send_text_message(
                access_token="access-token-demo",
                api_base_url="https://api.sgroup.qq.com",
                scene="group",
                target_openid="group-openid-demo",
                content="hello qq bot",
                timeout_ms=10000,
                msg_id="origin-msg",
                msg_seq=1,
            )

        self.assertEqual(token["access_token"], "access-token-demo")
        self.assertEqual(calls[0]["payload"]["appId"], "appid-demo")
        self.assertEqual(calls[0]["payload"]["clientSecret"], "secret-demo")
        self.assertEqual(calls[1]["url"], "https://api.sgroup.qq.com/v2/groups/group-openid-demo/messages")
        self.assertEqual(calls[1]["headers"]["Authorization"], "QQBot access-token-demo")
        self.assertEqual(calls[1]["payload"]["content"], "hello qq bot")
        self.assertEqual(calls[1]["payload"]["msg_id"], "origin-msg")
        self.assertEqual(calls[1]["payload"]["msg_seq"], 1)
        self.assertEqual(message["id"], "message-id-demo")

    def test_upload_rich_media_and_send_local_image_message(self):
        calls = []

        def fake_post(url, payload, headers, timeout_ms):
            calls.append({"url": url, "payload": payload, "headers": headers, "timeoutMs": timeout_ms})
            if url.endswith("/files"):
                return {"file_uuid": "file-uuid-demo", "file_info": "file-info-demo", "ttl": 60}
            return {"id": "message-id-demo", "timestamp": "2026-04-08T18:00:00+08:00"}

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "demo.png"
            image_path.write_bytes(b"fake-image")

            with patch("publish.qq_bot_client._post_json", side_effect=fake_post):
                upload_result = upload_rich_media(
                    access_token="access-token-demo",
                    api_base_url="https://api.sgroup.qq.com",
                    scene="user",
                    target_openid="user-openid-demo",
                    file_type=1,
                    url="https://example.com/demo.png",
                    srv_send_msg=False,
                    timeout_ms=10000,
                )
                message_result = send_local_image_message(
                    access_token="access-token-demo",
                    api_base_url="https://api.sgroup.qq.com",
                    scene="user",
                    target_openid="user-openid-demo",
                    image_path=image_path,
                    content="caption",
                    timeout_ms=10000,
                    msg_id="origin-msg",
                    msg_seq=1,
                )

        self.assertEqual(upload_result["file_info"], "file-info-demo")
        self.assertEqual(calls[0]["url"], "https://api.sgroup.qq.com/v2/users/user-openid-demo/files")
        self.assertEqual(calls[1]["url"], "https://api.sgroup.qq.com/v2/users/user-openid-demo/files")
        self.assertEqual(calls[2]["url"], "https://api.sgroup.qq.com/v2/users/user-openid-demo/messages")
        self.assertEqual(calls[2]["payload"]["msg_type"], 7)
        self.assertEqual(calls[2]["payload"]["media"]["file_info"], "file-info-demo")
        self.assertEqual(calls[2]["payload"]["content"], "caption")
        self.assertEqual(calls[2]["payload"]["msg_id"], "origin-msg")
        self.assertEqual(message_result["id"], "message-id-demo")
        self.assertIn("fileUuid", message_result["_upload"])

    def test_detect_image_file_type_supports_png_and_jpg(self):
        self.assertEqual(detect_image_file_type(Path("demo.png")), 1)
        self.assertEqual(detect_image_file_type(Path("demo.jpg")), 1)
        with self.assertRaises(RuntimeError):
            detect_image_file_type(Path("demo.gif"))

    def test_fetch_access_token_retries_retryable_failures(self):
        calls = {"count": 0}

        def fake_post(url, payload, headers, timeout_ms):
            calls["count"] += 1
            if calls["count"] == 1:
                raise TimeoutError("timed out")
            return {"access_token": "access-token-demo", "expires_in": 7200}

        with patch("publish.qq_bot_client._post_json", side_effect=fake_post), patch(
            "publish.qq_bot_client.time.sleep", return_value=None
        ):
            token = fetch_app_access_token(
                app_id="appid-demo",
                app_secret="secret-demo",
                access_token_url="https://bots.qq.com/app/getAppAccessToken",
                timeout_ms=10000,
            )

        self.assertEqual(token["access_token"], "access-token-demo")
        self.assertEqual(calls["count"], 2)


if __name__ == "__main__":
    unittest.main()
