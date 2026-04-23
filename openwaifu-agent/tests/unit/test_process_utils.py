from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from process_utils import is_process_alive, resolve_background_python_executable


class ProcessUtilsTests(unittest.TestCase):
    def test_resolve_background_python_executable_prefers_pythonw_on_windows(self):
        with TemporaryDirectory() as temp_dir:
            scripts_dir = Path(temp_dir)
            python_path = scripts_dir / "python.exe"
            pythonw_path = scripts_dir / "pythonw.exe"
            python_path.write_text("", encoding="utf-8")
            pythonw_path.write_text("", encoding="utf-8")

            resolved = resolve_background_python_executable(python_path)

        self.assertEqual(resolved, pythonw_path.resolve())

    def test_resolve_background_python_executable_falls_back_to_python_when_pythonw_missing(self):
        with TemporaryDirectory() as temp_dir:
            scripts_dir = Path(temp_dir)
            python_path = scripts_dir / "python.exe"
            python_path.write_text("", encoding="utf-8")

            resolved = resolve_background_python_executable(python_path)

        self.assertEqual(resolved, python_path.resolve())

    def test_is_process_alive_uses_win32_fallback_on_windows(self):
        if os.name != "nt":
            self.skipTest("Windows-only fallback")

        fake_kernel32 = type(
            "Kernel32",
            (),
            {
                "OpenProcess": staticmethod(lambda *_args: 0),
                "GetExitCodeProcess": staticmethod(lambda *_args: 0),
                "CloseHandle": staticmethod(lambda *_args: 1),
            },
        )()
        completed = type("Completed", (), {"stdout": '"pythonw.exe","1234","Console","1","10,000 K"\n'})()
        with patch("process_utils.ctypes.WinDLL", return_value=fake_kernel32), patch(
            "process_utils.ctypes.get_last_error",
            return_value=123,
        ), patch("process_utils.subprocess.run", return_value=completed):
            self.assertTrue(is_process_alive(1234))


if __name__ == "__main__":
    unittest.main()
