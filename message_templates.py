"""Hebrew message templates for WhatsApp appointment reminders."""

from datetime import datetime
from zoneinfo import ZoneInfo

import config

TIMEZONE = ZoneInfo(config.TIMEZONE)


def _format_datetime(dt: datetime) -> tuple[str, str]:
    """Return (date_str, time_str) formatted for display."""
    local_dt = dt.astimezone(TIMEZONE) if dt.tzinfo else dt
    date_str = local_dt.strftime("%d/%m/%Y")
    time_str = local_dt.strftime("%H:%M")
    return date_str, time_str


def build_reminder_message(
    recipient_phone: str,
    customer_name: str,
    appointment_time: datetime,
    appointment_subject: str,
    reminder_id: int,
) -> dict:
    """Build the interactive button reminder message payload."""
    date_str, time_str = _format_datetime(appointment_time)

    body_text = (
        f"\u05e9\u05dc\u05d5\u05dd {customer_name},\n\n"
        f"\u05e8\u05e6\u05d9\u05e0\u05d5 \u05dc\u05d4\u05d6\u05db\u05d9\u05e8 \u05dc\u05da \u05e9\u05e0\u05e7\u05d1\u05e2\u05d4 \u05e4\u05d2\u05d9\u05e9\u05d4 \u05e2\u05dd SafeShare:\n\n"
        f"\U0001f4c5 \u05ea\u05d0\u05e8\u05d9\u05da: {date_str}\n"
        f"\U0001f550 \u05e9\u05e2\u05d4: {time_str}\n"
        f"\U0001f4cb \u05e0\u05d5\u05e9\u05d0: {appointment_subject}\n\n"
        f"\u05e0\u05e9\u05de\u05d7 \u05dc\u05d0\u05e9\u05e8 \u05d0\u05ea \u05d4\u05d2\u05e2\u05ea\u05da."
    )

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "text",
                "text": "SafeShare - \u05ea\u05d6\u05db\u05d5\u05e8\u05ea \u05e4\u05d2\u05d9\u05e9\u05d4",
            },
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"confirm_{reminder_id}",
                            "title": "\u05d0\u05d9\u05e9\u05d5\u05e8 \u2713",
                        },
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"reschedule_{reminder_id}",
                            "title": "\u05e7\u05d1\u05d9\u05e2\u05d4 \u05de\u05d7\u05d3\u05e9",
                        },
                    },
                ],
            },
        },
    }


def build_confirm_ack(recipient_phone: str, appointment_time: datetime) -> dict:
    """Build the confirmation acknowledgment text message."""
    date_str, time_str = _format_datetime(appointment_time)

    return {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "body": (
                f"\u05ea\u05d5\u05d3\u05d4 \u05e2\u05dc \u05d4\u05d0\u05d9\u05e9\u05d5\u05e8! \u2713\n\n"
                f"\u05e0\u05ea\u05e8\u05d0\u05d4 \u05d1\u05e4\u05d2\u05d9\u05e9\u05d4 \u05d1-{date_str} \u05d1\u05e9\u05e2\u05d4 {time_str}.\n\n"
                f"\u05d0\u05dd \u05ea\u05e6\u05d8\u05e8\u05da \u05dc\u05e9\u05e0\u05d5\u05ea \u2014 \u05e4\u05e9\u05d5\u05d8 \u05e6\u05d5\u05e8 \u05e7\u05e9\u05e8."
            )
        },
    }


def build_reschedule_ack(recipient_phone: str) -> dict:
    """Build the reschedule acknowledgment text message with Calendly link."""
    return {
        "messaging_product": "whatsapp",
        "to": recipient_phone,
        "type": "text",
        "text": {
            "body": (
                f"\u05e7\u05d9\u05d1\u05dc\u05e0\u05d5 \u05d0\u05ea \u05d1\u05e7\u05e9\u05ea\u05da \u05dc\u05ea\u05d9\u05d0\u05d5\u05dd \u05de\u05d7\u05d3\u05e9.\n\n"
                f"\u05dc\u05e7\u05d1\u05d9\u05e2\u05ea \u05de\u05d5\u05e2\u05d3 \u05d7\u05d3\u05e9 \u05dc\u05d7\u05e6/\u05d9 \u05db\u05d0\u05df:\n"
                f"{config.BOOKING_URL}\n\n"
                f"\u05d0\u05d5 \u05e9\u05e0\u05e6\u05d9\u05d2 \u05e9\u05dc\u05e0\u05d5 \u05d9\u05d9\u05e6\u05d5\u05e8 \u05d0\u05d9\u05ea\u05da \u05e7\u05e9\u05e8 \u05d1\u05d4\u05e7\u05d3\u05dd."
            )
        },
    }


def build_owner_reschedule_notification(
    customer_name: str,
    customer_phone: str,
    appointment_time: datetime,
    appointment_subject: str,
) -> dict:
    """Build the notification message sent to the business owner on reschedule."""
    date_str, time_str = _format_datetime(appointment_time)

    # Format phone for display (e.g., "972544522025" → "054-452-2025")
    display_phone = customer_phone
    if customer_phone.startswith("972") and len(customer_phone) == 12:
        p = "0" + customer_phone[3:]
        display_phone = f"{p[:3]}-{p[3:6]}-{p[6:]}"

    return {
        "messaging_product": "whatsapp",
        "to": config.MY_WHATSAPP_NUMBER,
        "type": "text",
        "text": {
            "body": (
                f"\U0001f514 \u05d1\u05e7\u05e9\u05d4 \u05dc\u05e7\u05d1\u05d9\u05e2\u05d4 \u05de\u05d7\u05d3\u05e9\n\n"
                f"\u05d4\u05dc\u05e7\u05d5\u05d7 {customer_name} ({display_phone}) \u05d1\u05d9\u05e7\u05e9 "
                f"\u05dc\u05e7\u05d1\u05d5\u05e2 \u05de\u05d7\u05d3\u05e9 \u05d0\u05ea \u05d4\u05e4\u05d2\u05d9\u05e9\u05d4 \u05e9\u05ea\u05d5\u05db\u05e0\u05e0\u05d4 \u05dc:\n"
                f"{date_str} \u05d1\u05e9\u05e2\u05d4 {time_str}\n"
                f"\u05e0\u05d5\u05e9\u05d0: {appointment_subject}"
            )
        },
    }
