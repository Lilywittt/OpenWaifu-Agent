from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from creative.social_trends import (
    _BLUESKY_FEED_CACHE,
    SocialPartition,
    _BILIBILI_COMMENT_FALLBACK_LIMIT,
    _build_registry,
    _collect_bilibili_partition,
    _health_path,
    _load_health,
    _list_bluesky_feeds,
    _render_bilibili_signal,
    collect_social_trend_sample,
)
from io_utils import write_json


class SocialTrendsTests(unittest.TestCase):
    def test_bilibili_episode_marker_desc_falls_back_to_comments(self):
        item = {
            "aid": "123",
            "title": "test title",
            "desc": "#01",
            "tname": "anime",
            "pub_location": "",
        }
        with patch("creative.social_trends._fetch_bilibili_comment_bodies", return_value=["mood detail", "scene detail"]):
            signal = _render_bilibili_signal(item)
        self.assertIn("mood detail scene detail", signal)
        self.assertNotIn("#01", signal)

    def test_reddit_block_backoff_skips_remaining_reddit_partitions_in_same_run(self):
        calls = {"reddit_hot": 0, "reddit_backup": 0, "bangumi": 0}

        def reddit_hot() -> list[str]:
            calls["reddit_hot"] += 1
            raise RuntimeError("HTTP 403: Blocked")

        def reddit_backup() -> list[str]:
            calls["reddit_backup"] += 1
            return ["should not be called", "should not be called either", "still should not be called"]

        def bangumi() -> list[str]:
            calls["bangumi"] += 1
            return ["signal a", "signal b", "signal c"]

        registry = [
            SocialPartition("reddit", "Reddit", "reddit_hot", "Reddit / hot", 1.0, reddit_hot),
            SocialPartition("reddit", "Reddit", "reddit_backup", "Reddit / backup", 1.0, reddit_backup),
            SocialPartition("bangumi", "Bangumi", "bangumi_anime", "Bangumi / anime", 1.0, bangumi),
        ]

        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            with patch("creative.social_trends._build_registry", return_value=registry), patch(
                "creative.social_trends._weighted_pick_without_replacement", side_effect=lambda partitions: list(partitions)
            ), patch(
                "creative.social_trends._RANDOM.sample", side_effect=lambda items, size: list(items[:size])
            ):
                result = collect_social_trend_sample(project_dir)

            self.assertEqual(result["sourceKey"], "bangumi")
            self.assertEqual(result["sampledSignalsZh"], ["signal a", "signal b", "signal c"])
            self.assertEqual(calls["reddit_hot"], 1)
            self.assertEqual(calls["reddit_backup"], 0)
            self.assertEqual(calls["bangumi"], 1)
            health = _load_health(project_dir)
            self.assertIn("reddit", health["sourceBackoff"])

    def test_active_source_backoff_skips_reddit_before_attempting_collectors(self):
        calls = {"reddit": 0, "bluesky": 0}

        def reddit() -> list[str]:
            calls["reddit"] += 1
            return ["should not be called", "should not be called either", "still should not be called"]

        def bluesky() -> list[str]:
            calls["bluesky"] += 1
            return ["signal a", "signal b", "signal c"]

        registry = [
            SocialPartition("reddit", "Reddit", "reddit_hot", "Reddit / hot", 1.0, reddit),
            SocialPartition("bluesky", "Bluesky", "bluesky_discover", "Bluesky / Discover", 1.0, bluesky),
        ]

        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            health = _load_health(project_dir)
            health["sourceBackoff"]["reddit"] = {
                "blockedUntil": "2099-01-01T00:00:00",
                "lastError": "HTTP 403: Blocked",
            }
            write_json(_health_path(project_dir), health)

            with patch("creative.social_trends._build_registry", return_value=registry), patch(
                "creative.social_trends._weighted_pick_without_replacement", side_effect=lambda partitions: list(partitions)
            ), patch(
                "creative.social_trends._RANDOM.sample", side_effect=lambda items, size: list(items[:size])
            ):
                result = collect_social_trend_sample(project_dir)

            self.assertEqual(result["sourceKey"], "bluesky")
            self.assertEqual(result["sampledSignalsZh"], ["signal a", "signal b", "signal c"])
            self.assertEqual(calls["reddit"], 0)
            self.assertEqual(calls["bluesky"], 1)

    def test_active_partition_backoff_skips_failing_provider_before_sampling(self):
        calls = {"bluesky": 0, "bangumi": 0}

        def bluesky() -> list[str]:
            calls["bluesky"] += 1
            return ["should not be called", "should not be called either", "still should not be called"]

        def bangumi() -> list[str]:
            calls["bangumi"] += 1
            return ["signal a", "signal b", "signal c"]

        registry = [
            SocialPartition("bluesky", "Bluesky", "bluesky_with_friends", "Bluesky / Popular With Friends", 1.0, bluesky),
            SocialPartition("bangumi", "Bangumi", "bangumi_anime", "Bangumi / anime", 1.0, bangumi),
        ]

        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            health = _load_health(project_dir)
            health["partitionBackoff"]["bluesky_with_friends"] = {
                "blockedUntil": "2099-01-01T00:00:00",
                "lastError": "HTTP 502",
            }
            write_json(_health_path(project_dir), health)

            with patch("creative.social_trends._build_registry", return_value=registry), patch(
                "creative.social_trends._weighted_pick_without_replacement", side_effect=lambda partitions: list(partitions)
            ), patch(
                "creative.social_trends._RANDOM.sample", side_effect=lambda items, size: list(items[:size])
            ):
                result = collect_social_trend_sample(project_dir)

            self.assertEqual(result["sourceKey"], "bangumi")
            self.assertEqual(calls["bluesky"], 0)
            self.assertEqual(calls["bangumi"], 1)

    def test_bilibili_partition_limits_comment_fallback_requests(self):
        posts = [
            {
                "aid": str(index),
                "title": f"title {index}",
                "desc": "#01",
                "tname": "anime",
                "pub_location": "",
            }
            for index in range(1, 8)
        ]
        seen_aids: list[str] = []

        def fake_comments(aid: str) -> list[str]:
            seen_aids.append(aid)
            return [f"comment {aid}"]

        with patch("creative.social_trends._collect_bilibili_region", return_value=posts), patch(
            "creative.social_trends._fetch_bilibili_comment_bodies",
            side_effect=fake_comments,
        ):
            signals = _collect_bilibili_partition(33)

        self.assertEqual(len(seen_aids), _BILIBILI_COMMENT_FALLBACK_LIMIT)
        self.assertEqual(len(signals), _BILIBILI_COMMENT_FALLBACK_LIMIT)

    def test_build_registry_skips_bluesky_when_feed_discovery_fails(self):
        with patch("creative.social_trends._list_bluesky_feeds", side_effect=RuntimeError("transport error")):
            registry = _build_registry()
        provider_keys = {partition.provider_key for partition in registry}
        self.assertIn("bangumi_anime", provider_keys)
        self.assertIn("bilibili_anime", provider_keys)
        self.assertNotIn("bluesky_discover", provider_keys)

    def test_list_bluesky_feeds_returns_stale_cache_when_refresh_fails(self):
        previous_loaded_at = _BLUESKY_FEED_CACHE.get("loadedAt")
        previous_feeds = list(_BLUESKY_FEED_CACHE.get("feeds", []))
        try:
            _BLUESKY_FEED_CACHE["loadedAt"] = None
            _BLUESKY_FEED_CACHE["feeds"] = [
                {
                    "uri": "at://cached/feed",
                    "display_name": "Cached Feed",
                    "description": "cached description",
                }
            ]
            with patch("creative.social_trends._fetch_json", side_effect=RuntimeError("transport error")):
                feeds = _list_bluesky_feeds()
            self.assertEqual(
                feeds,
                [
                    {
                        "uri": "at://cached/feed",
                        "display_name": "Cached Feed",
                        "description": "cached description",
                    }
                ],
            )
        finally:
            _BLUESKY_FEED_CACHE["loadedAt"] = previous_loaded_at
            _BLUESKY_FEED_CACHE["feeds"] = previous_feeds


if __name__ == "__main__":
    unittest.main()
