"""Telegram group notifications for appointment reminder events."""

import logging
from html import escape

import requests

import config

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
_raw_chat_id = config.TELEGRAM_CHAT_ID.strip().strip('"').strip("'")
TELEGRAM_CHAT_ID = int(_raw_chat_id) if _raw_chat_id else None
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

logger.info("Telegram chat_id configured: %s (raw env: %r)", TELEGRAM_CHAT_ID, config.TELEGRAM_CHAT_ID)


def _send(text: str, caller: str = "") -> bool:
    """Send an HTML-formatted message to the Telegram group."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram not configured, skipping notification")
        return False

    logger.info("[TG-SEND] caller=%s chat_id=%s type=%s", caller, TELEGRAM_CHAT_ID, type(TELEGRAM_CHAT_ID).__name__)
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json=payload,
            timeout=10,
        )
        data = resp.json()
        if not resp.ok:
            logger.error("[TG-SEND] API error: %s %s", resp.status_code, resp.text)
        else:
            # Log where the message actually went
            chat_info = data.get("result", {}).get("chat", {})
            logger.info("[TG-SEND] SUCCESS caller=%s -> chat_id=%s chat_type=%s chat_title=%s",
                        caller, chat_info.get("id"), chat_info.get("type"), chat_info.get("title", "N/A"))
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("[TG-SEND] Failed to send Telegram notification (caller=%s)", caller)
        return False


def _format_phone(phone: str) -> str:
    """Format 972XXXXXXXXX to 05X-XXX-XXXX for display."""
    if phone.startswith("972") and len(phone) == 12:
        p = "0" + phone[3:]
        return f"{p[:3]}-{p[3:6]}-{p[6:]}"
    return phone


def send_test() -> dict:
    """Send a test message to verify group delivery. Returns API response."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {"error": "Telegram not configured", "chat_id": TELEGRAM_CHAT_ID}

    text = f"\U0001f9ea <b>Test</b>\n\nchat_id: <code>{TELEGRAM_CHAT_ID}</code>"
    try:
        resp = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


def notify_confirmed(customer_name: str, customer_phone: str,
                     appointment_time, appointment_subject: str):
    """Notify the group that a client confirmed their appointment."""
    from message_templates import _format_datetime
    date_str, time_str = _format_datetime(appointment_time)
    phone_display = _format_phone(customer_phone)

    text = (
        f"\u2705 <b>\u05d0\u05d9\u05e9\u05d5\u05e8 \u05e4\u05d2\u05d9\u05e9\u05d4</b>\n\n"
        f"<b>{escape(customer_name)}</b> ({phone_display})\n"
        f"\u05d0\u05d9\u05e9\u05e8/\u05d4 \u05d0\u05ea \u05d4\u05e4\u05d2\u05d9\u05e9\u05d4:\n"
        f"{date_str} \u05d1\u05e9\u05e2\u05d4 {time_str}\n"
        f"\u05e0\u05d5\u05e9\u05d0: {escape(appointment_subject) or 'N/A'}"
    )
    _send(text, caller="notify_confirmed")


def notify_reschedule(customer_name: str, customer_phone: str,
                      appointment_time, appointment_subject: str):
    """Notify the group that a client requested to reschedule."""
    from message_templates import _format_datetime
    date_str, time_str = _format_datetime(appointment_time)
    phone_display = _format_phone(customer_phone)

    text = (
        f"\U0001f514 <b>\u05d1\u05e7\u05e9\u05d4 \u05dc\u05ea\u05d9\u05d0\u05d5\u05dd \u05de\u05d7\u05d3\u05e9</b>\n\n"
        f"<b>{escape(customer_name)}</b> ({phone_display})\n"
        f"\u05d1\u05d9\u05e7\u05e9/\u05d4 \u05dc\u05ea\u05d0\u05dd \u05de\u05d7\u05d3\u05e9 \u05d0\u05ea \u05d4\u05e4\u05d2\u05d9\u05e9\u05d4:\n"
        f"{date_str} \u05d1\u05e9\u05e2\u05d4 {time_str}\n"
        f"\u05e0\u05d5\u05e9\u05d0: {escape(appointment_subject) or 'N/A'}"
    )
    _send(text, caller="notify_reschedule")


def notify_reminder_sent(customer_name: str, customer_phone: str,
                         appointment_time, appointment_subject: str):
    """Notify the group that a reminder was sent to a client."""
    from message_templates import _format_datetime
    date_str, time_str = _format_datetime(appointment_time)
    phone_display = _format_phone(customer_phone)

    text = (
        f"\U0001f4e4 <b>\u05ea\u05d6\u05db\u05d5\u05e8\u05ea \u05e0\u05e9\u05dc\u05d7\u05d4</b>\n\n"
        f"<b>{escape(customer_name)}</b> ({phone_display})\n"
        f"\u05e4\u05d2\u05d9\u05e9\u05d4: {date_str} \u05d1\u05e9\u05e2\u05d4 {time_str}\n"
        f"\u05e0\u05d5\u05e9\u05d0: {escape(appointment_subject) or 'N/A'}"
    )
    _send(text, caller="notify_reminder_sent")


def notify_invalid_phone(lead_id: int, lead_name: str, lead_email: str,
                         raw_phone: str, appointment_subject: str = ""):
    """Notify the group about an invalid phone number."""
    text = (
        f"\u26a0\ufe0f <b>\u05de\u05e1\u05e4\u05e8 \u05d8\u05dc\u05e4\u05d5\u05df \u05dc\u05d0 \u05ea\u05e7\u05d9\u05df</b>\n\n"
        f"\u05dc\u05d9\u05d3 #{lead_id}: <b>{escape(lead_name)}</b>\n"
        f"\u05d0\u05d9\u05de\u05d9\u05d9\u05dc: {escape(lead_email)}\n"
        f"\u05d8\u05dc\u05e4\u05d5\u05df: <code>{escape(raw_phone)}</code>\n"
        f"\u05e4\u05d2\u05d9\u05e9\u05d4: {escape(appointment_subject) or 'N/A'}\n\n"
        f"\u05e0\u05d0 \u05dc\u05e2\u05d3\u05db\u05df \u05d0\u05ea \u05d4\u05d8\u05dc\u05e4\u05d5\u05df \u05d1-CRM."
    )
    _send(text, caller="notify_invalid_phone")
