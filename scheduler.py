"""APScheduler configuration for hourly calendar scanning."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
import db
from outlook_client import get_upcoming_appointments, normalize_phone
from whatsapp_client import send_interactive_message
from message_templates import build_reminder_message

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=config.TIMEZONE)

QUIET_AFTER = (22, 30)  # No sends after 22:30 Israel time
QUIET_BEFORE = (8, 0)   # No sends before 08:00 Israel time


def _is_quiet_hours() -> bool:
    """Return True if current Israel time is outside sending window.

    Schedule:
      Sun-Thu: 08:00-22:30
      Friday:  off all day (Shabbat)
      Saturday: after 20:00 only
    """
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    current = (now.hour, now.minute)
    weekday = now.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun

    # Friday (4) - no sends all day
    if weekday == 4:
        return True

    # Saturday (5) - only after 20:00
    if weekday == 5:
        return current < (20, 0) or current >= QUIET_AFTER

    # Sun-Thu - normal 08:00-22:30 window
    return current >= QUIET_AFTER or current < QUIET_BEFORE


def scan_and_send_reminders() -> int:
    """Scan next 24h of calendar and send WhatsApp reminders."""
    if _is_quiet_hours():
        logger.info("Quiet hours -- skipping scan")
        return 0

    logger.info("Starting calendar scan for next 24h appointments")
    sent_count = 0

    try:
        appointments = get_upcoming_appointments()
    except Exception:
        logger.exception("Failed to fetch appointments from Outlook")
        return 0

    for appt in appointments:
        try:
            sent = _process_appointment(appt)
            if sent:
                sent_count += 1
        except Exception:
            logger.exception(
                "Failed to process appointment %s for %s",
                appt.event_id,
                appt.attendee_email,
            )

    logger.info("Calendar scan complete: %d reminders sent", sent_count)
    return sent_count


def _process_appointment(appt) -> bool:
    if db.reminder_exists(appt.event_id):
        logger.debug("Reminder already exists for event %s, skipping", appt.event_id)
        return False

    lead = db.find_lead_by_email(appt.attendee_email)
    if lead is None:
        lead = db.find_lead_by_name(appt.attendee_name)
    if lead is None:
        logger.warning("No lead found for attendee %s (%s), skipping", appt.attendee_name, appt.attendee_email)
        return False

    phone = normalize_phone(lead["Phone"])
    if not phone or len(phone) < 10:
        logger.warning("Invalid phone for lead %s: %s", lead["ID"], lead["Phone"])
        return False

    name = f"{lead['First_name']} {lead['Last_name']}".strip()

    reminder_id = db.insert_reminder(
        outlook_event_id=appt.event_id, lead_id=lead["ID"],
        customer_phone=phone, customer_name=name,
        appointment_time=appt.start_time, appointment_subject=appt.subject,
    )

    payload = build_reminder_message(
        recipient_phone=phone, customer_name=name,
        appointment_time=appt.start_time,
        appointment_subject=appt.subject or "\u05e4\u05d2\u05d9\u05e9\u05d4 \u05e2\u05dd SafeShare",
        reminder_id=reminder_id,
    )

    try:
        msg_id = send_interactive_message(payload)
        db.update_reminder_sent(reminder_id, msg_id)
        logger.info("Reminder #%d sent to %s (lead %d)", reminder_id, phone, lead["ID"])
        return True
    except Exception:
        db.update_reminder_failed(reminder_id)
        logger.exception("Failed to send WhatsApp message for reminder #%d", reminder_id)
        raise


def retry_failed_reminders() -> int:
    if _is_quiet_hours():
        return 0

    failed = db.get_failed_reminders()
    if not failed:
        return 0

    logger.info("Retrying %d failed reminders", len(failed))
    retried = 0

    for reminder in failed:
        try:
            payload = build_reminder_message(
                recipient_phone=reminder["customer_phone"],
                customer_name=reminder["customer_name"],
                appointment_time=reminder["appointment_time"],
                appointment_subject=reminder["appointment_subject"] or "\u05e4\u05d2\u05d9\u05e9\u05d4 \u05e2\u05dd SafeShare",
                reminder_id=reminder["id"],
            )
            msg_id = send_interactive_message(payload)
            db.update_reminder_sent(reminder["id"], msg_id)
            retried += 1
            logger.info("Retry successful for reminder #%d", reminder["id"])
        except Exception:
            logger.exception("Retry failed for reminder #%d", reminder["id"])

    return retried


def start_scheduler():
    scheduler.add_job(
        scan_and_send_reminders,
        trigger=IntervalTrigger(hours=1, timezone=config.TIMEZONE),
        id="hourly_scan", name="Hourly calendar scan (24h window)", replace_existing=True,
    )
    scheduler.add_job(
        retry_failed_reminders,
        trigger=IntervalTrigger(minutes=30, timezone=config.TIMEZONE),
        id="retry_failed", name="Retry failed reminders", replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: scan every 1h, retry every 30m (%s)", config.TIMEZONE)
