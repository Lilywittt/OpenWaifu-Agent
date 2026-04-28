from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.adapters import browser_automation_adapter_names, is_browser_automation_adapter
from publish.adapters.bilibili_dynamic import publish_to_bilibili_dynamic
from publish.adapters.instagram_browser_draft import (
    _click_instagram_share_button,
    publish_to_instagram_browser_draft,
)


class _FakePage:
    def __init__(self, url: str) -> None:
        self.url = url

    def wait_for_load_state(self, *_args, **_kwargs) -> None:
        return None


class _FakeSession:
    def __init__(self, url: str) -> None:
        self.page = _FakePage(url)
        self.remote_debugging_port = 9222
        self.user_data_dir = Path("browser-session")
        self.disconnected = False
        self.close_browser = False

    def disconnect(self, *, close_browser: bool = False) -> None:
        self.disconnected = True
        self.close_browser = close_browser


class _InstagramActionFakePage:
    def __init__(self) -> None:
        self.evaluate_calls: list[dict] = []
        self.url = "https://www.instagram.com/"

    def evaluate(self, _script: str, payload: dict) -> bool:
        self.evaluate_calls.append(payload)
        return True

    def wait_for_timeout(self, *_args, **_kwargs) -> None:
        return None


def _bundle() -> SimpleNamespace:
    base = Path("runtime")
    return SimpleNamespace(
        run_id="adapter-test",
        creative_dir=base / "creative",
        social_post_dir=base / "social_post",
        execution_dir=base / "execution",
        publish_dir=base / "publish",
        output_dir=base / "output",
    )


