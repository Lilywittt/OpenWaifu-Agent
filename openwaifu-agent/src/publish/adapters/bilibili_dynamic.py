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
BILIBILI_IMAGE_SUCCESS_SELECTORS = [
    ".bili-pics-uploader__item.success",
    ".bili-pics-uploader-item-preview[status='SUCCESS']",
    ".bili-pics-uploader-item-preview__pic",
    ".bili-dyn-publishing__image-upload img[src]",
    ".bili-pics-uploader img[src]",
    "[class*='pics-uploader'] img[src]",
]
BILIBILI_IMAGE_UPLOAD_BUSY_SELECTORS = [
    ".bili-pics-uploader__item.uploading",
    ".bili-pics-uploader__item.loading",
    ".bili-pics-uploader-item-preview[status='UPLOADING']",
    ".bili-pics-uploader-item-preview[status='WAITING']",
    ".bili-dyn-publishing__image-upload [class*='progress']",
    ".bili-dyn-publishing__image-upload [class*='loading']",
    ".bili-dyn-publishing__image-upload [class*='uploading']",
    "[class*='pics-uploader'] [class*='progress']",
    "[class*='pics-uploader'] [class*='loading']",
    "[class*='pics-uploader'] [class*='uploading']",
]
BILIBILI_IMAGE_UPLOAD_ERROR_SELECTORS = [
    ".bili-pics-uploader__item.error",
    ".bili-pics-uploader-item-preview[status='ERROR']",
    ".bili-pics-uploader-item-preview[status='FAIL']",
    ".bili-dyn-publishing__image-upload [class*='error']",
    ".bili-dyn-publishing__image-upload [class*='fail']",
    ".bili-dyn-publishing__image-upload [class*='retry']",
    "[class*='pics-uploader'] [class*='error']",
    "[class*='pics-uploader'] [class*='fail']",
    "[class*='pics-uploader'] [class*='retry']",
]
BILIBILI_IMAGE_PICKER_LABELS = [
    "选择图片",
    "本地上传",
    "上传图片",
    "图片空间",
]
BILIBILI_IMAGE_PICKER_DISMISS_TEXTS = [
    "取消",
    "关闭",
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


def _normalize_text_for_commit(value: str) -> str:
    return "".join(ch for ch in str(value or "") if not ch.isspace() and ch != "\u200b")


def _text_contains_fragments(text: str, fragments: list[str]) -> bool:
    normalized_text = _normalize_text_for_commit(text)
    normalized_fragments = [_normalize_text_for_commit(fragment) for fragment in fragments if _normalize_text_for_commit(fragment)]
    if not normalized_fragments:
        return bool(normalized_text)
    return all(fragment in normalized_text for fragment in normalized_fragments)


def _append_tags(text: str, tags: list[str]) -> str:
    normalized_tags = [f"#{tag.strip().lstrip('#')}#" for tag in tags if str(tag).strip()]
    if not normalized_tags:
        return text
    suffix = " ".join(normalized_tags)
    return "\n\n".join([part for part in (text.strip(), suffix) if part])


def _looks_logged_out(page) -> bool:
    text = page_visible_text(page)
    return "探索属于你的新世界" in text or "赶快注册或登录" in text


def _ensure_bilibili_upload_panel(page) -> bool:
    return wait_for_any_locator(page, BILIBILI_UPLOAD_PANEL_SELECTORS, timeout_ms=800)


def _click_bilibili_upload_tool(page) -> bool:
    if click_locator_candidates(page, BILIBILI_UPLOAD_TOOL_SELECTORS, timeout_ms=3000):
        return True
    return click_visible_text_candidates(
        page,
        BILIBILI_UPLOAD_BUTTON_TEXTS,
        timeout_ms=3000,
        scope_selector=".bili-dyn-publishing button,.bili-dyn-publishing a,.bili-dyn-publishing [role='button'],.bili-dyn-publishing div,.bili-dyn-publishing span",
    )


def _click_bilibili_upload_add(page) -> bool:
    if _ensure_bilibili_upload_panel(page):
        return click_locator_candidates(page, BILIBILI_UPLOAD_ADD_SELECTORS, timeout_ms=5000)
    return _click_bilibili_upload_tool(page)


def _bilibili_roots(page) -> list:
    roots = [page]
    try:
        roots.extend(page.frames)
    except Exception:
        pass
    return roots


def _install_bilibili_file_input_capture_in_root(root) -> bool:
    script = """
    () => {
      const captureVersion = 2;
      if (window.__openwaifuBiliFileCaptureVersion === captureVersion) return true;
      window.__openwaifuBiliFileCaptureInstalled = true;
      window.__openwaifuBiliFileCaptureVersion = captureVersion;
      window.__openwaifuBiliOriginalInputClick = window.__openwaifuBiliOriginalInputClick || HTMLInputElement.prototype.click;
      window.__openwaifuBiliCapturedFileInput = false;
      window.__openwaifuBiliCapturedFileInputElement = null;
      const markInput = (input) => {
        if (!input || String(input.type || "").toLowerCase() !== "file") return false;
        input.setAttribute("data-openwaifu-bili-file-input", "1");
        window.__openwaifuBiliCapturedFileInput = true;
        window.__openwaifuBiliCapturedFileInputElement = input;
        return true;
      };
      HTMLInputElement.prototype.click = function(...args) {
        if (markInput(this)) return undefined;
        return window.__openwaifuBiliOriginalInputClick.apply(this, args);
      };
      document.addEventListener("click", (event) => {
        const target = event.target;
        if (!target || !target.closest) return;
        const input = target.matches?.("input[type='file']") ? target : target.querySelector?.("input[type='file']");
        if (markInput(input)) {
          event.preventDefault();
          event.stopImmediatePropagation();
          return;
        }
        const label = target.closest("label");
        const control = label?.control;
        if (markInput(control)) {
          event.preventDefault();
          event.stopImmediatePropagation();
        }
      }, true);
      return true;
    }
    """
    try:
        return bool(root.evaluate(script))
    except Exception:
        return False


def _install_bilibili_file_input_capture(page) -> int:
    return sum(1 for root in _bilibili_roots(page) if _install_bilibili_file_input_capture_in_root(root))


def _set_bilibili_captured_file_input(page, image_path: Path) -> bool:
    for root in _bilibili_roots(page):
        handle = None
        try:
            handle = root.evaluate_handle("() => window.__openwaifuBiliCapturedFileInputElement || null")
            element = handle.as_element()
            if element is None:
                continue
            element.set_input_files(str(image_path), timeout=45000)
            return True
        except Exception:
            continue
        finally:
            try:
                if handle is not None:
                    handle.dispose()
            except Exception:
                pass
    return False


def _bilibili_file_input_capture_seen(page) -> bool:
    for root in _bilibili_roots(page):
        try:
            if bool(root.evaluate("() => Boolean(window.__openwaifuBiliCapturedFileInput)")):
                return True
        except Exception:
            continue
    return False


def _bilibili_upload_dom_debug(page) -> dict:
    script = """
    () => ({
      fileInputCount: document.querySelectorAll("input[type='file']").length,
      capturedFileInputCount: document.querySelectorAll("input[type='file'][data-openwaifu-bili-file-input='1']").length,
      capturedDetachedFileInput: Boolean(window.__openwaifuBiliCapturedFileInputElement),
      uploadButtonText: Array.from(document.querySelectorAll("button,a,[role='button'],div,span"))
        .map((element) => (element.innerText || element.textContent || element.getAttribute("aria-label") || element.title || "").trim())
        .filter((text) => /图片|上传|本地|动态/.test(text))
        .slice(0, 12),
      href: location.href,
    })
    """
    frames: list[dict] = []
    for root in _bilibili_roots(page):
        try:
            payload = root.evaluate(script)
        except Exception:
            continue
        if isinstance(payload, dict):
            frames.append(
                {
                    "href": str(payload.get("href", "") or "")[:180],
                    "fileInputCount": int(payload.get("fileInputCount", 0) or 0),
                    "capturedFileInputCount": int(payload.get("capturedFileInputCount", 0) or 0),
                    "capturedDetachedFileInput": bool(payload.get("capturedDetachedFileInput", False)),
                    "uploadButtonText": [str(item)[:80] for item in payload.get("uploadButtonText", []) if str(item).strip()],
                }
            )
    return {
        "frameCount": len(frames),
        "fileInputCount": sum(item["fileInputCount"] for item in frames),
        "capturedFileInputCount": sum(item["capturedFileInputCount"] for item in frames),
        "capturedDetachedFileInput": any(item["capturedDetachedFileInput"] for item in frames),
        "frames": frames[:8],
    }


def _dismiss_bilibili_image_picker(page) -> None:
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    click_visible_text_candidates(
        page,
        BILIBILI_IMAGE_PICKER_DISMISS_TEXTS,
        timeout_ms=800,
        scope_selector=BILIBILI_CONFIRM_SCOPE_SELECTOR,
    )


def _set_bilibili_image_file(
    page,
    image_path: Path,
    *,
    allow_file_chooser: bool,
    allow_native_file_chooser: bool = False,
) -> dict:
    if set_file_input_candidates(page, BILIBILI_FILE_INPUT_SELECTORS, image_path):
        return {
            "uploaded": True,
            "chooserFallbackUsed": False,
            "uploadMethod": "direct_input",
            "fileInputCaptured": False,
            "captureInstallCount": 0,
            "uploadDomDebug": _bilibili_upload_dom_debug(page),
        }
    if not allow_file_chooser:
        return {
            "uploaded": False,
            "chooserFallbackUsed": False,
            "uploadMethod": "",
            "fileInputCaptured": False,
            "captureInstallCount": 0,
            "uploadDomDebug": _bilibili_upload_dom_debug(page),
        }
    capture_install_count = _install_bilibili_file_input_capture(page)
    captured_selectors = [
        "input[type='file'][data-openwaifu-bili-file-input='1']",
        *BILIBILI_FILE_INPUT_SELECTORS,
    ]
    for click_upload in (_click_bilibili_upload_add, _click_bilibili_upload_tool):
        try:
            click_upload(page)
        except Exception:
            pass
        captured = _bilibili_file_input_capture_seen(page)
        if captured and _set_bilibili_captured_file_input(page, image_path):
            return {
                "uploaded": True,
                "chooserFallbackUsed": True,
                "uploadMethod": "captured_detached_input",
                "fileInputCaptured": True,
                "captureInstallCount": capture_install_count,
                "uploadDomDebug": _bilibili_upload_dom_debug(page),
            }
        if set_file_input_candidates(page, captured_selectors, image_path):
            return {
                "uploaded": True,
                "chooserFallbackUsed": True,
                "uploadMethod": "captured_input",
                "fileInputCaptured": captured,
                "captureInstallCount": capture_install_count,
                "uploadDomDebug": _bilibili_upload_dom_debug(page),
            }
    if allow_native_file_chooser and set_file_with_chooser(page, image_path, lambda: _click_bilibili_upload_add(page)):
        return {
            "uploaded": True,
            "chooserFallbackUsed": True,
            "uploadMethod": "file_chooser",
            "fileInputCaptured": _bilibili_file_input_capture_seen(page),
            "captureInstallCount": capture_install_count,
            "uploadDomDebug": _bilibili_upload_dom_debug(page),
        }
    if _bilibili_image_upload_state(page).get("pickerOpen"):
        _dismiss_bilibili_image_picker(page)
    return {
        "uploaded": False,
        "chooserFallbackUsed": True,
        "uploadMethod": "captured_input_failed",
        "fileInputCaptured": _bilibili_file_input_capture_seen(page),
        "captureInstallCount": capture_install_count,
        "uploadDomDebug": _bilibili_upload_dom_debug(page),
    }


def _wait_for_bilibili_image_preview(page) -> bool:
    committed, _state = _wait_for_bilibili_image_upload_commit(page)
    return committed


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


def _read_bilibili_editor_text(page) -> str:
    script = """
    (selectors) => {
      const visible = (element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width > 1
          && rect.height > 1
          && rect.bottom > 0
          && rect.right > 0
          && rect.top < window.innerHeight
          && rect.left < window.innerWidth
          && style.visibility !== "hidden"
          && style.display !== "none";
      };
      for (const selector of selectors) {
        const element = Array.from(document.querySelectorAll(selector)).find(visible);
        if (!element) continue;
        if ("value" in element) return element.value || "";
        return element.innerText || element.textContent || "";
      }
      return "";
    }
    """
    try:
        return str(page.evaluate(script, BILIBILI_EDITOR_SELECTORS) or "")
    except Exception:
        return ""


def _clear_bilibili_editor(page) -> bool:
    script = """
    (selectors) => {
      const visible = (element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width > 1
          && rect.height > 1
          && rect.bottom > 0
          && rect.right > 0
          && rect.top < window.innerHeight
          && rect.left < window.innerWidth
          && style.visibility !== "hidden"
          && style.display !== "none";
      };
      for (const selector of selectors) {
        const element = Array.from(document.querySelectorAll(selector)).find(visible);
        if (!element) continue;
        element.focus();
        const tag = String(element.tagName || "").toLowerCase();
        if (tag === "textarea" || tag === "input") {
          const proto = tag === "textarea" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
          if (setter) setter.call(element, "");
          else element.value = "";
          element.dispatchEvent(new InputEvent("input", { bubbles: true, composed: true, inputType: "deleteContentBackward" }));
          element.dispatchEvent(new Event("change", { bubbles: true }));
          return true;
        }
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(element);
        selection.removeAllRanges();
        selection.addRange(range);
        document.execCommand("delete", false);
        element.dispatchEvent(new InputEvent("input", { bubbles: true, composed: true, inputType: "deleteContentBackward" }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
      return false;
    }
    """
    try:
        return bool(page.evaluate(script, BILIBILI_EDITOR_SELECTORS))
    except Exception:
        return False


def _wait_for_bilibili_caption_commit(page, required_fragments: list[str], *, timeout_rounds: int = 16) -> tuple[bool, str]:
    last_text = ""
    stable_hits = 0
    for _ in range(max(int(timeout_rounds), 1)):
        current_text = _read_bilibili_editor_text(page)
        if current_text:
            last_text = current_text
        if _text_contains_fragments(current_text, required_fragments):
            stable_hits += 1
            if stable_hits >= 2:
                return True, current_text
        else:
            stable_hits = 0
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
    return False, last_text


def _bilibili_image_upload_state(page) -> dict:
    script = """
    ({ successSelectors, busySelectors, errorSelectors, pickerLabels }) => {
      const visible = (element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return rect.width > 1
          && rect.height > 1
          && rect.bottom > 0
          && rect.right > 0
          && rect.top < window.innerHeight
          && rect.left < window.innerWidth
          && style.visibility !== "hidden"
          && style.display !== "none";
      };
      const hasImageSource = (element) => {
        if (element.tagName && element.tagName.toLowerCase() === "img") {
          return Boolean(element.getAttribute("src") || element.currentSrc);
        }
        if (element.querySelector("img[src]")) return true;
        const background = window.getComputedStyle(element).backgroundImage || "";
        return Boolean(background && background !== "none");
      };
      const countVisible = (selectors, { requireImageSource = false } = {}) => {
        const seen = new Set();
        let count = 0;
        for (const selector of selectors) {
          for (const element of Array.from(document.querySelectorAll(selector))) {
            if (seen.has(element) || !visible(element)) continue;
            if (requireImageSource && !hasImageSource(element)) continue;
            seen.add(element);
            count += 1;
          }
        }
        return count;
      };
      const normalize = (value) => String(value || "").replace(/\\s+/g, "");
      const pickerWanted = pickerLabels.map(normalize).filter(Boolean);
      const modalSelector = ".bili-popup-modal,.bili-modal,.bili-dialog,[class*='popup'],[class*='modal'],[class*='dialog'],[role='dialog']";
      const pickerOpen = Array.from(document.querySelectorAll(modalSelector)).some((element) => {
        if (!visible(element)) return false;
        if (element.closest(".bili-dyn-publishing")) return false;
        const text = normalize(element.innerText || element.textContent || "");
        return pickerWanted.some((label) => text.includes(label));
      });
      return {
        successCount: countVisible(successSelectors, { requireImageSource: true }),
        busyCount: countVisible(busySelectors),
        errorCount: countVisible(errorSelectors),
        pickerOpen,
      };
    }
    """
    empty_state = {"successCount": 0, "busyCount": 0, "errorCount": 0, "pickerOpen": False}
    try:
        state = page.evaluate(
            script,
            {
                "successSelectors": BILIBILI_IMAGE_SUCCESS_SELECTORS,
                "busySelectors": BILIBILI_IMAGE_UPLOAD_BUSY_SELECTORS,
                "errorSelectors": BILIBILI_IMAGE_UPLOAD_ERROR_SELECTORS,
                "pickerLabels": BILIBILI_IMAGE_PICKER_LABELS,
            },
        )
    except Exception:
        return empty_state
    if not isinstance(state, dict):
        return empty_state
    return {
        "successCount": int(state.get("successCount", 0) or 0),
        "busyCount": int(state.get("busyCount", 0) or 0),
        "errorCount": int(state.get("errorCount", 0) or 0),
        "pickerOpen": bool(state.get("pickerOpen", False)),
    }


def _wait_for_bilibili_image_upload_commit(page, *, timeout_rounds: int = 90) -> tuple[bool, dict]:
    last_state = {"successCount": 0, "busyCount": 0, "errorCount": 0, "pickerOpen": False}
    stable_hits = 0
    for _ in range(max(int(timeout_rounds), 1)):
        last_state = _bilibili_image_upload_state(page)
        if (
            last_state["successCount"] > 0
            and last_state["busyCount"] == 0
            and last_state["errorCount"] == 0
            and not last_state["pickerOpen"]
        ):
            stable_hits += 1
            if stable_hits >= 2:
                return True, last_state
        else:
            stable_hits = 0
            if last_state["errorCount"] > 0 or last_state["pickerOpen"]:
                return False, last_state
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
    return False, last_state


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
    close_browser_on_exit = not should_keep_browser_open(target_config)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=45000)
        dismiss_common_popups(page)
        logged_out = _looks_logged_out(page)
        if logged_out:
            close_browser_on_exit = False
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
        editor_cleared_before_fill = _clear_bilibili_editor(page) if editor_ready else False
        caption_text = _append_tags(_dynamic_caption(publish_input, target_config), publish_tags(publish_input, target_config))
        required_caption_fragments = _caption_required_fragments(publish_input, caption_text)
        caption_filled, caption_editor_text = fill_first_editor_verified(
            page,
            BILIBILI_EDITOR_SELECTORS,
            caption_text,
            required_fragments=required_caption_fragments,
        )
        existing_images_cleared = _clear_bilibili_existing_images(page)
        stale_image_count = _bilibili_image_preview_count(page)
        chooser_fallback_allowed = bool(target_config.get("allowFileChooserFallback", True))
        upload_result = _set_bilibili_image_file(
            page,
            image_path,
            allow_file_chooser=chooser_fallback_allowed,
            allow_native_file_chooser=bool(target_config.get("allowNativeFileChooserFallback", False)),
        )
        uploaded = bool(upload_result.get("uploaded", False))
        chooser_fallback_used = bool(upload_result.get("chooserFallbackUsed", False))
        upload_method = str(upload_result.get("uploadMethod", "") or "")
        file_input_captured = bool(upload_result.get("fileInputCaptured", False))
        capture_install_count = int(upload_result.get("captureInstallCount", 0) or 0)
        upload_dom_debug = upload_result.get("uploadDomDebug", {})
        image_preview_ready, image_upload_state = (
            _wait_for_bilibili_image_upload_commit(page)
            if uploaded and stale_image_count == 0
            else (False, _bilibili_image_upload_state(page))
        )
        image_preview_count = int(image_upload_state.get("successCount", 0) or 0)
        caption_committed, committed_caption_text = (
            _wait_for_bilibili_caption_commit(page, required_caption_fragments)
            if caption_filled
            else (False, caption_editor_text)
        )
        if committed_caption_text:
            caption_editor_text = committed_caption_text
        submit_ready = _bilibili_submit_ready(page) if caption_committed and image_preview_ready else False
        publish_ready = caption_committed and image_preview_ready and submit_ready

        submit_clicked = False
        submit_confirmed = False
        confirmations_clicked = 0
        if bool(target_config.get("autoSubmit", True)) and publish_ready:
            submit_clicked = _click_bilibili_submit(page)
            if submit_clicked:
                submit_confirmed, confirmations_clicked = _wait_for_bilibili_publish_result(page)
        trust_submit_click = bool(target_config.get("trustSubmitClick", False))
        status = "published" if submit_clicked and (submit_confirmed or trust_submit_click) else "draft_prepared"
        error = ""
        if not editor_ready or not caption_filled:
            status = "draft_needs_attention"
            error = "Bilibili 动态正文没有写入平台编辑器，已停止自动发布。"
        elif not caption_committed:
            status = "draft_needs_attention"
            error = "Bilibili 动态正文没有稳定保留在平台编辑器内，已停止自动发布。"
        elif not uploaded:
            status = "draft_needs_attention"
            if chooser_fallback_allowed:
                error = "Bilibili 动态页面没有接收图片文件，请人工检查上传控件。"
            else:
                error = "Bilibili 动态页面没有可直接写入的图片上传控件，已停止自动发布。"
        elif stale_image_count > 0:
            status = "draft_needs_attention"
            error = "Bilibili 动态编辑器里有旧图片没有清理掉，已停止自动发布。"
        elif image_upload_state.get("pickerOpen"):
            status = "draft_needs_attention"
            error = "Bilibili 图片选择弹层仍在打开，图片没有进入可发布状态，已停止自动发布。"
        elif image_upload_state.get("errorCount"):
            status = "draft_needs_attention"
            error = "Bilibili 图片上传区域出现失败或重试状态，已停止自动发布。"
        elif image_upload_state.get("busyCount"):
            status = "draft_needs_attention"
            error = "Bilibili 图片仍在上传处理中，已停止自动发布。"
        elif not image_preview_ready:
            status = "draft_needs_attention"
            error = "Bilibili 图片文件已提交给页面，但没有检测到稳定成功的图片预览，已停止自动发布。"
        elif bool(target_config.get("autoSubmit", True)) and not submit_clicked:
            status = "draft_needs_attention"
            error = "Bilibili 动态图文已写入，但发布按钮没有进入可用状态，已停止自动发布。"
        elif bool(target_config.get("autoSubmit", True)) and submit_clicked and not submit_confirmed and not trust_submit_click:
            status = "draft_needs_attention"
            error = "Bilibili 发布按钮已点击，但没有检测到成功状态，请人工确认平台结果。"
        draft_cleared_on_failure = False
        draft_images_cleared_on_failure = 0
        if (
            status == "draft_needs_attention"
            and bool(target_config.get("autoSubmit", True))
            and not should_keep_browser_open(target_config)
        ):
            close_browser_on_exit = False
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
            "imageUploadBusyCount": int(image_upload_state.get("busyCount", 0) or 0),
            "imageUploadErrorCount": int(image_upload_state.get("errorCount", 0) or 0),
            "imagePickerOpen": bool(image_upload_state.get("pickerOpen", False)),
            "existingImagesCleared": existing_images_cleared,
            "editorClearedBeforeFill": editor_cleared_before_fill,
            "draftClearedOnFailure": draft_cleared_on_failure,
            "draftImagesClearedOnFailure": draft_images_cleared_on_failure,
            "captionCommitted": caption_committed,
            "chooserFallbackAllowed": chooser_fallback_allowed,
            "chooserFallbackUsed": chooser_fallback_used,
            "uploadMethod": upload_method,
            "fileInputCaptured": file_input_captured,
            "captureInstallCount": capture_install_count,
            "uploadDomDebug": upload_dom_debug if isinstance(upload_dom_debug, dict) else {},
            "submitReady": submit_ready,
            "publishReady": publish_ready,
            "submitClicked": submit_clicked,
            "submitConfirmed": submit_confirmed,
            "confirmationsClicked": confirmations_clicked,
            "autoSubmit": bool(target_config.get("autoSubmit", True)),
            "trustSubmitClick": trust_submit_click,
            "loggedOut": logged_out,
            "error": error,
        }
    finally:
        session.disconnect(close_browser=close_browser_on_exit)
