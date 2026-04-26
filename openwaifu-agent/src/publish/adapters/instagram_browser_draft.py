from __future__ import annotations

import time
from pathlib import Path

from .browser_actions import (
    click_locator_candidates,
    click_visible_text_candidates,
    dismiss_common_popups,
    fill_first_editor_verified,
    has_visible_text_candidates,
    set_file_input_candidates,
    wait_for_any_locator,
)
from .browser_session import open_edge_page
from .publish_content import publish_caption, receipt_base


INSTAGRAM_URL = "https://www.instagram.com/"
INSTAGRAM_FILE_INPUT_SELECTORS = [
    "input[type='file'][accept*='image']",
    "input[type='file']",
]
INSTAGRAM_CAPTION_SELECTORS = [
    "[contenteditable='true'][aria-label*='caption' i]",
    "[contenteditable='true'][aria-placeholder*='caption' i]",
    "[contenteditable='true'][aria-label*='Write a caption' i]",
    "[contenteditable='true'][aria-label*='说明']",
    "[contenteditable='true'][aria-label*='文案']",
    "[contenteditable='true'][aria-label*='撰写']",
    "textarea[aria-label*='caption' i]",
    "textarea[placeholder*='caption' i]",
    "textarea",
    "[contenteditable='true']",
]
INSTAGRAM_CAPTION_READY_SELECTORS = [
    "[contenteditable='true'][aria-label*='caption' i]",
    "[contenteditable='true'][aria-placeholder*='caption' i]",
    "[contenteditable='true'][aria-label*='Write a caption' i]",
    "[contenteditable='true'][aria-label*='说明']",
    "[contenteditable='true'][aria-label*='文案']",
    "[contenteditable='true'][aria-label*='撰写']",
    "textarea[aria-label*='caption' i]",
    "textarea[placeholder*='caption' i]",
]
INSTAGRAM_CREATE_SELECTORS = [
    "a[href='#']:has(svg[aria-label='新帖子'])",
    "a[href='#']:has(svg[aria-label='New post'])",
    "a[href='#']:has-text('新帖子')",
    "a[href='#']:has-text('创建')",
    "a[href='#']:has-text('Create')",
    "svg[aria-label='New post']",
    "svg[aria-label='新帖子']",
    "div[role='button']:has-text('Create')",
    "div[role='button']:has-text('创建')",
]
INSTAGRAM_CREATE_TEXTS = ["创建", "Create", "New post", "新帖子"]
INSTAGRAM_NEXT_TEXTS = ["Next", "下一步", "继续"]
INSTAGRAM_SHARE_TEXTS = ["Share", "分享", "发布", "Publish"]
INSTAGRAM_SHARE_DONE_TEXTS = [
    "Your post has been shared",
    "Post shared",
    "已分享",
    "发布成功",
]


def _caption_required_fragments(publish_input: dict, caption_text: str) -> list[str]:
    social_text = str(publish_input.get("socialPostText", "")).strip()
    for line in social_text.splitlines():
        if len("".join(line.split())) >= 8:
            return [line]
    return [caption_text]


def _click_create_nav(page) -> bool:
    selectors = (
        "a[href='#']:has(svg[aria-label='新帖子'])",
        "a[href='#']:has(svg[aria-label='New post'])",
    )
    deadline = time.monotonic() + 18
    while time.monotonic() < deadline:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if int(locator.count()) <= 0:
                    continue
                try:
                    locator.click(timeout=1500)
                except Exception:
                    locator.evaluate("(element) => element.click()")
                return True
            except Exception:
                continue
        try:
            page.wait_for_timeout(500)
        except Exception:
            time.sleep(0.5)
    return False


def _caption_ready(page) -> bool:
    return wait_for_any_locator(page, INSTAGRAM_CAPTION_READY_SELECTORS, timeout_ms=1000)


def _click_instagram_next_step(page) -> bool:
    selectors: list[str] = []
    for label in INSTAGRAM_NEXT_TEXTS:
        selectors.extend(
            [
                f"div[role='dialog'] button:has-text('{label}')",
                f"div[role='dialog'] div[role='button']:has-text('{label}')",
                f"div[role='dialog'] [role='button']:has-text('{label}')",
            ]
        )
    if click_locator_candidates(page, selectors, timeout_ms=3000):
        return True
    return click_visible_text_candidates(
        page,
        INSTAGRAM_NEXT_TEXTS,
        timeout_ms=4000,
        scope_selector="div[role='dialog'] button,div[role='dialog'] [role='button'],button,[role='button']",
    )


def _advance_to_caption_step(page) -> bool:
    for _ in range(6):
        if _caption_ready(page):
            return True
        clicked = _click_instagram_next_step(page)
        if clicked:
            try:
                page.wait_for_timeout(2200)
            except Exception:
                pass
    return _caption_ready(page)


