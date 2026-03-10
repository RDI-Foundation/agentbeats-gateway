import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from main import get_agent_routes, get_participant_service_urls


class MainHelpersTests(unittest.TestCase):
    def test_runtime_ignores_legacy_non_participant_slots(self):
        config = SimpleNamespace(
            service_urls={
                "green": "http://green",
                "green_mcp": "http://green-mcp",
                "purple1": "http://purple1",
            },
            participant_roles={
                "green": "debate_judge",
                "purple1": "pro_debater",
            },
        )

        self.assertEqual(
            get_participant_service_urls(config),
            ["http://green", "http://purple1"],
        )
        self.assertEqual(
            get_agent_routes(config),
            {
                "debate_judge": "http://green",
                "pro_debater": "http://purple1",
            },
        )


if __name__ == "__main__":
    unittest.main()
