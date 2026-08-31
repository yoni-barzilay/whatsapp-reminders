"""Telegram group notifications for appointment reminder events."""

import logging

import requests

import config

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _send(text: str) -> bool:
    """Send an HTML-formatted message to the Telegram group."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram not configured, skipping notification")
        return False

    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed to send Telegram notification")
        return False


def _format_phone(phone: str) -> str:
    """Format 972XXXXXXXXX to 05X-XXX-XXXX for display."""
    if phone.startswith("972") and len(phone) == 12:
        p = "0" + phone[3:]
        return f"{p[:3]}-{p[3:6]}-{p[6:]}"
    return phone


def notify_confirmed(customer_name: str, customer_phone: str,
                     appointment_time, appointment_subject: str):
    """Notify the group that a client confirmed their appointment."""
    from message_templates import _format_datetime
    date_str, time_str = _format_datetime(appointment_time)
    phone_display = _format_phone(customer_phone)

    text = (
        f"\u2705 <b>Appointment Confirmed</b>\n\n"
        f"<b>{customer_name}</b> ({phone_display})\n"
        f"confirmed the meeting on {date_str} at {time_str}\n"
        f"Subject: {appointment_subject or 'N/A'}"
    )
    _send(text)


def notify_reschedule(customer_name: str, customer_phone: str,
                      appointment_time, appointment_subject: str):
    """Notify the group that a client requested to reschedule."""
    from message_templates import _format_datetime
    date_str, time_str = _format_datetime(appointment_time)
    phone_display = _format_phone(customer_phone)

    text = (
        f"\U0001f514 <b>Reschedule Requested</b>\n\n"
        f"<b>{customer_name}</b> ({phone_display})\n"
        f"wants to reschedule the meeting on {date_str} at {time_str}\n"
        f"Subject: {appointment_subject or 'N/A'}"
    )
    _send(text)


def notify_reminder_sent(customer_name: str, customer_phone: str,
                         appointment_time, appointment_subject: str):
    """Notify the group that a reminder was sent to a client."""
    from message_templates import _format_datetime
    date_str, time_str = _format_datetime(appointment_time)
    phone_display = _format_phone(customer_phone)

    text = (
        f"\U0001f4e4 <b>Reminder Sent</b>\n\n"
        f"<b>{customer_name}</b> ({phone_display})\n"
        f"Meeting: {date_str} at {time_str}\n"
        f"Subject: {appointment_subject or 'N/A'}"
    )
    _send(text)


def notify_invalid_phone(lead_id: int, lead_name: str, lead_email: str,
                         raw_phone: str, appointment_subject: str = ""):
    """Notify the group about an invalid phone number."""
    text = (
        f"\u26a0\ufe0f <b>Invalid Phone Number</b>\n\n"
        f"Lead #{lead_id}: <b>{lead_name}</b>\n"
        f"Email: {lead_email}\n"
        f"Phone: <code>{raw_phone}</code>\n"
        f"Meeting: {appointment_subject or 'N/A'}\n\n"
        f"Please update the phone in the CRM."
    )
    _send(text)
