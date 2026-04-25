from __future__ import annotations

from pathlib import Path

from .browser_common import (
    click_text_candidates,
    fill_first_locator,
    open_edge_page,
    publish_caption,
    receipt_base,
    set_file_input,
)


INSTAGRAM_URL = "https://www.instagram.com/"
INSTAGRAM_CAPTION_SELECTORS = [
    "[contenteditable='true'][aria-label*='caption' i]",
    "[contenteditable='true'][aria-label*='说明']",
    "[contenteditable='true'][aria-label*='文案']",
    "[contenteditable='true'][aria-label*='撰写']",
    "textarea[aria-label*='caption' i]",
    "textarea[placeholder*='caption' i]",
    "textarea",
    "[contenteditable='true']",
]


def _caption_ready(page) -> bool:
    for selector in INSTAGRAM_CAPTION_SELECTORS:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible(timeout=1000):
                return True
        except Exception:
            continue
    return False


def _advance_to_caption_step(page) -> bool:
    for _ in range(4):
        if _caption_ready(page):
            return True
        clicked = click_text_candidates(page, ["Next", "下一步", "继续"], timeout_ms=15000)
        if clicked:
            try:
                page.wait_for_timeout(1800)
            except Exception:
                pass
    return _caption_ready(page)


def publish_to_instagram_browser_draft(
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
    post_url = str(target_config.get("postUrl", INSTAGRAM_URL)).strip() or INSTAGRAM_URL
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
        click_text_candidates(page, ["Create", "创建", "新建", "发帖", "发布"], timeout_ms=8000)
        uploaded = set_file_input(page, image_path)
        caption_ready = _advance_to_caption_step(page)
        caption_filled = fill_first_locator(
            page,
            INSTAGRAM_CAPTION_SELECTORS,
            publish_caption(publish_input, target_config),
        )
        submitted = False
        if bool(target_config.get("autoSubmit", False)):
            submitted = click_text_candidates(page, ["Share", "分享", "发布", "Publish"], timeout_ms=8000)
        status = "published" if submitted else "draft_prepared"
        error = ""
        if not uploaded:
            status = "draft_needs_attention"
            error = "Instagram 页面没有接收图片文件，请确认已登录且创建帖子入口可用。"
        elif not caption_filled:
            status = "draft_needs_attention"
            error = "Instagram 草稿已打开，但没有进入文案填写步骤。"
        return {
            **receipt_base(
                target_id=target_id,
                adapter="instagram_browser_draft",
                status=status,
                page_url=page.url,
                port=session.remote_debugging_port,
                user_data_dir=session.user_data_dir,
            ),
            "imageUploaded": uploaded,
            "captionReady": caption_ready,
            "captionFilled": caption_filled,
            "autoSubmit": bool(target_config.get("autoSubmit", False)),
            "error": error,
        }
    finally:
        session.disconnect()
