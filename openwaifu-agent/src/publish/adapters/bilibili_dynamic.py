from __future__ import annotations

from pathlib import Path

from .browser_actions import (
    click_locator_candidates,
    click_visible_text_candidates,
    dismiss_common_popups,
    fill_first_editor_verified,
    has_visible_text_candidates,
    page_visible_text,
    set_file_input_candidates,
    set_file_with_chooser,
    wait_for_any_locator,
)
from .browser_session import open_edge_page, should_keep_browser_open
from .publish_content import publish_caption, publish_tags, publish_title, receipt_base


BILIBILI_DYNAMIC_URL = "https://t.bilibili.com/"
BILIBILI_FILE_INPUT_SELECTORS = [
    "input[type='file'][accept*='image']",
    "input[type='file']",
]
BILIBILI_EDITOR_SELECTORS = [
    ".bili-dyn-publishing__input .bili-rich-textarea__inner[contenteditable='true']",
    ".bili-dyn-publishing .bili-rich-textarea__inner[contenteditable='true']",
    ".bili-dyn-publishing [contenteditable='true'][placeholder*='有什么想和大家分享']",
    "[contenteditable='true'][placeholder*='动态']",
    "[contenteditable='true'][aria-label*='动态']",
    ".bili-dyn-publishing [contenteditable='true']",
    "textarea[placeholder*='动态']",
    ".bili-dyn-publishing textarea",
]
BILIBILI_UPLOAD_BUTTON_TEXTS = [
    "图片",
    "上传图片",
    "添加图片",
]
BILIBILI_UPLOAD_TOOL_SELECTORS = [
    ".bili-dyn-publishing__tools__item.pic",
]
BILIBILI_UPLOAD_ADD_SELECTORS = [
    ".bili-dyn-publishing__image-upload .bili-pics-uploader__add",
    ".bili-pics-uploader__add",
]
BILIBILI_UPLOAD_PANEL_SELECTORS = [
    ".bili-dyn-publishing__image-upload:not([style*='display: none'])",
    ".bili-dyn-publishing__image-upload .bili-pics-uploader",
]
BILIBILI_UPLOAD_SELECTORS = [
    *BILIBILI_UPLOAD_TOOL_SELECTORS,
    *BILIBILI_UPLOAD_ADD_SELECTORS,
    ".bili-dyn-publishing__image",
    ".bili-dyn-publishing__upload",
    "[class*='pics-uploader'] [class*='add']",
    ".upload",
    "[class*='upload']",
]
BILIBILI_IMAGE_PREVIEW_SELECTORS = [
    ".bili-pics-uploader__item.success",
    ".bili-pics-uploader-item-preview[status='SUCCESS']",
    ".bili-pics-uploader-item-preview__pic",
    ".bili-dyn-publishing__image-upload:not([style*='display: none']) img",
    ".bili-dyn-publishing__image-upload [class*='pic'] img",
    ".bili-dyn-publishing__image-upload [class*='image'] img",
    ".bili-pics-uploader img",
    ".bili-pics-uploader__item",
    ".bili-pics-uploader__preview",
    ".bili-pics-uploader__content img",
    "[class*='pics-uploader'] img",
    "[class*='pics-uploader'] [class*='item']",
]
BILIBILI_IMAGE_REMOVE_SELECTORS = [
    ".bili-pics-uploader__item__remove",
]
BILIBILI_SUBMIT_TEXTS = [
    "发布",
    "立即发布",
]
BILIBILI_SUBMIT_SELECTORS = [
    ".bili-dyn-publishing__action.launcher:not(.disabled)",
    ".bili-dyn-publishing__action:not(.disabled):has-text('发布')",
    ".bili-dyn-publishing__headquarters .launcher:not(.disabled)",
]
BILIBILI_SUCCESS_TEXTS = [
    "发布成功",
    "动态发布成功",
]
BILIBILI_CONFIRM_TEXTS = [
    "确认发布",
    "继续发布",
    "仍要发布",
    "确定",
    "确认",
    "我知道了",
    "知道了",
]
BILIBILI_CONFIRM_SCOPE_SELECTOR = (
    ".bili-popup-modal button,.bili-popup-modal [role='button'],"
    ".bili-modal button,.bili-modal [role='button'],"
    ".bili-dialog button,.bili-dialog [role='button'],"
    "[class*='popup'] button,[class*='popup'] [role='button'],"
    "[class*='modal'] button,[class*='modal'] [role='button'],"
    "[class*='dialog'] button,[class*='dialog'] [role='button']"
)


