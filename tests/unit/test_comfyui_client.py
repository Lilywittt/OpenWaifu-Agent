from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from execution.comfyui_client import _should_bypass_proxy


class ComfyUIClientTests(unittest.TestCase):
    def test_should_bypass_proxy_for_loopback_endpoints(self):
        self.assertTrue(_should_bypass_proxy("http://127.0.0.1:8188/system_stats"))
        self.assertTrue(_should_bypass_proxy("http://localhost:8188/system_stats"))

    def test_should_not_bypass_proxy_for_external_endpoints(self):
        self.assertFalse(_should_bypass_proxy("https://api.deepseek.com/v1/chat/completions"))


if __name__ == "__main__":
    unittest.main()
