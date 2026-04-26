from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .browser_session import DEFAULT_BROWSER_TIMEOUT_MS, SHORT_ACTION_TIMEOUT_MS


def set_file_input(page: Any, image_path: Path) -> bool:
    return set_file_input_candidates(page, ["input[type='file']"], image_path)


def _page_roots(page: Any) -> list[Any]:
    roots = [page]
    try:
        roots.extend(page.frames)
    except Exception:
        pass
    return roots


def _locator_count(locator: Any) -> int:
    try:
        return int(locator.count())
    except Exception:
        return 0


def _first_visible_locator(root: Any, selectors: list[str], *, timeout_ms: int = 1000) -> Any | None:
    for selector in selectors:
        try:
            locator = root.locator(selector).first
            if _locator_count(locator) <= 0:
                continue
            try:
                if not locator.is_visible(timeout=timeout_ms):
                    continue
            except Exception:
                pass
            return locator
        except Exception:
            continue
    return None


def set_file_input_candidates(page: Any, selectors: list[str], image_path: Path) -> bool:
    for root in _page_roots(page):
        for selector in selectors:
            try:
                locator = root.locator(selector).first
                if _locator_count(locator) <= 0:
                    continue
                locator.set_input_files(str(image_path), timeout=DEFAULT_BROWSER_TIMEOUT_MS)
                return True
            except Exception:
                continue
    return False


def fill_first_locator(page: Any, selectors: list[str], value: str) -> bool:
    if not value:
        return False
    for root in _page_roots(page):
        if fill_first_locator_in_root(root, selectors, value):
            return True
    return False


def fill_first_locator_in_root(root: Any, selectors: list[str], value: str) -> bool:
    for selector in selectors:
        try:
            locator = root.locator(selector).first
            if _locator_count(locator) <= 0:
                continue
            locator.fill(value, timeout=SHORT_ACTION_TIMEOUT_MS)
            return True
        except Exception:
            continue
    return False


def fill_first_editor(page: Any, selectors: list[str], value: str) -> bool:
    if not value:
        return False
    for root in _page_roots(page):
        locator = _first_visible_locator(root, selectors)
        if locator is None:
            continue
        try:
            locator.fill(value, timeout=SHORT_ACTION_TIMEOUT_MS)
            return True
        except Exception:
            pass
        try:
            locator.click(timeout=SHORT_ACTION_TIMEOUT_MS)
            page.keyboard.press("Control+A")
            page.keyboard.insert_text(value)
            return True
        except Exception:
            continue
    return False


def normalize_editor_text(value: str) -> str:
    return "".join(ch for ch in str(value or "") if not ch.isspace() and ch != "\u200b")


def _read_locator_edit_text(locator: Any) -> str:
    try:
        return str(
            locator.evaluate(
                """
                (element) => {
                  if ("value" in element) return element.value || "";
                  return element.innerText || element.textContent || "";
                }
                """
            )
        )
    except Exception:
        try:
            return str(locator.inner_text(timeout=1000))
        except Exception:
            return ""


def _editor_contains_fragments(text: str, fragments: list[str]) -> bool:
    normalized_text = normalize_editor_text(text)
    normalized_fragments = [normalize_editor_text(fragment) for fragment in fragments if normalize_editor_text(fragment)]
    if not normalized_fragments:
        return bool(normalized_text)
    return all(fragment in normalized_text for fragment in normalized_fragments)


def _set_editable_value_with_events(locator: Any, value: str) -> None:
    locator.evaluate(
        """
        (element, value) => {
          element.focus();
          const tag = element.tagName.toLowerCase();
          if (tag === "textarea" || tag === "input") {
            const proto = tag === "textarea" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
            if (setter) setter.call(element, value);
            else element.value = value;
            element.dispatchEvent(new InputEvent("input", { bubbles: true, composed: true, data: value, inputType: "insertText" }));
            element.dispatchEvent(new Event("change", { bubbles: true }));
            return;
          }
          const selection = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(element);
          selection.removeAllRanges();
          selection.addRange(range);
          document.execCommand("delete", false);
          document.execCommand("insertText", false, value);
          element.dispatchEvent(new InputEvent("input", { bubbles: true, composed: true, data: value, inputType: "insertText" }));
        }
        """,
        value,
    )


def fill_first_editor_verified(
    page: Any,
    selectors: list[str],
    value: str,
    *,
    required_fragments: list[str] | None = None,
    timeout_ms: int = 8000,
) -> tuple[bool, str]:
    if not value:
        return False, ""
    fragments = required_fragments if required_fragments is not None else [value]
    for root in _page_roots(page):
        locator = _first_visible_locator(root, selectors)
        if locator is None:
            continue
        for attempt in ("keyboard", "events", "fill"):
            try:
                locator.click(timeout=SHORT_ACTION_TIMEOUT_MS)
                if attempt == "keyboard":
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.insert_text(value)
                elif attempt == "events":
                    _set_editable_value_with_events(locator, value)
                else:
                    locator.fill(value, timeout=SHORT_ACTION_TIMEOUT_MS)
            except Exception:
                continue
            deadline = time.monotonic() + timeout_ms / 1000
            while time.monotonic() < deadline:
                current_text = _read_locator_edit_text(locator)
                if _editor_contains_fragments(current_text, fragments):
                    return True, current_text
                time.sleep(0.2)
        current_text = _read_locator_edit_text(locator)
        if _editor_contains_fragments(current_text, fragments):
            return True, current_text
    return False, ""


