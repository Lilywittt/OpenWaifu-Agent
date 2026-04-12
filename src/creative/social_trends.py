from __future__ import annotations

import html
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from io_utils import normalize_spaces, read_json, unique_list, write_json


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_TEXT_SIGNAL_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
_ALPHA_SIGNAL_RE = re.compile(r"[A-Za-z\u4e00-\u9fff]")
_BILIBILI_DESC_NOISE_RE = re.compile(r"(?:[#＃]\s*\d{1,3}|第?\s*\d{1,3}\s*(?:话|集|期)|ep\.?\s*\d{1,3})", re.I)
_SOURCE_BACKOFF_WINDOW = timedelta(hours=6)
_PARTITION_BACKOFF_WINDOW = timedelta(hours=2)
_SOCIAL_SIGNAL_SHORTLIST_SIZE = 3
_DEFAULT_HTTP_TIMEOUT_SECONDS = 10
_REDDIT_HTTP_TIMEOUT_SECONDS = 6
_REDDIT_COMMENT_HTTP_TIMEOUT_SECONDS = 3
_COMMENT_HTTP_TIMEOUT_SECONDS = 2
_REDDIT_TARGET_CANDIDATE_COUNT = _SOCIAL_SIGNAL_SHORTLIST_SIZE
_REDDIT_COMMENT_FALLBACK_LIMIT = 0
_BILIBILI_TARGET_CANDIDATE_COUNT = _SOCIAL_SIGNAL_SHORTLIST_SIZE
_BILIBILI_COMMENT_FALLBACK_LIMIT = 2
_BLUESKY_FEED_CACHE_WINDOW = timedelta(minutes=30)
_RANDOM = random.SystemRandom()
_BLUESKY_FEED_CACHE: dict[str, Any] = {
    "loadedAt": None,
    "feeds": [],
}

@dataclass(frozen=True)
class SocialPartition:
    source_key: str
    source_zh: str
    provider_key: str
    provider_zh: str
    weight: float
    collector: Callable[[], list[str]]


def _strip_html(raw: str) -> str:
    text = html.unescape(str(raw or ""))
    text = _HTML_TAG_RE.sub(" ", text)
    return normalize_spaces(_WHITESPACE_RE.sub(" ", text))


