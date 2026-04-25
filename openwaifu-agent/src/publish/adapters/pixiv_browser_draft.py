from __future__ import annotations

from pathlib import Path

from .browser_common import (
    click_text_candidates,
    fill_first_locator,
    open_edge_page,
    publish_caption,
    publish_tags,
    publish_title,
    receipt_base,
    set_file_input,
)


PIXIV_CREATE_URL = "https://www.pixiv.net/illustration/create"


def _fill_pixiv_tags(page, tags: list[str]) -> int:
    filled = 0
    for tag in tags:
        if fill_first_locator(
            page,
            [
                "input[placeholder*='タグ']",
                "input[aria-label*='タグ']",
                "input[name*='tag']",
            ],
            tag,
        ):
            try:
                page.keyboard.press("Enter")
            except Exception:
                pass
            filled += 1
    return filled


def publish_to_pixiv_browser_draft(
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
    post_url = str(target_config.get("postUrl", PIXIV_CREATE_URL)).strip() or PIXIV_CREATE_URL
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
        uploaded = set_file_input(page, image_path)
        title_filled = fill_first_locator(
            page,
            [
                "input[placeholder*='タイトル']",
                "input[aria-label*='タイトル']",
                "input[name*='title']",
            ],
            publish_title(publish_input, target_config),
        )
        caption_filled = fill_first_locator(
            page,
            [
                "textarea[placeholder*='キャプション']",
                "textarea[aria-label*='キャプション']",
                "textarea",
                "[contenteditable='true']",
            ],
            publish_caption(publish_input, target_config),
        )
        tags_filled = _fill_pixiv_tags(page, publish_tags(publish_input, target_config))
        submitted = False
        if bool(target_config.get("autoSubmit", False)):
            submitted = click_text_candidates(page, ["投稿する", "公開する", "发布", "Publish"])
        status = "published" if submitted else "draft_prepared"
        error = ""
        if not uploaded:
            status = "draft_needs_attention"
            error = "Pixiv 投稿页没有接收图片文件，请确认登录态和页面状态。"
        elif not title_filled or not caption_filled:
            status = "draft_needs_attention"
            error = "Pixiv 草稿已打开，但标题或说明没有自动填入。"
        return {
            **receipt_base(
                target_id=target_id,
                adapter="pixiv_browser_draft",
                status=status,
                page_url=page.url,
                port=session.remote_debugging_port,
                user_data_dir=session.user_data_dir,
            ),
            "imageUploaded": uploaded,
            "titleFilled": title_filled,
            "captionFilled": caption_filled,
            "tagsFilled": tags_filled,
            "autoSubmit": bool(target_config.get("autoSubmit", False)),
            "error": error,
        }
    finally:
        session.disconnect()
