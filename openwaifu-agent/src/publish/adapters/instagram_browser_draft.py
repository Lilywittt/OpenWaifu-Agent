from __future__ import annotations

import time
from pathlib import Path

from .browser_actions import (
    click_locator_candidates,
    click_visible_text_candidates,
    dismiss_common_popups,
    fill_first_editor_verified,
    set_file_input_candidates,
    wait_for_any_locator,
)
from .browser_session import open_edge_page, should_keep_browser_open
from .publish_content import publish_caption, receipt_base


INSTAGRAM_URL = "https://www.instagram.com/"
INSTAGRAM_FILE_INPUT_SELECTORS = [
    "input[type='file'][accept*='image']",
    "input[type='file']",
]
INSTAGRAM_CAPTION_SELECTORS = [
    "div[role='dialog'] [contenteditable='true'][aria-label*='Write a caption' i]",
    "div[role='dialog'] [contenteditable='true'][aria-label*='caption' i]",
    "div[role='dialog'] [contenteditable='true'][aria-placeholder*='caption' i]",
    "div[role='dialog'] [contenteditable='true'][aria-label*='说明']",
    "div[role='dialog'] [contenteditable='true'][aria-label*='文案']",
    "div[role='dialog'] [contenteditable='true'][aria-label*='撰写']",
    "div[role='dialog'] textarea[aria-label*='caption' i]",
    "div[role='dialog'] textarea[placeholder*='caption' i]",
    "div[role='dialog'] textarea",
    "div[role='dialog'] [contenteditable='true']",
]
INSTAGRAM_CAPTION_READY_SELECTORS = [
    "div[role='dialog'] [contenteditable='true'][aria-label*='Write a caption' i]",
    "div[role='dialog'] [contenteditable='true'][aria-label*='caption' i]",
    "div[role='dialog'] [contenteditable='true'][aria-placeholder*='caption' i]",
    "div[role='dialog'] [contenteditable='true'][aria-label*='说明']",
    "div[role='dialog'] [contenteditable='true'][aria-label*='文案']",
    "div[role='dialog'] [contenteditable='true'][aria-label*='撰写']",
    "div[role='dialog'] textarea[aria-label*='caption' i]",
    "div[role='dialog'] textarea[placeholder*='caption' i]",
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
INSTAGRAM_DIALOG_SELECTOR = "div[role='dialog']"
INSTAGRAM_DIALOG_ACTION_SCOPE = (
    "button,[role='button'],a[href='#'],div[tabindex='0'],span[role='button']"
)
INSTAGRAM_WRONG_SHARE_HINTS = [
    "send",
    "message",
    "friend",
    "friends",
    "direct",
    "copylink",
    "shareto",
    "发送",
    "私信",
    "好友",
    "朋友",
    "复制链接",
    "分享给",
]


def _caption_required_fragments(publish_input: dict, caption_text: str) -> list[str]:
    social_text = str(publish_input.get("socialPostText", "")).strip()
    for line in social_text.splitlines():
        if len("".join(line.split())) >= 8:
            return [line]
    return [caption_text]


def _read_instagram_caption_text(page) -> str:
    script = """
    ({ dialogSelector }) => {
      const visible = (element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width >= 2
          && rect.height >= 2
          && rect.bottom >= 0
          && rect.right >= 0
          && rect.top <= window.innerHeight
          && rect.left <= window.innerWidth
          && style.visibility !== "hidden"
          && style.display !== "none";
      };
      const dialogs = Array.from(document.querySelectorAll(dialogSelector)).filter(visible);
      const selectors = [
        "[contenteditable='true'][aria-label*='Write a caption' i]",
        "[contenteditable='true'][aria-label*='caption' i]",
        "[contenteditable='true'][aria-placeholder*='caption' i]",
        "[contenteditable='true'][aria-label*='说明']",
        "[contenteditable='true'][aria-label*='文案']",
        "[contenteditable='true'][aria-label*='撰写']",
        "textarea[aria-label*='caption' i]",
        "textarea[placeholder*='caption' i]",
        "textarea",
        "[contenteditable='true']",
      ];
      for (const dialog of dialogs) {
        for (const selector of selectors) {
          const element = Array.from(dialog.querySelectorAll(selector)).find(visible);
          if (!element) continue;
          if ("value" in element) return element.value || "";
          return element.innerText || element.textContent || "";
        }
      }
      return "";
    }
    """
    try:
        return str(page.evaluate(script, {"dialogSelector": INSTAGRAM_DIALOG_SELECTOR}) or "")
    except Exception:
        return ""


def _fill_instagram_caption_verified(page, caption_text: str, required_fragments: list[str]) -> tuple[bool, str]:
    def compact(value: str) -> str:
        return "".join(ch for ch in str(value or "") if not ch.isspace() and ch != "\u200b")

    filled, editor_text = fill_first_editor_verified(
        page,
        INSTAGRAM_CAPTION_SELECTORS,
        caption_text,
        required_fragments=required_fragments,
        timeout_ms=10000,
    )
    if not filled:
        return False, editor_text

    compact_fragments = [compact(fragment) for fragment in required_fragments if compact(fragment)]
    deadline = time.monotonic() + 5
    last_text = editor_text
    while time.monotonic() < deadline:
        current_text = _read_instagram_caption_text(page)
        if current_text:
            last_text = current_text
        compact_current = compact(current_text)
        if compact_fragments and all(fragment in compact_current for fragment in compact_fragments):
            try:
                page.wait_for_timeout(1200)
            except Exception:
                time.sleep(1.2)
            return True, current_text
        try:
            page.wait_for_timeout(250)
        except Exception:
            time.sleep(0.25)
    return False, last_text


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


def _click_instagram_dialog_action(page, labels: list[str], *, timeout_ms: int = 5000) -> bool:
    script = """
    ({ labels, dialogSelector, scopeSelector, wrongHints }) => {
      const normalize = (value) => String(value || "").replace(/\\s+/g, "").toLowerCase();
      const wanted = labels.map(normalize).filter(Boolean);
      const hints = wrongHints.map(normalize).filter(Boolean);
      const visible = (element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width >= 2
          && rect.height >= 2
          && rect.bottom >= 0
          && rect.right >= 0
          && rect.top <= window.innerHeight
          && rect.left <= window.innerWidth
          && style.visibility !== "hidden"
          && style.display !== "none";
      };
      const dialogs = Array.from(document.querySelectorAll(dialogSelector))
        .filter(visible)
        .sort((left, right) => {
          const leftRect = left.getBoundingClientRect();
          const rightRect = right.getBoundingClientRect();
          return (rightRect.width * rightRect.height) - (leftRect.width * leftRect.height);
        });
      for (const dialog of dialogs) {
        const dialogText = normalize(dialog.innerText || dialog.textContent || "");
        const createDialog =
          dialog.querySelector("input[type='file']")
          || dialog.querySelector("[contenteditable='true']")
          || dialogText.includes("create")
          || dialogText.includes("newpost")
          || dialogText.includes("创建")
          || dialogText.includes("新帖子")
          || dialogText.includes("caption")
          || dialogText.includes("说明")
          || dialogText.includes("文案")
          || dialogText.includes("撰写");
        if (!createDialog) continue;
        const dialogRect = dialog.getBoundingClientRect();
        const candidates = Array.from(dialog.querySelectorAll(scopeSelector))
          .filter(visible)
          .map((element) => {
            const rawText = element.innerText || element.textContent || element.getAttribute("aria-label") || element.title || "";
            const text = normalize(rawText);
            const rect = element.getBoundingClientRect();
            const exact = wanted.includes(text);
            const aria = normalize(element.getAttribute("aria-label") || element.title || "");
            const ariaExact = wanted.includes(aria);
            const wrong = hints.some((hint) => text.includes(hint) || aria.includes(hint));
            const nearTopRight = rect.top <= dialogRect.top + Math.max(96, dialogRect.height * 0.18)
              && rect.left >= dialogRect.left + dialogRect.width * 0.48;
            return {
              element,
              exact,
              ariaExact,
              wrong,
              nearTopRight,
              score:
                (exact ? 1000 : 0)
                + (ariaExact ? 800 : 0)
                + (nearTopRight ? 160 : 0)
                - (wrong ? 2000 : 0)
                - Math.abs((rect.top + rect.bottom) / 2 - dialogRect.top),
            };
          })
          .filter((item) => (item.exact || item.ariaExact) && !item.wrong)
          .sort((left, right) => right.score - left.score);
        const picked = candidates[0]?.element;
        if (!picked) continue;
        picked.scrollIntoView({ block: "center", inline: "center" });
        const rect = picked.getBoundingClientRect();
        const x = rect.left + Math.min(Math.max(rect.width / 2, 1), rect.width - 1);
        const y = rect.top + Math.min(Math.max(rect.height / 2, 1), rect.height - 1);
        const target = document.elementFromPoint(x, y) || picked;
        for (const type of ["mouseover", "mousedown", "mouseup", "click"]) {
          target.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y }));
        }
        if (target !== picked) {
          picked.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y }));
        }
        return true;
      }
      return false;
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            if page.evaluate(
                script,
                {
                    "labels": labels,
                    "dialogSelector": INSTAGRAM_DIALOG_SELECTOR,
                    "scopeSelector": INSTAGRAM_DIALOG_ACTION_SCOPE,
                    "wrongHints": INSTAGRAM_WRONG_SHARE_HINTS,
                },
            ):
                return True
        except Exception:
            pass
        try:
            page.wait_for_timeout(250)
        except Exception:
            time.sleep(0.25)
    return False


def _click_instagram_next_step(page) -> bool:
    if _click_instagram_dialog_action(page, INSTAGRAM_NEXT_TEXTS, timeout_ms=3000):
        return True
    return click_visible_text_candidates(
        page,
        INSTAGRAM_NEXT_TEXTS,
        timeout_ms=4000,
        scope_selector="div[role='dialog'] button,div[role='dialog'] [role='button']",
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
    if not _caption_ready(page):
        return False
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


def _click_instagram_share_button(page) -> bool:
    if not _caption_ready(page):
        return False
    return _click_instagram_dialog_action(page, INSTAGRAM_SHARE_TEXTS, timeout_ms=12000)


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
        required_fragments = _caption_required_fragments(publish_input, caption_text)
        caption_filled, caption_editor_text = _fill_instagram_caption_verified(
            page,
            caption_text,
            required_fragments,
        )
        share_ready = _instagram_share_ready(page) if caption_filled else False
        share_clicked = False
        submit_confirmed = False
        if bool(target_config.get("autoSubmit", False)) and caption_filled and share_ready:
            share_clicked = _click_instagram_share_button(page)
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
        session.disconnect(close_browser=not should_keep_browser_open(target_config))
