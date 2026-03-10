import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import load_config


class LoadConfigTests(unittest.TestCase):
    def test_load_config_reads_required_fields(self):
        with patch.dict(
            os.environ,
            {
                "SERVICE_URLS": '{"green":{"url":"http://green"},"purple1":{"url":"http://purple"}}',
                "PARTICIPANT_ROLES": '{"green":"judge","purple1":"debater"}',
                "ASSESSMENT_CONFIG": '{"topic":"test"}',
            },
            clear=True,
        ), patch.object(sys, "argv", ["gateway"]):
            config = load_config()

        self.assertEqual(
            config.service_urls,
            {"green": "http://green", "purple1": "http://purple"},
        )
        self.assertEqual(
            config.participant_roles,
            {"green": "judge", "purple1": "debater"},
        )
        self.assertEqual(config.assessment_config, {"topic": "test"})


if __name__ == "__main__":
    unittest.main()
