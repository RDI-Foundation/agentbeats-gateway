import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from proxy import _rewrite_agent_card


class RewriteAgentCardTests(unittest.TestCase):
    def test_rewrites_supported_interfaces_and_primary_url(self):
        body = json.dumps(
            {
                "name": "debater",
                "url": "http://127.0.0.1:9010/a2a",
                "supportedInterfaces": [
                    {"url": "http://localhost:9010/a2a?x=1#frag"},
                    {"url": "https://api.example.com/a2a"},
                ],
                "signatures": [{"sig": "abc"}],
            }
        ).encode()

        rewritten = json.loads(
            _rewrite_agent_card(body, "pro_debater", "http://gateway.internal:8080")
        )

        self.assertEqual(
            rewritten["url"],
            "http://gateway.internal:8080/pro_debater/a2a",
        )
        self.assertEqual(
            rewritten["supportedInterfaces"][0]["url"],
            "http://gateway.internal:8080/pro_debater/a2a?x=1#frag",
        )
        self.assertEqual(
            rewritten["supportedInterfaces"][1]["url"],
            "https://api.example.com/a2a",
        )
        self.assertNotIn("signatures", rewritten)

    def test_non_loopback_cards_are_left_unchanged(self):
        body = json.dumps(
            {
                "url": "https://api.example.com/a2a",
                "supportedInterfaces": [{"url": "https://api.example.com/a2a"}],
                "signatures": [{"sig": "abc"}],
            }
        ).encode()

        self.assertEqual(
            _rewrite_agent_card(body, "pro_debater", "http://gateway.internal:8080"),
            body,
        )


if __name__ == "__main__":
    unittest.main()