def _dynamic_caption(publish_input: dict, target_config: dict) -> str:
    caption = publish_caption(publish_input, target_config)
    if not bool(target_config.get("includeTitle", False)):
        return caption
    title = publish_title(publish_input, target_config)
    if title and title not in caption:
        return "\n\n".join([title, caption]) if caption else title
    return caption


def _caption_required_fragments(publish_input: dict, caption_text: str) -> list[str]:
    social_text = str(publish_input.get("socialPostText", "")).strip()
    for line in social_text.splitlines():
        if len("".join(line.split())) >= 8:
            return [line]
    return [caption_text]


def _append_tags(text: str, tags: list[str]) -> str:
    normalized_tags = [f"#{tag.strip().lstrip('#')}#" for tag in tags if str(tag).strip()]
    if not normalized_tags:
        return text
    suffix = " ".join(normalized_tags)
    return "\n\n".join([part for part in (text.strip(), suffix) if part])


def _looks_logged_out(page) -> bool:
    text = page_visible_text(page)
    return "探索属于你的新世界" in text or "赶快注册或登录" in text


def _click_bilibili_upload(page) -> bool:
    if _ensure_bilibili_upload_panel(page):
        return _click_bilibili_upload_add(page)
    if click_locator_candidates(page, BILIBILI_UPLOAD_SELECTORS, timeout_ms=3000):
        return True
    return click_visible_text_candidates(
        page,
        BILIBILI_UPLOAD_BUTTON_TEXTS,
        timeout_ms=3000,
        scope_selector=".bili-dyn-publishing button,.bili-dyn-publishing a,.bili-dyn-publishing [role='button'],.bili-dyn-publishing div,.bili-dyn-publishing span",
    )


def _ensure_bilibili_upload_panel(page) -> bool:
    if wait_for_any_locator(page, BILIBILI_UPLOAD_PANEL_SELECTORS, timeout_ms=800):
        return True
    if not click_locator_candidates(page, BILIBILI_UPLOAD_TOOL_SELECTORS, timeout_ms=3000):
        return False
    return wait_for_any_locator(page, BILIBILI_UPLOAD_PANEL_SELECTORS, timeout_ms=5000)


def _click_bilibili_upload_add(page) -> bool:
    if not _ensure_bilibili_upload_panel(page):
        return False
    return click_locator_candidates(page, BILIBILI_UPLOAD_ADD_SELECTORS, timeout_ms=5000)


def _wait_for_bilibili_image_preview(page) -> bool:
    for _ in range(90):
        if _bilibili_image_preview_count(page) > 0:
            return True
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
    return False


def _bilibili_image_preview_count(page) -> int:
    script = """
    () => Array.from(document.querySelectorAll(
      ".bili-pics-uploader__item.success, .bili-pics-uploader-item-preview[status='SUCCESS'], .bili-pics-uploader-item-preview__pic"
    )).filter((element) => {
      const rect = element.getBoundingClientRect();
      return rect.width > 1 && rect.height > 1 && rect.bottom > 0 && rect.right > 0;
    }).length
    """
    try:
        return int(page.evaluate(script))
    except Exception:
        return 0


def _clear_bilibili_existing_images(page) -> int:
    removed = 0
    click_script = """
    (selectors) => {
      for (const selector of selectors) {
        const element = Array.from(document.querySelectorAll(selector)).find((candidate) => {
          const rect = candidate.getBoundingClientRect();
          return rect.width > 1 && rect.height > 1 && rect.bottom > 0 && rect.right > 0;
        });
        if (!element) continue;
        element.scrollIntoView({ block: "center", inline: "center" });
        const rect = element.getBoundingClientRect();
        const x = rect.left + Math.min(Math.max(rect.width / 2, 1), rect.width - 1);
        const y = rect.top + Math.min(Math.max(rect.height / 2, 1), rect.height - 1);
        const target = document.elementFromPoint(x, y) || element;
        for (const type of ["mouseover", "mousedown", "mouseup", "click"]) {
          target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y }));
        }
        if (target !== element) {
          element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y }));
        }
        return true;
      }
      return false;
    }
    """
    for _ in range(9):
        try:
            clicked = bool(page.evaluate(click_script, BILIBILI_IMAGE_REMOVE_SELECTORS))
        except Exception:
            clicked = click_locator_candidates(page, BILIBILI_IMAGE_REMOVE_SELECTORS, timeout_ms=1000)
        if not clicked:
            break
        removed += 1
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
    return removed