def _trim(text: str, limit: int = 260) -> str:
    cleaned = normalize_spaces(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _parse_iso_datetime(raw: str) -> datetime | None:
    cleaned = normalize_spaces(raw)
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _is_low_signal_bilibili_desc(text: str) -> bool:
    cleaned = normalize_spaces(text)
    if not cleaned or cleaned == "-":
        return True
    stripped = _BILIBILI_DESC_NOISE_RE.sub(" ", cleaned)
    return len(_ALPHA_SIGNAL_RE.findall(stripped)) < 4


def _should_backoff_source(source_key: str, error: str) -> bool:
    lowered = normalize_spaces(error).casefold()
    timed_out = "timeout" in lowered or "timed out" in lowered or "transport error" in lowered
    if source_key == "reddit":
        return timed_out or "http 403" in lowered or "http 429" in lowered or "blocked" in lowered or "forbidden" in lowered
    if source_key == "bilibili":
        return timed_out
    return False


def _should_backoff_partition(partition: SocialPartition, error: str) -> bool:
    lowered = normalize_spaces(error).casefold()
    if "timeout" in lowered or "timed out" in lowered or "transport error" in lowered:
        return True
    if partition.source_key == "reddit" and "http 429" in lowered:
        return True
    if partition.source_key == "bilibili" and "not enough items" in lowered:
        return True
    if partition.source_key == "bluesky" and any(code in lowered for code in ("http 500", "http 502", "http 503", "http 504")):
        return True
    return False


def _fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = _DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> Any:
    merged_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ig-roleplay-v3",
        "Accept": "application/json",
    }
    if headers:
        merged_headers.update(headers)
    request = Request(url, headers=merged_headers, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error
    except (URLError, OSError) as error:
        try:
            opener = build_opener(ProxyHandler({}))
            with opener.open(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as retry_error:
            detail = retry_error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {retry_error.code}: {detail}") from retry_error
        except (URLError, OSError):
            pass
        raise RuntimeError(f"transport error: {error}") from error


def _fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = _DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> str:
    merged_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ig-roleplay-v3",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if headers:
        merged_headers.update(headers)
    request = Request(url, headers=merged_headers, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error
    except (URLError, OSError) as error:
        try:
            opener = build_opener(ProxyHandler({}))
            with opener.open(request, timeout=timeout_seconds) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as retry_error:
            detail = retry_error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {retry_error.code}: {detail}") from retry_error
        except (URLError, OSError):
            pass
        raise RuntimeError(f"transport error: {error}") from error


def _fetch_reddit_posts(subreddit: str) -> list[dict[str, str]]:
    payload = _fetch_json(
        f"https://www.reddit.com/r/{subreddit}/hot.json?limit=20&raw_json=1",
        timeout_seconds=_REDDIT_HTTP_TIMEOUT_SECONDS,
    )
    items: list[dict[str, str]] = []
    for child in payload.get("data", {}).get("children", [])[:20]:
        data = child.get("data", {})
        if data.get("stickied") or data.get("pinned"):
            continue
        title = normalize_spaces(str(data.get("title", "")))
        body = _trim(normalize_spaces(str(data.get("selftext", ""))), 1200)
        lowered = f"{title} {body}".casefold()
        if data.get("distinguished") == "moderator":
            continue
        if any(
            token in lowered
            for token in (
                "moderator applications",
                "new post flair",
                "official question thread",
                "daily simple questions",
                "discord server",
                "read our rules",
            )
        ):
            continue
        items.append(
            {
                "subreddit": normalize_spaces(str(data.get("subreddit_name_prefixed", ""))),
                "title": title,
                "body": body,
                "permalink": normalize_spaces(str(data.get("permalink", ""))),
            }
        )
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        key = "|".join([item.get("subreddit", ""), item.get("title", ""), item.get("permalink", "")]).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _fetch_reddit_comment_bodies(permalink: str) -> list[str]:
    if not permalink:
        return []
    payload = _fetch_json(
        f"https://www.reddit.com{permalink}.json?limit=5&depth=1&sort=top&raw_json=1",
        timeout_seconds=_REDDIT_COMMENT_HTTP_TIMEOUT_SECONDS,
    )
    if not isinstance(payload, list) or len(payload) < 2:
        return []
    comments = payload[1].get("data", {}).get("children", [])
    bodies: list[str] = []
    for comment in comments:
        data = comment.get("data", {})
        body = _trim(normalize_spaces(str(data.get("body", ""))), 300)
        lowered = body.casefold()
        if any(
            token in lowered
            for token in (
                "moderator applications",
                "read more [here]",
                "direct link",
                "read our rules",
            )
        ):
            continue
        if body and body not in bodies:
            bodies.append(body)
        if len(bodies) >= 2:
            break
    return bodies


def _render_reddit_signal(item: dict[str, str], *, allow_comment_fallback: bool = True) -> str:
    subreddit = item.get("subreddit", "")
    title = item.get("title", "")
    body = item.get("body", "")
    if not body and allow_comment_fallback:
        comment_bodies = _fetch_reddit_comment_bodies(item.get("permalink", ""))
        if comment_bodies:
            body = " ".join(comment_bodies)
    parts = [part for part in (subreddit, title, body) if part]
    return " | ".join(parts)


def _collect_reddit_partition(subreddit: str) -> list[str]:
    posts = _fetch_reddit_posts(subreddit)
    rendered: list[str] = []
    comment_fallbacks_used = 0
    for item in posts:
        allow_comment_fallback = comment_fallbacks_used < _REDDIT_COMMENT_FALLBACK_LIMIT
        if not normalize_spaces(item.get("body", "")) and allow_comment_fallback:
            comment_fallbacks_used += 1
        signal = _render_reddit_signal(item, allow_comment_fallback=allow_comment_fallback)
        if signal:
            rendered.append(signal)
        deduped = unique_list(rendered)
        if len(deduped) >= _REDDIT_TARGET_CANDIDATE_COUNT:
            return deduped
    return unique_list(rendered)


def _list_bluesky_feeds() -> list[dict[str, str]]:
    cached_at = _BLUESKY_FEED_CACHE.get("loadedAt")
    cached_feeds = _BLUESKY_FEED_CACHE.get("feeds", [])
    if isinstance(cached_at, datetime) and datetime.now() - cached_at < _BLUESKY_FEED_CACHE_WINDOW and cached_feeds:
        return [dict(item) for item in cached_feeds]
    try:
        payload = _fetch_json("https://api.bsky.app/xrpc/app.bsky.unspecced.getPopularFeedGenerators?limit=30")
    except Exception:
        if cached_feeds:
            return [dict(item) for item in cached_feeds]
        raise
    feeds = payload.get("feeds", [])
    items: list[dict[str, str]] = []
    for item in feeds:
        uri = normalize_spaces(str(item.get("uri", "")))
        display_name = normalize_spaces(str(item.get("displayName", "")))
        description = _trim(normalize_spaces(str(item.get("description", ""))), 240)
        if uri and display_name:
            items.append(
                {
                    "uri": uri,
                    "display_name": display_name,
                    "description": description,
                }
            )
    _BLUESKY_FEED_CACHE["loadedAt"] = datetime.now()
    _BLUESKY_FEED_CACHE["feeds"] = [dict(item) for item in items]
    return items


def _render_bluesky_post(item: dict[str, Any]) -> str:
    post = item.get("post", {})
    author = post.get("author", {})
    record = post.get("record", {})
    display_name = normalize_spaces(str(author.get("displayName") or author.get("handle") or ""))
    text = _trim(normalize_spaces(str(record.get("text", ""))), 900)
    lowered = text.casefold()
    if (
        "welcome to the" in lowered
        or "pinned post" in lowered
        or "open this thread" in lowered
        or "photo credits & permissions" in lowered
    ):
        return ""
    if len(_TEXT_SIGNAL_RE.findall(text)) < 10:
        return ""

    extras: list[str] = []
    embed = post.get("embed", {})
    if "external" in embed:
        external = embed.get("external", {})
        title = normalize_spaces(str(external.get("title", "")))
        description = _trim(normalize_spaces(str(external.get("description", ""))), 220)
        extras.extend(part for part in (title, description) if part)
    elif "images" in embed:
        alts = []
        for image in embed.get("images", [])[:2]:
            alt = _trim(normalize_spaces(str(image.get("alt", ""))), 140)
            if alt:
                alts.append(alt)
        extras.extend(alts)

    parts = [part for part in (display_name, text, *extras) if part]
    if len(normalize_spaces(" ".join(parts))) < 32:
        return ""
    return " | ".join(parts)


def _collect_bluesky_feed(feed_uri: str) -> list[str]:
    url = "https://api.bsky.app/xrpc/app.bsky.feed.getFeed?limit=20&feed=" + quote(feed_uri, safe="")
    payload = _fetch_json(url)
    items = payload.get("feed", [])[:20]
    rendered = [_render_bluesky_post(item) for item in items]
    return unique_list([item for item in rendered if normalize_spaces(item)])


def _collect_bilibili_region(rid: int) -> list[dict[str, str]]:
    payload = _fetch_json(
        f"https://api.bilibili.com/x/web-interface/ranking/region?rid={rid}&day=3",
        headers={"Referer": "https://www.bilibili.com/"},
    )
    items: list[dict[str, str]] = []
    for data in (payload.get("data") or [])[:20]:
        items.append(
            {
                "aid": str(data.get("aid", "")),
                "title": normalize_spaces(str(data.get("title", ""))),
                "desc": _trim(
                    normalize_spaces(
                        str(data.get("description", "") or data.get("desc", "") or data.get("subtitle", ""))
                    ),
                    500,
                ),
                "tname": normalize_spaces(str(data.get("typename", "") or data.get("tname", ""))),
                "pub_location": normalize_spaces(str(data.get("pub_location", ""))),
            }
        )
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        key = "|".join([item.get("aid", ""), item.get("title", "")]).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _fetch_bilibili_comment_bodies(aid: str) -> list[str]:
    if not aid:
        return []
    payload = _fetch_json(
        f"https://api.bilibili.com/x/v2/reply?pn=1&type=1&oid={aid}&sort=2",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        },
        timeout_seconds=_COMMENT_HTTP_TIMEOUT_SECONDS,
    )
    replies = payload.get("data", {}).get("replies", []) or []
    bodies: list[str] = []
    for reply in replies:
        content = reply.get("content", {})
        body = _trim(normalize_spaces(str(content.get("message", ""))), 240)
        if body and body not in bodies:
            bodies.append(body)
        if len(bodies) >= 2:
            break
    return bodies


def _render_bilibili_signal(item: dict[str, str], *, allow_comment_fallback: bool = True) -> str:
    desc = item.get("desc", "")
    if _is_low_signal_bilibili_desc(desc):
        desc = ""
    if not desc and allow_comment_fallback:
        comment_bodies = _fetch_bilibili_comment_bodies(item.get("aid", ""))
        if comment_bodies:
            desc = " ".join(comment_bodies)
    if not desc:
        return ""
    parts = [
        part
        for part in (
            item.get("tname", ""),
            item.get("pub_location", ""),
            item.get("title", ""),
            desc,
        )
        if part
    ]
    return " | ".join(parts)


def _collect_bilibili_partition(rid: int) -> list[str]:
    posts = _collect_bilibili_region(rid)
    rendered: list[str] = []
    comment_fallbacks_used = 0
    for item in posts:
        allow_comment_fallback = comment_fallbacks_used < _BILIBILI_COMMENT_FALLBACK_LIMIT
        if _is_low_signal_bilibili_desc(item.get("desc", "")) and allow_comment_fallback:
            comment_fallbacks_used += 1
        signal = _render_bilibili_signal(item, allow_comment_fallback=allow_comment_fallback)
        if signal:
            rendered.append(signal)
        deduped = unique_list(rendered)
        if len(deduped) >= _BILIBILI_TARGET_CANDIDATE_COUNT:
            return deduped
    return unique_list(rendered)


def _collect_bangumi_anime_browser() -> list[str]:
    html_text = _fetch_text("https://bgm.tv/anime/browser?sort=trends")
    blocks = re.findall(r'<li id="item_\d+".*?</li>', html_text, re.S)[:20]
    signals: list[str] = []
    for block in blocks:
        title_match = re.search(
            r'<h3>.*?<a href="/subject/\d+" class="l">(.*?)</a>(?:\s*<small class="grey">(.*?)</small>)?',
            block,
            re.S,
        )
        info_match = re.search(r'<p class="info tip">\s*(.*?)\s*</p>', block, re.S)
        rate_match = re.search(r'<p class="rateInfo">\s*(.*?)\s*</p>', block, re.S)
        if not title_match:
            continue

        title = normalize_spaces(_strip_html(title_match.group(1)))
        alt_title = ""
        if title_match.lastindex and title_match.group(2):
            alt_title = normalize_spaces(_strip_html(title_match.group(2)))
        info = _trim(normalize_spaces(_strip_html(info_match.group(1) if info_match else "")), 260)
        rate = _trim(normalize_spaces(_strip_html(rate_match.group(1) if rate_match else "")), 120)

        parts = [part for part in (title, alt_title, info, rate) if part]
        signal = " | ".join(parts)
        if signal:
            signals.append(signal)
    return unique_list(signals)


def _build_registry() -> list[SocialPartition]:
    reddit_platform_weight = 1.12
    mainstream_platform_weight = 1.0

    reddit_subreddits = [
        ("reddit_teenagers", "Reddit / teenagers", 3.6, "teenagers"),
        ("reddit_outfits", "Reddit / Outfits", 1.01, "Outfits"),
        ("reddit_streetwear", "Reddit / streetwear", 1.0, "streetwear"),
        ("reddit_food", "Reddit / food", 1.0, "food"),
        ("reddit_baking", "Reddit / Baking", 0.99, "Baking"),
        ("reddit_cozy_places", "Reddit / CozyPlaces", 0.97, "CozyPlaces"),
        ("reddit_photography", "Reddit / photography", 0.96, "photography"),
        ("reddit_mildlyinteresting", "Reddit / mildlyinteresting", 1.02, "mildlyinteresting"),
        ("reddit_askreddit", "Reddit / AskReddit", 0.95, "AskReddit"),
    ]

    registry: list[SocialPartition] = []
    for provider_key, provider_zh, partition_weight, subreddit in reddit_subreddits:
        registry.append(
            SocialPartition(
                source_key="reddit",
                source_zh="Reddit",
                provider_key=provider_key,
                provider_zh=provider_zh,
                weight=reddit_platform_weight * partition_weight,
                collector=lambda subreddit=subreddit: _collect_reddit_partition(subreddit),
            )
        )

    allowed_bluesky_feeds = {
        "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot": ("bluesky_discover", "Bluesky / Discover", 1.02),
        "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/with-friends": ("bluesky_with_friends", "Bluesky / Popular With Friends", 0.98),
        "at://did:plc:y7crv2yh74s7qhmtx3mvbgv5/app.bsky.feed.generator/art-new": ("bluesky_art", "Bluesky / Artists Trending", 1.03),
        "at://did:plc:5rw2on4i56btlcajojaxwcat/app.bsky.feed.generator/aaao6g552b33o": ("bluesky_gardening", "Bluesky / Gardening", 0.99),
        "at://did:plc:geoqe3qls5mwezckxxsewys2/app.bsky.feed.generator/aaabrbjcg4hmk": ("bluesky_booksky", "Bluesky / BookSky", 0.97),
        "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/hot-classic": ("bluesky_hot_classic", "Bluesky / What's Hot Classic", 1.0),
    }
    try:
        bluesky_feeds = _list_bluesky_feeds()
    except Exception:
        bluesky_feeds = []
    for feed in bluesky_feeds:
        uri = feed["uri"]
        if uri not in allowed_bluesky_feeds:
            continue
        provider_key, provider_zh, partition_weight = allowed_bluesky_feeds[uri]
        registry.append(
            SocialPartition(
                source_key="bluesky",
                source_zh="Bluesky",
                provider_key=provider_key,
                provider_zh=provider_zh,
                weight=mainstream_platform_weight * partition_weight,
                collector=lambda uri=uri: _collect_bluesky_feed(uri),
            )
        )

    registry.append(
        SocialPartition(
            source_key="bilibili",
            source_zh="哔哩哔哩",
            provider_key="bilibili_anime",
            provider_zh="哔哩哔哩 / 日漫分区",
            weight=2.0,
            collector=lambda: _collect_bilibili_partition(33),
        )
    )
    registry.append(
        SocialPartition(
            source_key="bangumi",
            source_zh="Bangumi",
            provider_key="bangumi_anime",
            provider_zh="Bangumi / 动画分区",
            weight=7.0,
            collector=_collect_bangumi_anime_browser,
        )
    )
    return registry


def _health_path(project_dir: Path) -> Path:
    return project_dir / "runtime" / "service_state" / "social_sampling_health.json"


def _load_health(project_dir: Path) -> dict[str, Any]:
    path = _health_path(project_dir)
    if not path.exists():
        return {"updatedAt": "", "partitions": {}, "lastSample": {}, "sourceBackoff": {}, "partitionBackoff": {}}
    health = read_json(path)
    health.setdefault("partitions", {})
    health.setdefault("lastSample", {})
    health.setdefault("sourceBackoff", {})
    health.setdefault("partitionBackoff", {})
    return health


def _save_health(project_dir: Path, health: dict[str, Any]) -> None:
    health["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(_health_path(project_dir), health)


def _active_source_backoffs(project_dir: Path) -> dict[str, str]:
    health = _load_health(project_dir)
    source_backoff = health.setdefault("sourceBackoff", {})
    active: dict[str, str] = {}
    now = datetime.now()
    changed = False
    for source_key in list(source_backoff):
        entry = source_backoff.get(source_key, {})
        blocked_until = _parse_iso_datetime(str(entry.get("blockedUntil", "")))
        if not blocked_until or blocked_until <= now:
            source_backoff.pop(source_key, None)
            changed = True
            continue
        active[source_key] = normalize_spaces(str(entry.get("lastError", ""))) or "source temporarily unavailable"
    if changed:
        _save_health(project_dir, health)
    return active


def _active_partition_backoffs(project_dir: Path) -> dict[str, str]:
    health = _load_health(project_dir)
    partition_backoff = health.setdefault("partitionBackoff", {})
    active: dict[str, str] = {}
    now = datetime.now()
    changed = False
    for provider_key in list(partition_backoff):
        entry = partition_backoff.get(provider_key, {})
        blocked_until = _parse_iso_datetime(str(entry.get("blockedUntil", "")))
        if not blocked_until or blocked_until <= now:
            partition_backoff.pop(provider_key, None)
            changed = True
            continue
        active[provider_key] = normalize_spaces(str(entry.get("lastError", ""))) or "provider temporarily unavailable"
    if changed:
        _save_health(project_dir, health)
    return active


def _set_source_backoff(project_dir: Path, source_key: str, error: str) -> None:
    health = _load_health(project_dir)
    source_backoff = health.setdefault("sourceBackoff", {})
    source_backoff[source_key] = {
        "blockedUntil": (datetime.now() + _SOURCE_BACKOFF_WINDOW).isoformat(timespec="seconds"),
        "lastError": normalize_spaces(error),
    }
    _save_health(project_dir, health)


def _set_partition_backoff(project_dir: Path, provider_key: str, error: str) -> None:
    health = _load_health(project_dir)
    partition_backoff = health.setdefault("partitionBackoff", {})
    partition_backoff[provider_key] = {
        "blockedUntil": (datetime.now() + _PARTITION_BACKOFF_WINDOW).isoformat(timespec="seconds"),
        "lastError": normalize_spaces(error),
    }
    _save_health(project_dir, health)


def _record_attempt(
    project_dir: Path,
    *,
    partition: SocialPartition,
    ok: bool,
    error: str = "",
    sampled_signals: list[str] | None = None,
    duration_ms: int = 0,
) -> None:
    health = _load_health(project_dir)
    partitions = health.setdefault("partitions", {})
    entry = partitions.setdefault(
        partition.provider_key,
        {
            "sourceKey": partition.source_key,
            "sourceZh": partition.source_zh,
            "providerKey": partition.provider_key,
            "providerZh": partition.provider_zh,
            "weight": partition.weight,
            "attemptCount": 0,
            "successCount": 0,
            "failureCount": 0,
            "consecutiveFailures": 0,
            "lastSuccessAt": "",
            "lastFailureAt": "",
            "lastError": "",
            "lastDurationMs": 0,
            "lastSamplePreviewZh": [],
        },
    )
    entry["attemptCount"] += 1
    now = datetime.now().isoformat(timespec="seconds")
    if ok:
        entry["successCount"] += 1
        entry["consecutiveFailures"] = 0
        entry["lastSuccessAt"] = now
        entry["lastError"] = ""
        entry["lastDurationMs"] = duration_ms
        entry["lastSamplePreviewZh"] = (sampled_signals or [])[:2]
        health["lastSample"] = {
            "at": now,
            "sourceKey": partition.source_key,
            "sourceZh": partition.source_zh,
            "providerKey": partition.provider_key,
            "providerZh": partition.provider_zh,
            "sampledSignalsZh": (sampled_signals or [])[:3],
        }
    else:
        entry["failureCount"] += 1
        entry["consecutiveFailures"] += 1
        entry["lastFailureAt"] = now
        entry["lastError"] = error
        entry["lastDurationMs"] = duration_ms
    _save_health(project_dir, health)


def _weighted_pick_without_replacement(partitions: list[SocialPartition]) -> list[SocialPartition]:
    pool = list(partitions)
    ordered: list[SocialPartition] = []
    while pool:
        total = sum(max(item.weight, 0.001) for item in pool)
        target = _RANDOM.random() * total
        cursor = 0.0
        picked_index = 0
        for index, item in enumerate(pool):
            cursor += max(item.weight, 0.001)
            if cursor >= target:
                picked_index = index
                break
        ordered.append(pool.pop(picked_index))
    return ordered


def collect_social_trend_sample(project_dir: Path) -> dict[str, Any]:
    registry = _build_registry()
    blocked_sources = _active_source_backoffs(project_dir)
    blocked_partitions = _active_partition_backoffs(project_dir)
    available_registry = [
        partition
        for partition in registry
        if partition.source_key not in blocked_sources and partition.provider_key not in blocked_partitions
    ]
    if available_registry:
        registry = available_registry
    failures: list[str] = []

    for partition in _weighted_pick_without_replacement(registry):
        if partition.source_key in blocked_sources or partition.provider_key in blocked_partitions:
            continue
        started_at = time.perf_counter()
        try:
            candidates = partition.collector()
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            if len(candidates) < _SOCIAL_SIGNAL_SHORTLIST_SIZE:
                raise RuntimeError("not enough items")
            sampled_signals = unique_list(_RANDOM.sample(candidates, _SOCIAL_SIGNAL_SHORTLIST_SIZE))
            if len(sampled_signals) < _SOCIAL_SIGNAL_SHORTLIST_SIZE:
                raise RuntimeError("not enough sampled items")
            _record_attempt(
                project_dir,
                partition=partition,
                ok=True,
                sampled_signals=sampled_signals,
                duration_ms=duration_ms,
            )
            return {
                "sourceKey": partition.source_key,
                "sourceZh": partition.source_zh,
                "providerKey": partition.provider_key,
                "providerZh": partition.provider_zh,
                "sampledSignalsZh": sampled_signals,
            }
        except Exception as error:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            message = str(error)
            failures.append(f"{partition.provider_key}: {message}")
            _record_attempt(project_dir, partition=partition, ok=False, error=message, duration_ms=duration_ms)
            if _should_backoff_partition(partition, message):
                blocked_partitions[partition.provider_key] = message
                _set_partition_backoff(project_dir, partition.provider_key, message)
            if _should_backoff_source(partition.source_key, message):
                blocked_sources[partition.source_key] = message
                _set_source_backoff(project_dir, partition.source_key, message)

    report_path = _health_path(project_dir)
    raise RuntimeError("社媒随机采样失败，已写入接口健康报告：" + str(report_path) + "；" + "；".join(failures))
