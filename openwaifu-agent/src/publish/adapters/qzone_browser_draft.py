from __future__ import annotations

import time
from pathlib import Path

from env import get_env_value

from .browser_actions import (
    click_locator_candidates,
    click_visible_text_candidates,
    dismiss_common_popups,
    fill_first_editor,
    page_visible_text,
    set_file_input_candidates,
    set_file_with_chooser,
    wait_for_any_locator,
)
from .browser_session import open_edge_page
from .publish_content import publish_caption, receipt_base


QZONE_URL = "https://user.qzone.qq.com/"
QZONE_EDITOR_SELECTORS = [
    "#qz_poster_editor_v4_container",
    "#QM_Mood_Poster_Container [contenteditable='true']",
    "[contenteditable='true'][placeholder*='说点']",
    "[contenteditable='true'][aria-label*='说说']",
    "[contenteditable='true']",
    "textarea[placeholder*='说点']",
    "textarea",
]
QZONE_FILE_INPUT_SELECTORS = [
    "input[type='file'][accept*='image']",
    "input[type='file']",
]
QZONE_UPLOAD_BUTTON_TEXTS = [
    "照片",
    "图片",
    "上传图片",
    "添加图片",
]
QZONE_PHOTO_SELECTORS = [
    "#QM_Mood_Poster_Container .item-pic a.pic",
    "#QM_Mood_Poster_Container .item-pic",
    "#QM_Mood_Poster_Container a.pic",
]
QZONE_LOCAL_UPLOAD_SELECTORS = [
    "#QM_Mood_Poster_Container .qz_poster_btn_local_pic a",
    "#QM_Mood_Poster_Container .qz_poster_btn_local_pic",
    ".qz_poster_btn_local_pic a",
    ".qz_poster_btn_local_pic",
]


def _qzone_post_url(project_dir: Path, target_config: dict) -> str:
    configured = str(target_config.get("postUrl", QZONE_URL)).strip() or QZONE_URL
    user_id = str(target_config.get("userId", "")).strip()
    if not user_id:
        user_id = get_env_value(project_dir, str(target_config.get("userIdEnvName", "QZONE_USER_ID")), "")
    if user_id and configured.rstrip("/") in {"https://user.qzone.qq.com", "http://user.qzone.qq.com"}:
        return f"https://user.qzone.qq.com/{user_id.strip()}"
    return configured


def _authorization_required(page) -> bool:
    try:
        if any("ptlogin" in str(frame.url).casefold() for frame in page.frames):
            return True
    except Exception:
        pass
    text = page_visible_text(page)
    return "QQ登录" in text and "说点儿什么吧" not in text


def _wait_for_authorization(page, timeout_seconds: int) -> bool:
    deadline = time.monotonic() + max(5, timeout_seconds)
    while time.monotonic() < deadline:
        if wait_for_any_locator(page, QZONE_EDITOR_SELECTORS, timeout_ms=1000):
            return True
        if not _authorization_required(page):
            return True
        try:
            page.wait_for_timeout(1000)
        except Exception:
            time.sleep(1)
    return False


def _click_qzone_local_upload(page) -> bool:
    hovered = False
    for selector in QZONE_PHOTO_SELECTORS:
        try:
            locator = page.locator(selector).first
            if int(locator.count()) <= 0:
                continue
            locator.hover(timeout=3000, force=True)
            hovered = True
            break
        except Exception:
            continue
    if not hovered:
        hovered = click_visible_text_candidates(
            page,
            QZONE_UPLOAD_BUTTON_TEXTS,
            timeout_ms=3000,
            scope_selector="#QM_Mood_Poster_Container a,#QM_Mood_Poster_Container div",
        )
    try:
        page.wait_for_timeout(500)
    except Exception:
        pass
    return click_locator_candidates(page, QZONE_LOCAL_UPLOAD_SELECTORS, timeout_ms=3000) or click_visible_text_candidates(
        page,
        ["本地"],
        timeout_ms=3000,
        scope_selector="#QM_Mood_Poster_Container a,#QM_Mood_Poster_Container li,#QM_Mood_Poster_Container span",
    )


def publish_to_qzone_browser_draft(
    *,
    project_dir: Path,
    bundle,
    target_id: str,
    target_config: dict,
    publish_input: dict,
) -> dict:
    image_path = Path(str(publish_input.get("imagePath", "")).strip()).resolve()
    if not image_path.exists():
        raise RuntimeError(f"发布图片不存在：{image_path}")
    post_url = _qzone_post_url(project_dir, target_config)
    configured_session_dir = str(target_config.get("browserSessionUserDataDir", "")).strip()
    session = open_edge_page(
        project_dir,
        post_url,
        session_name=f"{bundle.run_id}_{target_id}",
        session_user_data_dir=Path(configured_session_dir) if configured_session_dir else None,
    )
    page = session.page
    try:
        page.wait_for_load_state("domcontentloaded", timeout=45000)
        dismiss_common_popups(page)
        authorization_required = _authorization_required(page)
        if authorization_required:
            try:
                authorization_wait_seconds = int(target_config.get("authorizationWaitSeconds", 75))
            except (TypeError, ValueError):
                authorization_wait_seconds = 75
            authorization_ready = _wait_for_authorization(page, authorization_wait_seconds)
            if not authorization_ready:
                return {
                    **receipt_base(
                        target_id=target_id,
                        adapter="qzone_browser_draft",
                        status="draft_needs_attention",
                        page_url=page.url,
                        port=session.remote_debugging_port,
                        user_data_dir=session.user_data_dir,
                    ),
                    "editorReady": False,
                    "captionFilled": False,
                    "imageUploaded": False,
                    "autoSubmit": False,
                    "authorizationRequired": True,
                    "error": "QQ 空间等待头像授权超时。请重新触发后在打开的页面点击头像授权。",
                }
        editor_ready = wait_for_any_locator(page, QZONE_EDITOR_SELECTORS, timeout_ms=12000)
        caption_filled = fill_first_editor(page, QZONE_EDITOR_SELECTORS, publish_caption(publish_input, target_config))
        if not wait_for_any_locator(page, QZONE_FILE_INPUT_SELECTORS, timeout_ms=1500, visible=False):
            _click_qzone_local_upload(page)
        uploaded = set_file_input_candidates(page, QZONE_FILE_INPUT_SELECTORS, image_path)
        if not uploaded:
            uploaded = set_file_with_chooser(page, image_path, lambda: _click_qzone_local_upload(page))
        status = "draft_prepared"
        error = ""
        if not editor_ready or not caption_filled:
            status = "draft_needs_attention"
            error = "QQ 空间编辑器没有成功填入正文，请确认登录态和页面状态。"
        elif not uploaded:
            status = "draft_needs_attention"
            error = "QQ 空间页面没有接收图片文件，请人工检查上传控件。"
        return {
            **receipt_base(
                target_id=target_id,
                adapter="qzone_browser_draft",
                status=status,
                page_url=page.url,
                port=session.remote_debugging_port,
                user_data_dir=session.user_data_dir,
            ),
            "editorReady": editor_ready,
            "captionFilled": caption_filled,
            "imageUploaded": uploaded,
            "autoSubmit": False,
            "authorizationRequired": False,
            "error": error,
        }
    finally:
        session.disconnect()
