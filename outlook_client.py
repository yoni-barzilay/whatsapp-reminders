"""Microsoft Graph API client for Outlook calendar integration."""

import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import msal
import requests

import config
from models import Appointment

logger = logging.getLogger(__name__)

_msal_app = None
_cached_token = None


def _get_msal_app():
    """Get or create the MSAL confidential client application."""
    global _msal_app
    if _msal_app is None:
        _msal_app = msal.ConfidentialClientApplication(
            client_id=config.AZURE_CLIENT_ID,
            client_credential=config.AZURE_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{config.AZURE_TENANT_ID}",
        )
    return _msal_app


def _get_access_token() -> str:
    """Acquire an access token using client_credentials flow (cached by MSAL)."""
    app = _get_msal_app()
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise RuntimeError(f"Failed to acquire Graph API token: {error}")
    return result["access_token"]


def get_upcoming_appointments() -> list[Appointment]:
    """Fetch all calendar events in the next 24 hours from the user's Outlook calendar."""
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    window_end = now + timedelta(hours=24)

    start_str = now.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = window_end.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    token = _get_access_token()
    url = (
        f"{config.GRAPH_API_URL}/users/{config.USER_EMAIL}/calendarView"
        f"?startDateTime={start_str}&endDateTime={end_str}"
        f"&$select=id,subject,start,end,attendees,bodyPreview"
        f"&$top=50"
    )

    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    required = config.REQUIRED_ATTENDEE.lower()

    appointments = []
    for event in data.get("value", []):
        attendee_emails = [
            a.get("emailAddress", {}).get("address", "").lower()
            for a in event.get("attendees", [])
            if a.get("emailAddress", {}).get("address", "").lower() != config.USER_EMAIL.lower()
        ]
        briefing_eligible = required in attendee_emails

        for attendee in event.get("attendees", []):
            email_addr = attendee.get("emailAddress", {})
            attendee_email = email_addr.get("address", "")
            attendee_name = email_addr.get("name", "")

            # Skip the calendar owner
            if attendee_email.lower() == config.USER_EMAIL.lower():
                continue

            start_dt = _parse_graph_datetime(event["start"])
            end_dt = _parse_graph_datetime(event["end"])

            appointments.append(
                Appointment(
                    event_id=event["id"],
                    subject=event.get("subject", ""),
                    start_time=start_dt,
                    end_time=end_dt,
                    attendee_email=attendee_email,
                    attendee_name=attendee_name,
                    briefing_eligible=briefing_eligible,
                )
            )

    logger.info("Found %d attendees in tomorrow's appointments", len(appointments))
    return appointments


def _parse_graph_datetime(dt_obj: dict) -> datetime:
    """Parse a Graph API dateTime object into a timezone-aware datetime."""
    dt_str = dt_obj.get("dateTime", "")
    tz_str = dt_obj.get("timeZone", "UTC")

    # Graph API returns ISO format like "2026-04-22T14:30:00.0000000"
    # Truncate fractional seconds for parsing
    dt_str = re.sub(r"\.\d+$", "", dt_str)
    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")

    # Map common Graph timezone names
    tz_map = {
        "Israel Standard Time": "Asia/Jerusalem",
        "UTC": "UTC",
    }
    tz_name = tz_map.get(tz_str, tz_str)

    try:
        return dt.replace(tzinfo=ZoneInfo(tz_name))
    except KeyError:
        logger.warning("Unknown timezone '%s', defaulting to UTC", tz_str)
        return dt.replace(tzinfo=ZoneInfo("UTC"))


def normalize_phone(raw: str) -> str:
    """Normalize an Israeli phone number to WhatsApp format (digits only, 972 prefix).

    Examples:
        "054-452-2025"    → "972544522025"
        "0544522025"      → "972544522025"
        "+972544522025"   → "972544522025"
        "972-54-452-2025" → "972544522025"
    """
    digits = re.sub(r"\D", "", raw)

    # 05X-XXXXXXX format (10 digits starting with 0)
    if digits.startswith("0") and len(digits) == 10:
        return "972" + digits[1:]

    # Already has 972 prefix (12 digits)
    if digits.startswith("972") and len(digits) == 12:
        return digits

    # Fallback: return as-is (best effort)
    return digits
