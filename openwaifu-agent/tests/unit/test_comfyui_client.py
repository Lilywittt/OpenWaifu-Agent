from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from execution.comfyui_client import (
    _default_comfyui_install_root,
    _default_comfyui_venv_dir,
    _should_bypass_proxy,
)


class ComfyUIClientTests(unittest.TestCase):
    def test_should_bypass_proxy_for_loopback_endpoints(self):
        self.assertTrue(_should_bypass_proxy("http://127.0.0.1:8188/system_stats"))
        self.assertTrue(_should_bypass_proxy("http://localhost:8188/system_stats"))

    def test_should_not_bypass_proxy_for_external_endpoints(self):
        self.assertFalse(_should_bypass_proxy("https://api.deepseek.com/v1/chat/completions"))

    def test_default_comfyui_paths_resolve_from_workspace_root(self):
        with TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            (workspace_root / "ai_must_read.txt").write_text("rules", encoding="utf-8")
            project_dir = workspace_root / "openwaifu-agent"
            project_dir.mkdir()

            self.assertEqual(
                _default_comfyui_install_root(project_dir),
                workspace_root / ".local" / "ComfyUI",
            )
            self.assertEqual(
                _default_comfyui_venv_dir(project_dir),
                workspace_root / ".local" / "comfyui-env",
            )


if __name__ == "__main__":
    unittest.main()