def _instagram_share_ready(page) -> bool:
    if has_visible_text_candidates(
        page,
        INSTAGRAM_SHARE_TEXTS,
        timeout_ms=3000,
        scope_selector="div[role='dialog'] button,div[role='dialog'] [role='button'],button,[role='button']",
    ):
        return True
    selectors: list[str] = []
    for label in INSTAGRAM_SHARE_TEXTS:
        selectors.extend(
            [
                f"div[role='dialog'] button:has-text('{label}')",
                f"div[role='dialog'] div[role='button']:has-text('{label}')",
                f"div[role='dialog'] [role='button']:has-text('{label}')",
            ]
        )
    return wait_for_any_locator(page, selectors, timeout_ms=2000)


def _open_create_dialog(page) -> bool:
    dismiss_common_popups(page)
    if wait_for_any_locator(page, INSTAGRAM_FILE_INPUT_SELECTORS, timeout_ms=1000, visible=False):
        return True
    current_url = str(getattr(page, "url", "") or "").split("?", 1)[0].rstrip("/")
    if current_url != INSTAGRAM_URL.rstrip("/"):
        try:
            page.goto(INSTAGRAM_URL, wait_until="domcontentloaded", timeout=25000)
        except Exception:
            pass
    dismiss_common_popups(page)
    if wait_for_any_locator(page, INSTAGRAM_FILE_INPUT_SELECTORS, timeout_ms=1000, visible=False):
        return True
    if _click_create_nav(page):
        return wait_for_any_locator(page, INSTAGRAM_FILE_INPUT_SELECTORS, timeout_ms=10000, visible=False)
    if click_locator_candidates(page, INSTAGRAM_CREATE_SELECTORS, timeout_ms=1200):
        return wait_for_any_locator(page, INSTAGRAM_FILE_INPUT_SELECTORS, timeout_ms=10000, visible=False)
    if click_visible_text_candidates(page, INSTAGRAM_CREATE_TEXTS, timeout_ms=3000):
        return wait_for_any_locator(page, INSTAGRAM_FILE_INPUT_SELECTORS, timeout_ms=10000, visible=False)
    return False


def _wait_for_instagram_share_result(page) -> bool:
    for _ in range(18):
        for text in INSTAGRAM_SHARE_DONE_TEXTS:
            try:
                if page.get_by_text(text, exact=False).first.is_visible(timeout=500):
                    return True
            except Exception:
                pass
        try:
            page.wait_for_timeout(1000)
        except Exception:
            pass
    return False


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
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    try:
        create_opened = _open_create_dialog(page)
        uploaded = False
        if create_opened:
            uploaded = set_file_input_candidates(page, INSTAGRAM_FILE_INPUT_SELECTORS, image_path)
        caption_ready = _advance_to_caption_step(page)
        caption_text = publish_caption(publish_input, target_config)
        caption_filled, caption_editor_text = fill_first_editor_verified(
            page,
            INSTAGRAM_CAPTION_SELECTORS,
            caption_text,
            required_fragments=_caption_required_fragments(publish_input, caption_text),
        )
        share_ready = _instagram_share_ready(page) if caption_filled else False
        share_clicked = False
        submit_confirmed = False
        if bool(target_config.get("autoSubmit", False)) and caption_filled and share_ready:
            share_clicked = click_visible_text_candidates(page, INSTAGRAM_SHARE_TEXTS, timeout_ms=12000)
            submit_confirmed = _wait_for_instagram_share_result(page) if share_clicked else False
        auto_submit = bool(target_config.get("autoSubmit", False))
        trust_share_click = bool(target_config.get("trustShareClick", False))
        status = "published" if share_clicked and (submit_confirmed or trust_share_click) else "draft_prepared"
        error = ""
        if not create_opened:
            status = "draft_needs_attention"
            error = "Instagram 创建帖子入口没有打开，请确认登录态和页面状态。"
        elif not uploaded:
            status = "draft_needs_attention"
            error = "Instagram 页面没有接收图片文件，请确认已登录且创建帖子入口可用。"
        elif not caption_filled:
            status = "draft_needs_attention"
            error = "Instagram 草稿已打开，但正文没有写入平台编辑器，已停止自动分享。"
        elif auto_submit and not share_ready:
            status = "draft_needs_attention"
            error = "Instagram 正文已写入，但分享按钮没有进入可用状态，已停止自动分享。"
        elif auto_submit and not share_clicked:
            status = "draft_needs_attention"
            error = "Instagram 草稿已准备，但没有找到分享按钮。"
        elif auto_submit and share_clicked and not submit_confirmed and not trust_share_click:
            status = "draft_needs_attention"
            error = "Instagram 分享按钮已点击，但没有检测到成功提示，请人工确认平台状态。"
        return {
            **receipt_base(
                target_id=target_id,
                adapter="instagram_browser_draft",
                status=status,
                page_url=page.url,
                port=session.remote_debugging_port,
                user_data_dir=session.user_data_dir,
            ),
            "createOpened": create_opened,
            "imageUploaded": uploaded,
            "captionReady": caption_ready,
            "captionFilled": caption_filled,
            "captionTextLength": len(caption_editor_text),
            "shareReady": share_ready,
            "shareClicked": share_clicked,
            "submitConfirmed": submit_confirmed,
            "autoSubmit": auto_submit,
            "trustShareClick": trust_share_click,
            "error": error,
        }
    finally:
        session.disconnect()
