import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main


class RunAssessmentTaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_routes_only_declared_participants_through_local_proxy(self):
        config = SimpleNamespace(
            proxy_port=8080,
            service_urls={
                "green": "http://green",
                "green_mcp": "http://green-mcp",
                "purple1": "http://purple1",
            },
            participant_roles={
                "green": "judge",
                "purple1": "pro_debater",
                "purple2": "missing",
            },
            assessment_config={"topic": "test"},
        )

        with patch.object(
            main, "wait_for_agents", AsyncMock(return_value=True)
        ) as wait_for_agents, patch.object(
            main,
            "run_assessment",
            AsyncMock(return_value={"status": "completed", "results": [{"winner": "pro"}]}),
        ) as run_assessment:
            main.result_data = {"status": "running"}
            await main.run_assessment_task(config)

        wait_for_agents.assert_awaited_once_with(["http://green", "http://purple1"])
        run_assessment.assert_awaited_once_with(
            "http://green",
            {
                "pro_debater": "http://127.0.0.1:8080/pro_debater",
            },
            {"topic": "test"},
        )
        self.assertEqual(
            main.result_data,
            {"status": "completed", "results": [{"winner": "pro"}]},
        )

    async def test_reports_readiness_timeout_without_starting_assessment(self):
        config = SimpleNamespace(
            proxy_port=8080,
            service_urls={"green": "http://green"},
            participant_roles={"green": "judge"},
            assessment_config={},
        )

        with patch.object(
            main, "wait_for_agents", AsyncMock(return_value=False)
        ) as wait_for_agents, patch.object(
            main, "run_assessment", AsyncMock()
        ) as run_assessment:
            main.result_data = {"status": "running"}
            await main.run_assessment_task(config)

        wait_for_agents.assert_awaited_once_with(["http://green"])
        run_assessment.assert_not_awaited()
        self.assertEqual(
            main.result_data,
            {"status": "failed", "error": "Timeout: agents not ready"},
        )


if __name__ == "__main__":
    unittest.main()
