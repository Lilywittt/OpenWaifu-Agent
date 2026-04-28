from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from publish.adapters.publish_content import publish_caption, publish_tags


class PublishContentTests(unittest.TestCase):
    def test_publish_tags_come_from_agent_output_only(self) -> None:
        publish_input = {
            "socialPostText": "demo caption",
            "socialTags": ["雨夜", "#便利店", "雨夜"],
        }
        target_config = {
            "tags": ["OpenWaifuAgent", "AIart"],
            "captionSuffix": "#debug",
        }

        self.assertEqual(publish_tags(publish_input, target_config), ["雨夜", "便利店"])

    def test_caption_appends_agent_tags_only_when_enabled(self) -> None:
        publish_input = {
            "socialPostText": "demo caption",
            "socialTags": ["雨夜", "便利店"],
        }

        self.assertEqual(publish_caption(publish_input, {}), "demo caption")
        self.assertEqual(
            publish_caption(publish_input, {"includeSocialTagsInCaption": True}),
            "demo caption\n\n#雨夜 #便利店",
        )


if __name__ == "__main__":
    unittest.main()
