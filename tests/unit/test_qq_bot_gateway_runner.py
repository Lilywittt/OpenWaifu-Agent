from pathlib import Path
import sys
import unittest

from websocket._exceptions import WebSocketTimeoutException

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tests" / "runners"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from qq_bot_c2c_gateway_runner import _extract_media_specs, _recv_gateway_payload, _resolve_auto_reply_content


class _FakeWebSocket:
    def __init__(self, *, to_raise: Exception | None = None, raw_message: str = ""):
        self._timeout = 10.0
        self._to_raise = to_raise
        self._raw_message = raw_message

    def gettimeout(self):
        return self._timeout

    def settimeout(self, value):
        self._timeout = value

    def recv(self):
        if self._to_raise is not None:
            raise self._to_raise
        return self._raw_message


class QQBotGatewayRunnerTests(unittest.TestCase):
    def test_recv_gateway_payload_returns_none_on_socket_timeout(self):
        ws = _FakeWebSocket(to_raise=WebSocketTimeoutException("Connection timed out"))

        raw_message, payload = _recv_gateway_payload(ws, timeout_seconds=2.0)

        self.assertIsNone(raw_message)
        self.assertIsNone(payload)
        self.assertEqual(ws.gettimeout(), 10.0)

    def test_recv_gateway_payload_returns_json_payload(self):
        ws = _FakeWebSocket(raw_message='{"t":"READY","s":1}')

        raw_message, payload = _recv_gateway_payload(ws, timeout_seconds=2.0)

        self.assertEqual(raw_message, '{"t":"READY","s":1}')
        self.assertEqual(payload["t"], "READY")
        self.assertEqual(ws.gettimeout(), 10.0)

    def test_resolve_auto_reply_content_defaults_to_event_content(self):
        payload = {"d": {"content": "hello qq"}}

        reply_content = _resolve_auto_reply_content(payload, "")

        self.assertEqual(reply_content, "hello qq")

    def test_resolve_auto_reply_content_prefers_manual_override(self):
        payload = {"d": {"content": "hello qq"}}

        reply_content = _resolve_auto_reply_content(payload, "manual")

        self.assertEqual(reply_content, "manual")

    def test_extract_media_specs_normalizes_attachment_url_and_detects_image_type(self):
        payload = {
            "d": {
                "attachments": [
                    {
                        "url": "//gchat.qpic.cn/demo.png",
                        "content_type": "image/png",
                        "name": "demo.png",
                    }
                ]
            }
        }

        media_specs = _extract_media_specs(payload)

        self.assertEqual(len(media_specs), 1)
        self.assertEqual(media_specs[0]["url"], "https://gchat.qpic.cn/demo.png")
        self.assertEqual(media_specs[0]["fileType"], 1)


if __name__ == "__main__":
    unittest.main()
