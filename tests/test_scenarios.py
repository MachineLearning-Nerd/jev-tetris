import unittest
import tempfile
from pathlib import Path

from database import initialize_database
from scenarios import ToolCall, build_local_scenario, custom_scenario


class CustomScenarioTests(unittest.TestCase):
    def test_custom_scenario_exposes_user_entered_trace(self) -> None:
        scenario = custom_scenario(
            task="Check my appointment",
            agent_instructions="Do not change anything.",
            conversation=("User: Check tomorrow.",),
            tool_calls=(
                ToolCall(
                    name="get_appointment",
                    arguments={"day": "tomorrow"},
                    result="No appointment found.",
                    permission="allowed: read calendar",
                ),
            ),
            final_message="You have no appointment tomorrow.",
            customer_feedback="That is correct.",
        )

        self.assertEqual(scenario.id, "custom")
        self.assertEqual(scenario.state()["task"], "Check my appointment")
        self.assertEqual(scenario.state()["tool_calls"][0]["name"], "get_appointment")


class LocalScenarioTests(unittest.TestCase):
    def test_local_scenario_uses_seeded_sqlite_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "agent_courtroom.db"
            initialize_database(db_path)

            scenario = build_local_scenario("appointment_failure", db_path)

            self.assertEqual(scenario.id, "local_appointment_failure")
            self.assertIn("cannot be rescheduled", scenario.tool_calls[0].result)
            self.assertFalse(scenario.tool_calls[0].succeeded)


if __name__ == "__main__":
    unittest.main()