def _click_bilibili_submit(page) -> bool:
    if click_locator_candidates(page, BILIBILI_SUBMIT_SELECTORS, timeout_ms=5000):
        return True
    return click_visible_text_candidates(
        page,
        BILIBILI_SUBMIT_TEXTS,
        timeout_ms=5000,
        scope_selector=".bili-dyn-publishing__action,.bili-dyn-publishing button,.bili-dyn-publishing [role='button']",
    )


def _bilibili_submit_ready(page) -> bool:
    if wait_for_any_locator(page, BILIBILI_SUBMIT_SELECTORS, timeout_ms=2000):
        return True
    return has_visible_text_candidates(
        page,
        BILIBILI_SUBMIT_TEXTS,
        timeout_ms=2000,
        scope_selector=".bili-dyn-publishing__action,.bili-dyn-publishing button,.bili-dyn-publishing [role='button']",
    )


def _click_bilibili_post_submit_confirmation(page) -> int:
    clicked_count = 0
    for _ in range(4):
        clicked = click_visible_text_candidates(
            page,
            BILIBILI_CONFIRM_TEXTS,
            timeout_ms=1500,
            scope_selector=BILIBILI_CONFIRM_SCOPE_SELECTOR,
        )
        if not clicked:
            break
        clicked_count += 1
        try:
            page.wait_for_timeout(1200)
        except Exception:
            pass
    return clicked_count


def _wait_for_bilibili_publish_result(page) -> tuple[bool, int]:
    confirmations_clicked = 0
    for _ in range(30):
        confirmations_clicked += _click_bilibili_post_submit_confirmation(page)
        for text in BILIBILI_SUCCESS_TEXTS:
            try:
                if page.get_by_text(text, exact=False).first.is_visible(timeout=500):
                    return True, confirmations_clicked
            except Exception:
                pass
        try:
            if not wait_for_any_locator(page, [".bili-dyn-publishing"], timeout_ms=300):
                return True, confirmations_clicked
        except Exception:
            pass
        try:
            page.wait_for_timeout(1000)
        except Exception:
            pass
    return False, confirmations_clicked


