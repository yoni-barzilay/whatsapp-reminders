"""Database connection and queries for appointment reminders."""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import pymysql
import pymysql.cursors

import config

logger = logging.getLogger(__name__)

_pool = None

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS appointment_reminders (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    outlook_event_id  VARCHAR(512) NOT NULL UNIQUE,
    lead_id           INT NULL,
    customer_phone    VARCHAR(20) NOT NULL,
    customer_name     VARCHAR(255) NOT NULL,
    appointment_time  DATETIME NOT NULL,
    appointment_subject VARCHAR(500),
    reminder_sent_at  DATETIME NULL,
    whatsapp_message_id VARCHAR(128) NULL,
    status            ENUM('pending','reminder_sent','confirmed','reschedule_requested','failed')
                      NOT NULL DEFAULT 'pending',
    response_at       DATETIME NULL,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_appointment_time (appointment_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def get_connection():
    """Get a new MySQL connection."""
    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASS,
        database=config.MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


@contextmanager
def get_cursor():
    """Context manager that yields a cursor and handles connection lifecycle."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
    finally:
        conn.close()


def run_migration():
    """Verify the appointment_reminders table exists (created externally)."""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM appointment_reminders LIMIT 1")
        logger.info("Migration check: appointment_reminders table ready")
    except Exception as e:
        logger.warning("appointment_reminders table check failed: %s", e)
        logger.warning("Please create the table manually (readonly_user lacks CREATE)")


def find_lead_by_email(email: str) -> Optional[dict]:
    """Find a lead by email address. Returns dict or None."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT ID, First_name, Last_name, Phone, email "
            "FROM Leads "
            "WHERE email = %s AND Phone IS NOT NULL AND Phone != '' "
            "LIMIT 1",
            (email,),
        )
        return cursor.fetchone()


def find_lead_by_name(full_name: str) -> Optional[dict]:
    """Find a lead by full name. Returns dict or None."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT ID, First_name, Last_name, Phone, email "
            "FROM Leads "
            "WHERE CONCAT(First_name, ' ', Last_name) = %s "
            "AND Phone IS NOT NULL AND Phone != '' "
            "LIMIT 1",
            (full_name,),
        )
        return cursor.fetchone()


def reminder_exists(outlook_event_id: str) -> bool:
    """Check if a reminder already exists for this Outlook event."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM appointment_reminders WHERE outlook_event_id = %s LIMIT 1",
            (outlook_event_id,),
        )
        return cursor.fetchone() is not None


def insert_reminder(
    outlook_event_id: str,
    lead_id: Optional[int],
    customer_phone: str,
    customer_name: str,
    appointment_time: datetime,
    appointment_subject: Optional[str],
) -> int:
    """Insert a new reminder record. Returns the new row ID."""
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO appointment_reminders "
            "(outlook_event_id, lead_id, customer_phone, customer_name, "
            "appointment_time, appointment_subject) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (outlook_event_id, lead_id, customer_phone, customer_name,
             appointment_time, appointment_subject),
        )
        return cursor.lastrowid


def update_reminder_sent(reminder_id: int, whatsapp_message_id: str):
    """Mark a reminder as sent."""
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE appointment_reminders "
            "SET status = 'reminder_sent', reminder_sent_at = NOW(), "
            "whatsapp_message_id = %s WHERE id = %s",
            (whatsapp_message_id, reminder_id),
        )


def update_reminder_status(reminder_id: int, status: str):
    """Update reminder status (confirmed, reschedule_requested, failed)."""
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE appointment_reminders "
            "SET status = %s, response_at = NOW() WHERE id = %s",
            (status, reminder_id),
        )


def update_reminder_failed(reminder_id: int):
    """Mark a reminder as failed."""
    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE appointment_reminders SET status = 'failed' WHERE id = %s",
            (reminder_id,),
        )


def get_reminder_by_id(reminder_id: int) -> Optional[dict]:
    """Get a single reminder by ID."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM appointment_reminders WHERE id = %s", (reminder_id,)
        )
        return cursor.fetchone()


def get_pending_reminders() -> list[dict]:
    """Get all reminders with status 'pending'."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM appointment_reminders WHERE status = 'pending' "
            "ORDER BY appointment_time"
        )
        return cursor.fetchall()


def get_failed_reminders() -> list[dict]:
    """Get all reminders with status 'failed' for retry."""
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM appointment_reminders WHERE status = 'failed' "
            "ORDER BY appointment_time"
        )
        return cursor.fetchall()


def get_reminders(
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List reminders with optional filters."""
    query = "SELECT * FROM appointment_reminders WHERE 1=1"
    params = []

    if status:
        query += " AND status = %s"
        params.append(status)
    if date_from:
        query += " AND appointment_time >= %s"
        params.append(date_from)
    if date_to:
        query += " AND appointment_time <= %s"
        params.append(date_to)

    query += " ORDER BY appointment_time DESC LIMIT %s"
    params.append(limit)

    with get_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()

