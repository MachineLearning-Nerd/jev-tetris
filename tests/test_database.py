import tempfile
import unittest
from pathlib import Path

from database import (
    get_appointment,
    get_order,
    initialize_database,
    reschedule_appointment,
    table_counts,
)


class DatabaseTests(unittest.TestCase):
    def test_seed_is_idempotent_and_queries_return_demo_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "agent_courtroom.db"
            initialize_database(db_path)
            initialize_database(db_path)

            self.assertEqual(table_counts(db_path)["orders"], 2)
            self.assertEqual(get_order("order-4182", db_path)["status"], "shipped")

    def test_locked_appointment_does_not_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "agent_courtroom.db"
            initialize_database(db_path)

            result = reschedule_appointment("appt-1001", "Thursday", db_path)

            self.assertFalse(result["succeeded"])
            self.assertEqual(get_appointment("appt-1001", db_path)["scheduled_day"], "Tuesday")


if __name__ == "__main__":
    unittest.main()