class PublishBrowserAdaptersTests(unittest.TestCase):
    def test_browser_adapter_metadata_is_centralized(self) -> None:
        self.assertIn("bilibili_dynamic", browser_automation_adapter_names())
        self.assertIn("instagram_browser_draft", browser_automation_adapter_names())
        self.assertTrue(is_browser_automation_adapter("qzone_browser_draft"))
        self.assertFalse(is_browser_automation_adapter("failing_adapter"))

    def test_instagram_receipt_reports_share_ready_before_submit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://www.instagram.com/")
            publish_input = {
                "imagePath": str(image_path),
                "socialPostText": "demo caption",
            }

            with patch("publish.adapters.instagram_browser_draft.open_edge_page", return_value=session), patch(
                "publish.adapters.instagram_browser_draft._open_create_dialog", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft.set_file_input_candidates", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft._advance_to_caption_step", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft._fill_instagram_caption_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.instagram_browser_draft._wait_for_instagram_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.instagram_browser_draft._instagram_share_ready", return_value=True
            ):
                receipt = publish_to_instagram_browser_draft(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="instagram_browser_draft",
                    target_config={"autoSubmit": False},
                    publish_input=publish_input,
                )

            self.assertEqual(receipt["status"], "draft_prepared")
            self.assertTrue(receipt["captionReady"])
            self.assertTrue(receipt["captionFilled"])
            self.assertTrue(receipt["captionCommitted"])
            self.assertTrue(receipt["shareReady"])
            self.assertFalse(receipt["shareClicked"])
            self.assertTrue(session.disconnected)
            self.assertFalse(session.close_browser)

    def test_instagram_auto_submit_uses_scoped_share_action(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://www.instagram.com/")
            publish_input = {
                "imagePath": str(image_path),
                "socialPostText": "demo caption",
            }

            with patch("publish.adapters.instagram_browser_draft.open_edge_page", return_value=session), patch(
                "publish.adapters.instagram_browser_draft._open_create_dialog", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft.set_file_input_candidates", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft._advance_to_caption_step", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft._fill_instagram_caption_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.instagram_browser_draft._wait_for_instagram_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.instagram_browser_draft._instagram_share_ready", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft._click_instagram_share_button", return_value=True
            ) as share_click, patch(
                "publish.adapters.instagram_browser_draft._wait_for_instagram_share_result", return_value=True
            ):
                receipt = publish_to_instagram_browser_draft(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="instagram_browser_draft",
                    target_config={"autoSubmit": True},
                    publish_input=publish_input,
                )

            self.assertEqual(receipt["status"], "published")
            self.assertTrue(receipt["captionCommitted"])
            self.assertTrue(receipt["shareClicked"])
            share_click.assert_called_once_with(session.page, ["demo caption"])
            self.assertTrue(session.disconnected)
            self.assertTrue(session.close_browser)

    def test_instagram_share_button_requires_caption_step_and_rejects_friend_share_labels(self) -> None:
        page = _InstagramActionFakePage()
        with patch("publish.adapters.instagram_browser_draft._caption_ready", return_value=True):
            clicked = _click_instagram_share_button(page)

        self.assertTrue(clicked)
        self.assertEqual(page.evaluate_calls[0]["dialogSelector"], "div[role='dialog']")
        self.assertIn("好友", page.evaluate_calls[0]["wrongHints"])
        self.assertIn("Share", page.evaluate_calls[0]["labels"])

    def test_instagram_manual_target_can_keep_browser_open(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://www.instagram.com/")

            with patch("publish.adapters.instagram_browser_draft.open_edge_page", return_value=session), patch(
                "publish.adapters.instagram_browser_draft._open_create_dialog", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft.set_file_input_candidates", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft._advance_to_caption_step", return_value=True
            ), patch(
                "publish.adapters.instagram_browser_draft._fill_instagram_caption_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.instagram_browser_draft._wait_for_instagram_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.instagram_browser_draft._instagram_share_ready", return_value=True
            ):
                publish_to_instagram_browser_draft(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="instagram_browser_draft",
                    target_config={"autoSubmit": False, "keepBrowserOpen": True},
                    publish_input={"imagePath": str(image_path), "socialPostText": "demo caption"},
                )

            self.assertTrue(session.disconnected)
            self.assertFalse(session.close_browser)

    def test_bilibili_receipt_reports_submit_ready_before_submit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://t.bilibili.com/")
            publish_input = {
                "imagePath": str(image_path),
                "socialPostText": "demo caption",
                "scenePremiseZh": "demo title",
            }

            with patch("publish.adapters.bilibili_dynamic.open_edge_page", return_value=session), patch(
                "publish.adapters.bilibili_dynamic.dismiss_common_popups"
            ), patch(
                "publish.adapters.bilibili_dynamic._looks_logged_out", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic.wait_for_any_locator", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic.fill_first_editor_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._ensure_bilibili_upload_panel", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_existing_images", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_image_preview_count", side_effect=[0, 1]
            ), patch(
                "publish.adapters.bilibili_dynamic.set_file_input_candidates", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_image_upload_commit",
                return_value=(True, {"successCount": 1, "busyCount": 0, "errorCount": 0, "pickerOpen": False}),
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_submit_ready", return_value=True
            ):
                receipt = publish_to_bilibili_dynamic(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="bilibili_dynamic",
                    target_config={"autoSubmit": False, "includeTitle": True, "tags": ["demo"]},
                    publish_input=publish_input,
                )

            self.assertEqual(receipt["status"], "draft_prepared")
            self.assertTrue(receipt["imageUploaded"])
            self.assertTrue(receipt["imagePreviewReady"])
            self.assertTrue(receipt["captionCommitted"])
            self.assertTrue(receipt["publishReady"])
            self.assertTrue(receipt["submitReady"])
            self.assertEqual(receipt["confirmationsClicked"], 0)
            self.assertFalse(receipt["submitClicked"])
            self.assertTrue(session.disconnected)

    def test_bilibili_auto_submit_publishes_when_submit_succeeds(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://t.bilibili.com/")
            publish_input = {
                "imagePath": str(image_path),
                "socialPostText": "demo caption",
                "scenePremiseZh": "demo title",
            }

            with patch("publish.adapters.bilibili_dynamic.open_edge_page", return_value=session), patch(
                "publish.adapters.bilibili_dynamic.dismiss_common_popups"
            ), patch(
                "publish.adapters.bilibili_dynamic._looks_logged_out", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic.wait_for_any_locator", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic.fill_first_editor_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._ensure_bilibili_upload_panel", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_existing_images", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_image_preview_count", side_effect=[0, 1]
            ), patch(
                "publish.adapters.bilibili_dynamic.set_file_input_candidates", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_image_upload_commit",
                return_value=(True, {"successCount": 1, "busyCount": 0, "errorCount": 0, "pickerOpen": False}),
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_submit_ready", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._click_bilibili_submit", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_publish_result",
                return_value=(True, 1),
            ):
                receipt = publish_to_bilibili_dynamic(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="bilibili_dynamic",
                    target_config={"autoSubmit": True, "includeTitle": True, "tags": ["demo"]},
                    publish_input=publish_input,
                )

            self.assertEqual(receipt["status"], "published")
            self.assertTrue(receipt["submitReady"])
            self.assertTrue(receipt["publishReady"])
            self.assertTrue(receipt["submitClicked"])
            self.assertTrue(receipt["submitConfirmed"])
            self.assertEqual(receipt["confirmationsClicked"], 1)

    def test_bilibili_auto_submit_stops_when_image_is_not_committed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://t.bilibili.com/")

            with patch("publish.adapters.bilibili_dynamic.open_edge_page", return_value=session), patch(
                "publish.adapters.bilibili_dynamic.dismiss_common_popups"
            ), patch(
                "publish.adapters.bilibili_dynamic._looks_logged_out", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic.wait_for_any_locator", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic.fill_first_editor_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_editor",
                side_effect=[True, True],
            ), patch(
                "publish.adapters.bilibili_dynamic._ensure_bilibili_upload_panel", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_existing_images", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_image_preview_count", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic.set_file_input_candidates", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_image_upload_commit",
                return_value=(False, {"successCount": 0, "busyCount": 1, "errorCount": 0, "pickerOpen": False}),
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_submit_ready", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._click_bilibili_submit", return_value=True
            ) as submit_click:
                receipt = publish_to_bilibili_dynamic(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="bilibili_dynamic",
                    target_config={"autoSubmit": True},
                    publish_input={"imagePath": str(image_path), "socialPostText": "demo caption"},
                )

            self.assertEqual(receipt["status"], "draft_needs_attention")
            self.assertFalse(receipt["imagePreviewReady"])
            self.assertFalse(receipt["publishReady"])
            self.assertFalse(receipt["submitClicked"])
            self.assertTrue(receipt["editorClearedBeforeFill"])
            self.assertFalse(receipt["draftClearedOnFailure"])
            self.assertFalse(session.close_browser)
            submit_click.assert_not_called()

    def test_bilibili_auto_submit_stops_when_caption_is_not_committed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://t.bilibili.com/")

            with patch("publish.adapters.bilibili_dynamic.open_edge_page", return_value=session), patch(
                "publish.adapters.bilibili_dynamic.dismiss_common_popups"
            ), patch(
                "publish.adapters.bilibili_dynamic._looks_logged_out", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic.wait_for_any_locator", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic.fill_first_editor_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._ensure_bilibili_upload_panel", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_existing_images", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_image_preview_count", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic.set_file_input_candidates", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_image_upload_commit",
                return_value=(True, {"successCount": 1, "busyCount": 0, "errorCount": 0, "pickerOpen": False}),
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_caption_commit",
                return_value=(False, ""),
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_submit_ready", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._click_bilibili_submit", return_value=True
            ) as submit_click:
                receipt = publish_to_bilibili_dynamic(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="bilibili_dynamic",
                    target_config={"autoSubmit": True},
                    publish_input={"imagePath": str(image_path), "socialPostText": "demo caption"},
                )

            self.assertEqual(receipt["status"], "draft_needs_attention")
            self.assertFalse(receipt["captionCommitted"])
            self.assertFalse(receipt["publishReady"])
            self.assertFalse(receipt["submitClicked"])
            submit_click.assert_not_called()

    def test_bilibili_uses_controlled_file_chooser_when_explicitly_enabled(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://t.bilibili.com/")

            with patch("publish.adapters.bilibili_dynamic.open_edge_page", return_value=session), patch(
                "publish.adapters.bilibili_dynamic.dismiss_common_popups"
            ), patch(
                "publish.adapters.bilibili_dynamic._looks_logged_out", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic.wait_for_any_locator", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic.fill_first_editor_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_existing_images", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_image_preview_count", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic.set_file_input_candidates", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic._install_bilibili_file_input_capture", return_value=3
            ) as capture_install, patch(
                "publish.adapters.bilibili_dynamic.set_file_with_chooser", return_value=True
            ) as file_chooser, patch(
                "publish.adapters.bilibili_dynamic._bilibili_file_input_capture_seen", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_image_upload_commit",
                return_value=(True, {"successCount": 1, "busyCount": 0, "errorCount": 0, "pickerOpen": False}),
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_submit_ready", return_value=True
            ):
                receipt = publish_to_bilibili_dynamic(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="bilibili_dynamic",
                    target_config={"autoSubmit": False, "allowNativeFileChooserFallback": True},
                    publish_input={"imagePath": str(image_path), "socialPostText": "demo caption"},
                )

            self.assertEqual(receipt["status"], "draft_prepared")
            self.assertTrue(receipt["imageUploaded"])
            self.assertTrue(receipt["chooserFallbackUsed"])
            self.assertEqual(receipt["uploadMethod"], "file_chooser")
            self.assertEqual(receipt["captureInstallCount"], 3)
            capture_install.assert_called_once()
            file_chooser.assert_called_once()

    def test_bilibili_sets_captured_detached_file_input_before_native_chooser(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://t.bilibili.com/")

            with patch("publish.adapters.bilibili_dynamic.open_edge_page", return_value=session), patch(
                "publish.adapters.bilibili_dynamic.dismiss_common_popups"
            ), patch(
                "publish.adapters.bilibili_dynamic._looks_logged_out", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic.wait_for_any_locator", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic.fill_first_editor_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_existing_images", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_image_preview_count", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic.set_file_input_candidates", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic._install_bilibili_file_input_capture", return_value=3
            ) as capture_install, patch(
                "publish.adapters.bilibili_dynamic._bilibili_file_input_capture_seen", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._set_bilibili_captured_file_input", return_value=True
            ) as captured_set, patch(
                "publish.adapters.bilibili_dynamic.set_file_with_chooser", return_value=True
            ) as file_chooser, patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_image_upload_commit",
                return_value=(True, {"successCount": 1, "busyCount": 0, "errorCount": 0, "pickerOpen": False}),
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_submit_ready", return_value=True
            ):
                receipt = publish_to_bilibili_dynamic(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="bilibili_dynamic",
                    target_config={"autoSubmit": False, "allowNativeFileChooserFallback": True},
                    publish_input={"imagePath": str(image_path), "socialPostText": "demo caption"},
                )

            self.assertEqual(receipt["status"], "draft_prepared")
            self.assertTrue(receipt["imageUploaded"])
            self.assertEqual(receipt["uploadMethod"], "captured_detached_input")
            self.assertTrue(receipt["fileInputCaptured"])
            capture_install.assert_called_once()
            captured_set.assert_called_once()
            file_chooser.assert_not_called()

    def test_bilibili_uses_captured_file_input_when_file_chooser_is_absent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://t.bilibili.com/")

            with patch("publish.adapters.bilibili_dynamic.open_edge_page", return_value=session), patch(
                "publish.adapters.bilibili_dynamic.dismiss_common_popups"
            ), patch(
                "publish.adapters.bilibili_dynamic._looks_logged_out", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic.wait_for_any_locator", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic.fill_first_editor_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_existing_images", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_image_preview_count", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic.set_file_input_candidates", side_effect=[False, True]
            ), patch(
                "publish.adapters.bilibili_dynamic._install_bilibili_file_input_capture", return_value=True
            ) as capture_install, patch(
                "publish.adapters.bilibili_dynamic.set_file_with_chooser", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_file_input_capture_seen", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_image_upload_commit",
                return_value=(True, {"successCount": 1, "busyCount": 0, "errorCount": 0, "pickerOpen": False}),
            ), patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_submit_ready", return_value=True
            ):
                receipt = publish_to_bilibili_dynamic(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="bilibili_dynamic",
                    target_config={"autoSubmit": False},
                    publish_input={"imagePath": str(image_path), "socialPostText": "demo caption"},
                )

            self.assertEqual(receipt["status"], "draft_prepared")
            self.assertTrue(receipt["imageUploaded"])
            self.assertTrue(receipt["imagePreviewReady"])
            self.assertTrue(receipt["chooserFallbackAllowed"])
            self.assertTrue(receipt["chooserFallbackUsed"])
            self.assertEqual(receipt["uploadMethod"], "captured_input")
            self.assertTrue(receipt["fileInputCaptured"])
            capture_install.assert_called_once()

    def test_bilibili_respects_disabled_file_chooser_fallback(self) -> None:
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            image_path = project_dir / "demo.png"
            image_path.write_bytes(b"fake-image")
            session = _FakeSession("https://t.bilibili.com/")

            with patch("publish.adapters.bilibili_dynamic.open_edge_page", return_value=session), patch(
                "publish.adapters.bilibili_dynamic.dismiss_common_popups"
            ), patch(
                "publish.adapters.bilibili_dynamic._looks_logged_out", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic.wait_for_any_locator", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic.fill_first_editor_verified",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._ensure_bilibili_upload_panel", return_value=True
            ), patch(
                "publish.adapters.bilibili_dynamic._clear_bilibili_existing_images", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic._bilibili_image_preview_count", return_value=0
            ), patch(
                "publish.adapters.bilibili_dynamic.set_file_input_candidates", return_value=False
            ), patch(
                "publish.adapters.bilibili_dynamic._install_bilibili_file_input_capture", return_value=True
            ) as capture_install, patch(
                "publish.adapters.bilibili_dynamic._wait_for_bilibili_caption_commit",
                return_value=(True, "demo caption"),
            ), patch(
                "publish.adapters.bilibili_dynamic._click_bilibili_submit", return_value=True
            ) as submit_click:
                receipt = publish_to_bilibili_dynamic(
                    project_dir=project_dir,
                    bundle=_bundle(),
                    target_id="bilibili_dynamic",
                    target_config={"autoSubmit": True, "allowFileChooserFallback": False},
                    publish_input={"imagePath": str(image_path), "socialPostText": "demo caption"},
                )

            self.assertEqual(receipt["status"], "draft_needs_attention")
            self.assertFalse(receipt["imageUploaded"])
            self.assertFalse(receipt["chooserFallbackAllowed"])
            self.assertFalse(receipt["chooserFallbackUsed"])
            self.assertEqual(receipt["uploadMethod"], "")
            capture_install.assert_not_called()
            submit_click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