def click_text_candidates(page: Any, labels: list[str], timeout_ms: int = 5000) -> bool:
    for root in _page_roots(page):
        if click_text_candidates_in_root(root, labels, timeout_ms=timeout_ms):
            return True
    return False


def click_text_candidates_in_root(root: Any, labels: list[str], timeout_ms: int = 5000) -> bool:
    for label in labels:
        try:
            root.get_by_role("button", name=label, exact=False).first.click(timeout=timeout_ms)
            return True
        except Exception:
            pass
        try:
            root.get_by_text(label, exact=False).first.click(timeout=timeout_ms)
            return True
        except Exception:
            continue
    return False


def click_locator_candidates(page: Any, selectors: list[str], timeout_ms: int = 5000) -> bool:
    for root in _page_roots(page):
        for selector in selectors:
            try:
                locator = root.locator(selector).first
                if _locator_count(locator) <= 0:
                    continue
                locator.click(timeout=timeout_ms)
                return True
            except Exception:
                continue
    return False


def click_visible_text_candidates(
    page: Any,
    labels: list[str],
    *,
    timeout_ms: int = 5000,
    scope_selector: str = "a,button,[role='button']",
) -> bool:
    script = """
    ({ labels, scopeSelector }) => {
      const normalize = (value) => String(value || "").replace(/\\s+/g, "");
      const wanted = labels.map(normalize).filter(Boolean);
      const selector = scopeSelector || "a,button,[role='button']";
      const candidates = Array.from(document.querySelectorAll(selector));
      const matches = [];
      for (const element of candidates) {
        const text = normalize(element.innerText || element.textContent || element.getAttribute("aria-label") || element.title || "");
        if (!text) continue;
        const rect = element.getBoundingClientRect();
        if (rect.width < 2 || rect.height < 2 || rect.bottom < 0 || rect.right < 0 || rect.top > window.innerHeight || rect.left > window.innerWidth) {
          continue;
        }
        const label = wanted.find((item) => text.includes(item));
        if (!label) continue;
        matches.push({
          element,
          score: (text === label ? 1000 : 0) - Math.abs(text.length - label.length),
        });
      }
      matches.sort((left, right) => right.score - left.score);
      const picked = matches[0]?.element;
      if (!picked) return false;
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
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for root in _page_roots(page):
            try:
                if root.evaluate(script, {"labels": labels, "scopeSelector": scope_selector}):
                    return True
            except Exception:
                continue
        time.sleep(0.2)
    return False


def has_visible_text_candidates(
    page: Any,
    labels: list[str],
    *,
    timeout_ms: int = 5000,
    scope_selector: str = "a,button,[role='button']",
) -> bool:
    script = """
    ({ labels, scopeSelector }) => {
      const normalize = (value) => String(value || "").replace(/\\s+/g, "");
      const wanted = labels.map(normalize).filter(Boolean);
      const selector = scopeSelector || "a,button,[role='button']";
      return Array.from(document.querySelectorAll(selector)).some((element) => {
        const text = normalize(element.innerText || element.textContent || element.getAttribute("aria-label") || element.title || "");
        if (!text) return false;
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        if (rect.width < 2 || rect.height < 2 || rect.bottom < 0 || rect.right < 0 || rect.top > window.innerHeight || rect.left > window.innerWidth) {
          return false;
        }
        if (style.visibility === "hidden" || style.display === "none") {
          return false;
        }
        return wanted.some((item) => text.includes(item));
      });
    }
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for root in _page_roots(page):
            try:
                if root.evaluate(script, {"labels": labels, "scopeSelector": scope_selector}):
                    return True
            except Exception:
                continue
        time.sleep(0.2)
    return False


def set_file_with_chooser(page: Any, image_path: Path, click_upload) -> bool:
    try:
        with page.expect_file_chooser(timeout=SHORT_ACTION_TIMEOUT_MS) as chooser_info:
            if not click_upload():
                return False
        chooser_info.value.set_files(str(image_path))
        return True
    except Exception:
        return False


def page_visible_text(page: Any, *, limit: int = 4000) -> str:
    chunks: list[str] = []
    for root in _page_roots(page):
        try:
            text = root.locator("body").evaluate("(element) => (element.innerText || element.textContent || '')")
            if text:
                chunks.append(str(text))
        except Exception:
            continue
    return " ".join(chunks)[:limit]


def dismiss_common_popups(page: Any) -> None:
    for labels in (
        ["Not now", "稍后", "以后再说", "暂不", "取消"],
        ["Accept all", "Allow all cookies", "接受全部", "同意"],
    ):
        click_visible_text_candidates(page, labels, timeout_ms=800)


def wait_for_any_locator(page: Any, selectors: list[str], *, timeout_ms: int = 15000, visible: bool = True) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for root in _page_roots(page):
            if visible:
                if _first_visible_locator(root, selectors, timeout_ms=300) is not None:
                    return True
            else:
                for selector in selectors:
                    try:
                        if _locator_count(root.locator(selector).first) > 0:
                            return True
                    except Exception:
                        continue
        time.sleep(0.2)
    return False
