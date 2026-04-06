from __future__ import annotations

import html
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from io_utils import normalize_spaces, read_json, unique_list, write_json


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_TEXT_SIGNAL_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
_RANDOM = random.SystemRandom()


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


def _fetch_json(url: str, *, headers: dict[str, str] | None = None) -> Any:
    merged_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ig-roleplay-v3",
        "Accept": "application/json",
    }
    if headers:
        merged_headers.update(headers)
    request = Request(url, headers=merged_headers, method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"transport error: {error}") from error


def _fetch_reddit_posts(subreddit: str) -> list[dict[str, str]]:
    payload = _fetch_json(f"https://old.reddit.com/r/{subreddit}/hot/.json?limit=20&raw_json=1")
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
    payload = _fetch_json(f"https://old.reddit.com{permalink}.json?limit=5&depth=1&sort=top&raw_json=1")
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


def _render_reddit_signal(item: dict[str, str]) -> str:
    subreddit = item.get("subreddit", "")
    title = item.get("title", "")
    body = item.get("body", "")
    if not body:
        comment_bodies = _fetch_reddit_comment_bodies(item.get("permalink", ""))
        if comment_bodies:
            body = " ".join(comment_bodies)
    parts = [part for part in (subreddit, title, body) if part]
    return " | ".join(parts)


def _collect_reddit_partition(subreddit: str) -> list[str]:
    posts = _fetch_reddit_posts(subreddit)
    rendered = [_render_reddit_signal(item) for item in posts]
    return unique_list([item for item in rendered if normalize_spaces(item)])


def _list_bluesky_feeds() -> list[dict[str, str]]:
    payload = _fetch_json("https://api.bsky.app/xrpc/app.bsky.unspecced.getPopularFeedGenerators?limit=30")
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


def _collect_bilibili_popular() -> list[dict[str, str]]:
    payload = _fetch_json(
        "https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1",
        headers={"Referer": "https://www.bilibili.com/"},
    )
    items: list[dict[str, str]] = []
    for data in payload.get("data", {}).get("list", [])[:20]:
        items.append(
            {
                "aid": str(data.get("aid", "")),
                "title": normalize_spaces(str(data.get("title", ""))),
                "desc": _trim(normalize_spaces(str(data.get("desc", ""))), 500),
                "tname": normalize_spaces(str(data.get("tname", ""))),
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


def _render_bilibili_signal(item: dict[str, str]) -> str:
    desc = item.get("desc", "")
    if desc == "-":
        desc = ""
    if not desc:
        comment_bodies = _fetch_bilibili_comment_bodies(item.get("aid", ""))
        if comment_bodies:
            desc = " ".join(comment_bodies)
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


def _collect_bilibili_partition() -> list[str]:
    posts = _collect_bilibili_popular()
    rendered = [_render_bilibili_signal(item) for item in posts]
    return unique_list([item for item in rendered if normalize_spaces(item)])


def _build_registry() -> list[SocialPartition]:
    reddit_platform_weight = 1.12
    mainstream_platform_weight = 1.0

    reddit_subreddits = [
        ("reddit_teenagers", "Reddit / teenagers", 3.6, "teenagers"),
        ("reddit_outfits", "Reddit / Outfits", 1.03, "Outfits"),
        ("reddit_streetwear", "Reddit / streetwear", 1.01, "streetwear"),
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
    for feed in _list_bluesky_feeds():
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
            provider_key="bilibili_popular",
            provider_zh="哔哩哔哩 / 总热榜",
            weight=0.99,
            collector=_collect_bilibili_partition,
        )
    )
    return registry


def _health_path(project_dir: Path) -> Path:
    return project_dir / "runtime" / "service_state" / "social_sampling_health.json"


def _load_health(project_dir: Path) -> dict[str, Any]:
    path = _health_path(project_dir)
    if not path.exists():
        return {"updatedAt": "", "partitions": {}, "lastSample": {}}
    return read_json(path)


def _save_health(project_dir: Path, health: dict[str, Any]) -> None:
    health["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    write_json(_health_path(project_dir), health)


def _record_attempt(
    project_dir: Path,
    *,
    partition: SocialPartition,
    ok: bool,
    error: str = "",
    sampled_signals: list[str] | None = None,
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
    failures: list[str] = []

    for partition in _weighted_pick_without_replacement(registry):
        try:
            candidates = partition.collector()
            if len(candidates) < 2:
                raise RuntimeError("not enough items")
            sample_size = min(len(candidates), _RANDOM.randint(2, 3))
            sampled_signals = unique_list(_RANDOM.sample(candidates, sample_size))
            if len(sampled_signals) < 2:
                raise RuntimeError("not enough sampled items")
            _record_attempt(project_dir, partition=partition, ok=True, sampled_signals=sampled_signals)
            return {
                "sourceKey": partition.source_key,
                "sourceZh": partition.source_zh,
                "providerKey": partition.provider_key,
                "providerZh": partition.provider_zh,
                "sampledSignalsZh": sampled_signals,
            }
        except Exception as error:  # noqa: BLE001
            message = str(error)
            failures.append(f"{partition.provider_key}: {message}")
            _record_attempt(project_dir, partition=partition, ok=False, error=message)

    report_path = _health_path(project_dir)
    raise RuntimeError("社媒随机采样失败，已写入接口健康报告：" + str(report_path) + "；" + "；".join(failures))
