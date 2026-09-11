#!/usr/bin/env python3
"""
Automated test suite for GitHub Profile README and automation layers.
Verifies:
- README marker tags and structure
- HTML and table tag symmetry
- Markdown links validity
- update_readme.py replacement logic and event parsing
"""

import os
import re
import unittest
import importlib.util

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")
SCRIPT_PATH = os.path.join(REPO_ROOT, ".github", "scripts", "update_readme.py")

# Load update_readme dynamically as a module
spec = importlib.util.spec_from_file_location("update_readme", SCRIPT_PATH)
update_readme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_readme)


class TestProfileIntegrity(unittest.TestCase):

    def setUp(self):
        self.assertTrue(os.path.exists(README_PATH), "README.md must exist in the repository root")
        with open(README_PATH, "r", encoding="utf-8") as f:
            self.readme_content = f.read()

    def test_required_markers_exist(self):
        """Ensure all dynamic marker tags are present and balanced."""
        required_marker_pairs = [
            ("<!-- START_SECTION:activity -->", "<!-- END_SECTION:activity -->"),
            ("<!-- START_SECTION:updated_at -->", "<!-- END_SECTION:updated_at -->"),
        ]
        for start_tag, end_tag in required_marker_pairs:
            self.assertIn(start_tag, self.readme_content, f"Missing start marker: {start_tag}")
            self.assertIn(end_tag, self.readme_content, f"Missing end marker: {end_tag}")
            start_pos = self.readme_content.find(start_tag)
            end_pos = self.readme_content.find(end_tag)
            self.assertLess(start_pos, end_pos, f"Start marker {start_tag} must precede end marker {end_tag}")

    def test_html_tags_symmetry(self):
        """Verify that table, picture, div, sub tags are properly opened and closed."""
        tags = ["table", "tr", "td", "picture", "div", "sub"]
        for tag in tags:
            open_count = len(re.findall(rf"<{tag}(\s+[^>]*)?>", self.readme_content, re.IGNORECASE))
            close_count = len(re.findall(rf"</{tag}>", self.readme_content, re.IGNORECASE))
            self.assertEqual(
                open_count,
                close_count,
                f"Mismatched <{tag}> tags: found {open_count} opening and {close_count} closing tags"
            )

    def test_markdown_links_format(self):
        """Verify that all markdown links [text](url) are syntactically valid."""
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        matches = link_pattern.findall(self.readme_content)
        self.assertGreater(len(matches), 0, "README should have links")
        for text, url in matches:
            text = text.strip()
            url = url.strip()
            self.assertGreater(len(text), 0, "Link text cannot be empty")
            self.assertTrue(
                url.startswith("http://") or url.startswith("https://") or url.startswith("mailto:"),
                f"Link '{text}' has invalid destination: {url}"
            )

    def test_no_forbidden_emojis(self):
        """Ensure no unwanted emojis slipped back into the profile headers or bullets."""
        forbidden_emojis = ["🚀", "👨‍💻", "🎓", "💼", "🔬", "⚡", "💻", "📊", "🐍", "🐅", "🫁", "🏎️", "🌐", "♟️"]
        for emoji in forbidden_emojis:
            self.assertNotIn(emoji, self.readme_content, f"Found unwanted emoji '{emoji}' in README.md")


class TestUpdateScriptLogic(unittest.TestCase):

    def test_replace_section_unit(self):
        """Test the regex-based section replacement in update_readme.py."""
        template = "Intro\n<!-- START_SECTION:test -->\nOld content\n<!-- END_SECTION:test -->\nOutro"
        result = update_readme.replace_section(
            template,
            "<!-- START_SECTION:test -->",
            "<!-- END_SECTION:test -->",
            "New content"
        )
        expected = "Intro\n<!-- START_SECTION:test -->\nNew content\n<!-- END_SECTION:test -->\nOutro"
        self.assertEqual(result, expected)

    def test_replace_section_missing_marker_safety(self):
        """Ensure script handles missing markers safely without modifying text or crashing."""
        template = "No markers here"
        result = update_readme.replace_section(
            template,
            "<!-- START_SECTION:missing -->",
            "<!-- END_SECTION:missing -->",
            "New content"
        )
        self.assertEqual(result, template)

    def test_fetch_github_activity_parsing(self):
        """Test event parsing with synthetic mock data for different GitHub event types."""
        mock_events = [
            {
                "type": "PushEvent",
                "repo": {"name": "kshtomar/TigersDay"},
                "payload": {"commits": [{"message": "feat: add MCTS optimization"}]},
                "created_at": "2026-09-11T00:00:00Z"
            },
            {
                "type": "PullRequestEvent",
                "repo": {"name": "kshtomar/TigersDay"},
                "payload": {
                    "action": "opened",
                    "pull_request": {"number": 12, "title": "WebAssembly SIMD backend", "html_url": "https://github.com/kshtomar/TigersDay/pull/12"}
                },
                "created_at": "2026-09-11T00:00:00Z"
            },
            {
                "type": "WatchEvent",
                "repo": {"name": "torvalds/linux"},
                "created_at": "2026-09-11T00:00:00Z"
            }
        ]

        # Intercept urlopen to test parsing without external network call
        original_urlopen = update_readme.urllib.request.urlopen

        class MockResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                import json
                return json.dumps(mock_events).encode("utf-8")

        update_readme.urllib.request.urlopen = lambda req, **kwargs: MockResponse()
        try:
            items = update_readme.fetch_github_activity("kshtomar")
            self.assertIsNotNone(items)
            self.assertEqual(len(items), 3)
            self.assertIn("Pushed 1 commit to [`kshtomar/TigersDay`]", items[0])
            self.assertIn("Opened PR [#12 WebAssembly SIMD backend]", items[1])
            self.assertIn("Starred [`torvalds/linux`]", items[2])
            # Ensure no emojis in parsed events
            for item in items:
                self.assertFalse(any(char in item for char in ["🔨", "🔀", "⭐", "🎉", "🌿", "🍴", "⚠️"]))
        finally:
            update_readme.urllib.request.urlopen = original_urlopen


if __name__ == "__main__":
    unittest.main()