def publish_to_bilibili_dynamic(
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
    post_url = str(target_config.get("postUrl", BILIBILI_DYNAMIC_URL)).strip() or BILIBILI_DYNAMIC_URL
    configured_session_dir = str(target_config.get("browserSessionUserDataDir", "")).strip()
    session = open_edge_page(
        project_dir,
        post_url,
        session_name=f"{bundle.run_id}_{target_id}",
        session_user_data_dir=Path(configured_session_dir) if configured_session_dir else None,
        persistent_user_data_dir=bool(target_config.get("browserSessionPersistent", False)),
    )
    page = session.page
    try:
        page.wait_for_load_state("domcontentloaded", timeout=45000)
        dismiss_common_popups(page)
        logged_out = _looks_logged_out(page)
        if logged_out:
            return {
                **receipt_base(
                    target_id=target_id,
                    adapter="bilibili_dynamic",
                    status="draft_needs_attention",
                    page_url=page.url,
                    port=session.remote_debugging_port,
                    user_data_dir=session.user_data_dir,
                ),
                "editorReady": False,
                "captionFilled": False,
                "captionTextLength": 0,
                "imageUploaded": False,
                "imagePreviewReady": False,
                "imagePreviewCount": 0,
                "submitReady": False,
                "submitClicked": False,
                "submitConfirmed": False,
                "confirmationsClicked": 0,
                "autoSubmit": bool(target_config.get("autoSubmit", True)),
                "loggedOut": True,
                "error": "Bilibili 发布 profile 未登录。请在打开的页面完成登录，登录后重新触发 Bilibili 动态发布。",
            }
        editor_ready = wait_for_any_locator(page, BILIBILI_EDITOR_SELECTORS, timeout_ms=12000)
        caption_text = _append_tags(_dynamic_caption(publish_input, target_config), publish_tags(publish_input, target_config))
        caption_filled, caption_editor_text = fill_first_editor_verified(
            page,
            BILIBILI_EDITOR_SELECTORS,
            caption_text,
            required_fragments=_caption_required_fragments(publish_input, caption_text),
        )
        _ensure_bilibili_upload_panel(page)
        existing_images_cleared = _clear_bilibili_existing_images(page)
        stale_image_count = _bilibili_image_preview_count(page)
        if not wait_for_any_locator(page, BILIBILI_FILE_INPUT_SELECTORS, timeout_ms=1500, visible=False):
            _ensure_bilibili_upload_panel(page)
        uploaded = set_file_input_candidates(page, BILIBILI_FILE_INPUT_SELECTORS, image_path)
        if not uploaded:
            uploaded = set_file_with_chooser(page, image_path, lambda: _click_bilibili_upload_add(page))
        image_preview_ready = _wait_for_bilibili_image_preview(page) if uploaded and stale_image_count == 0 else False
        image_preview_count = _bilibili_image_preview_count(page) if image_preview_ready else 0
        submit_ready = _bilibili_submit_ready(page) if image_preview_ready else False

        submit_clicked = False
        submit_confirmed = False
        confirmations_clicked = 0
        if bool(target_config.get("autoSubmit", True)) and image_preview_ready and submit_ready:
            submit_clicked = _click_bilibili_submit(page)
            if submit_clicked:
                submit_confirmed, confirmations_clicked = _wait_for_bilibili_publish_result(page)
        trust_submit_click = bool(target_config.get("trustSubmitClick", False))
        status = "published" if submit_clicked and (submit_confirmed or trust_submit_click) else "draft_prepared"
        error = ""
        if not editor_ready or not caption_filled:
            status = "draft_needs_attention"
            error = "Bilibili 动态正文没有写入平台编辑器，已停止自动发布。"
        elif not uploaded:
            status = "draft_needs_attention"
            error = "Bilibili 动态页面没有接收图片文件，请人工检查上传控件。"
        elif stale_image_count > 0:
            status = "draft_needs_attention"
            error = "Bilibili 动态编辑器里有旧图片没有清理掉，已停止自动发布。"
        elif not image_preview_ready:
            status = "draft_needs_attention"
            error = "Bilibili 图片文件已提交给页面，但没有检测到图片预览，已停止自动发布。"
        elif bool(target_config.get("autoSubmit", True)) and not submit_clicked:
            status = "draft_needs_attention"
            error = "Bilibili 动态已填好图文，但没有找到发布按钮。"
        elif bool(target_config.get("autoSubmit", True)) and submit_clicked and not submit_confirmed and not trust_submit_click:
            status = "draft_needs_attention"
            error = "Bilibili 发布按钮已点击，但没有检测到成功状态，请人工确认平台结果。"
        return {
            **receipt_base(
                target_id=target_id,
                adapter="bilibili_dynamic",
                status=status,
                page_url=page.url,
                port=session.remote_debugging_port,
                user_data_dir=session.user_data_dir,
            ),
            "editorReady": editor_ready,
            "captionFilled": caption_filled,
            "captionTextLength": len(caption_editor_text),
            "imageUploaded": uploaded,
            "imagePreviewReady": image_preview_ready,
            "imagePreviewCount": image_preview_count,
            "existingImagesCleared": existing_images_cleared,
            "submitReady": submit_ready,
            "submitClicked": submit_clicked,
            "submitConfirmed": submit_confirmed,
            "confirmationsClicked": confirmations_clicked,
            "autoSubmit": bool(target_config.get("autoSubmit", True)),
            "trustSubmitClick": trust_submit_click,
            "loggedOut": logged_out,
            "error": error,
        }
    finally:
        session.disconnect(close_browser=not should_keep_browser_open(target_config))
