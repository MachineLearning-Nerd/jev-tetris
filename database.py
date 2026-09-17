from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any


DB_PATH = Path(__file__).resolve().parent / "data" / "agent_courtroom.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    status TEXT NOT NULL,
    shipped_at TEXT,
    tracking_code TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    title TEXT NOT NULL,
    scheduled_day TEXT NOT NULL,
    status TEXT NOT NULL,
    location TEXT NOT NULL,
    reschedule_allowed INTEGER NOT NULL CHECK (reschedule_allowed IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_appointments_user_id ON appointments(user_id);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    status TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    reason TEXT NOT NULL,
    next_step TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_refunds_user_id ON refunds(user_id);

CREATE TABLE IF NOT EXISTS account_activity (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    occurred_at TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_account_activity_user_date
    ON account_activity(user_id, occurred_at DESC);
"""

SEED_USERS = (
    ("demo-user", "Alex Demo", "alex@example.test"),
)

SEED_ORDERS = (
    ("order-4182", "demo-user", "shipped", "2026-09-16", "MOCK-4182"),
    ("order-4183", "demo-user", "processing", None, None),
)

SEED_APPOINTMENTS = (
    (
        "appt-1001",
        "demo-user",
        "Dentist cleaning",
        "Tuesday",
        "confirmed",
        "Northside Clinic",
        0,
    ),
    (
        "appt-1002",
        "demo-user",
        "Physical therapy",
        "Friday",
        "confirmed",
        "Movement Studio",
        1,
    ),
)

SEED_REFUNDS = (
    (
        "refund-88",
        "demo-user",
        "order-4183",
        "pending",
        2499,
        "Processor review required",
        "Wait for processor review; contact support if it remains pending for five business days.",
    ),
)

SEED_ACTIVITY = (
    ("demo-user", "2026-09-16", "login", "Signed in from a known device.", "low"),
    ("demo-user", "2026-09-15", "payment_method_viewed", "Viewed the saved payment method.", "low"),
    ("demo-user", "2026-09-14", "address_changed", "Updated the shipping address.", "medium"),
)


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: Path = DB_PATH) -> None:
    connection = connect(db_path)
    try:
        with connection:
            connection.executescript(SCHEMA)
            connection.executemany(
                "INSERT OR IGNORE INTO users (user_id, display_name, email) VALUES (?, ?, ?)",
                SEED_USERS,
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO orders
                    (order_id, user_id, status, shipped_at, tracking_code)
                VALUES (?, ?, ?, ?, ?)
                """,
                SEED_ORDERS,
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO appointments
                    (appointment_id, user_id, title, scheduled_day, status, location, reschedule_allowed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                SEED_APPOINTMENTS,
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO refunds
                    (refund_id, user_id, order_id, status, amount_cents, reason, next_step)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                SEED_REFUNDS,
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO account_activity
                    (user_id, occurred_at, action, description, severity)
                VALUES (?, ?, ?, ?, ?)
                """,
                SEED_ACTIVITY,
            )
    finally:
        connection.close()


def get_order(order_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    return _fetch_one(
        "SELECT * FROM orders WHERE order_id = ?",
        (order_id,),
        db_path,
    )


def get_appointment(appointment_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    return _fetch_one(
        "SELECT * FROM appointments WHERE appointment_id = ?",
        (appointment_id,),
        db_path,
    )


def get_refund(refund_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    return _fetch_one(
        "SELECT * FROM refunds WHERE refund_id = ?",
        (refund_id,),
        db_path,
    )


def list_recent_activity(user_id: str, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    connection = connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT * FROM account_activity
            WHERE user_id = ?
            ORDER BY occurred_at DESC
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def reschedule_appointment(
    appointment_id: str,
    new_day: str,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    appointment = get_appointment(appointment_id, db_path)
    if appointment is None:
        return {"succeeded": False, "message": "ERROR: appointment was not found."}

    if not appointment["reschedule_allowed"]:
        return {
            "succeeded": False,
            "message": (
                f"ERROR: {appointment['title']} cannot be rescheduled in this demo; "
                f"it remains on {appointment['scheduled_day']}."
            ),
        }

    connection = connect(db_path)
    try:
        with connection:
            connection.execute(
                "UPDATE appointments SET scheduled_day = ? WHERE appointment_id = ?",
                (new_day, appointment_id),
            )
        return {
            "succeeded": True,
            "message": f"Appointment moved to {new_day}.",
        }
    finally:
        connection.close()


def table_counts(db_path: Path = DB_PATH) -> dict[str, int]:
    connection = connect(db_path)
    try:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("users", "orders", "appointments", "refunds", "account_activity")
        }
    finally:
        connection.close()


def _fetch_one(
    query: str,
    parameters: tuple[Any, ...],
    db_path: Path,
) -> dict[str, Any] | None:
    connection = connect(db_path)
    try:
        row = connection.execute(query, parameters).fetchone()
        return dict(row) if row is not None else None
    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()
    print(f"Created local database at {DB_PATH}")
    print(table_counts())
