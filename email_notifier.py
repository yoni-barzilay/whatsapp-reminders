"""Email notifications via Microsoft Graph API for invalid phone alerts."""

import logging

import requests

import config
from outlook_client import _get_access_token

logger = logging.getLogger(__name__)

# Track notified leads per process lifecycle to avoid spamming
_notified_leads: set[int] = set()

NOTIFICATION_EMAIL = "yoni@safeshare.co.il"


def notify_invalid_phone(
    lead_id: int,
    lead_name: str,
    lead_email: str,
    raw_phone: str,
    appointment_subject: str = "",
) -> bool:
    """Send an email to NOTIFICATION_EMAIL about an invalid phone number.

    Returns True if email was sent, False if skipped or failed.
    Deduplicates within the same process lifecycle.
    """
    if lead_id in _notified_leads:
        logger.debug("Already notified about lead %d invalid phone, skipping", lead_id)
        return False

    subject = f"WhatsApp Reminder - Invalid phone for lead #{lead_id}"
    body = (
        f"<div dir='rtl' style='font-family: Arial, sans-serif;'>"
        f"<h3>Invalid Phone Number Detected</h3>"
        f"<p>A calendar appointment was found but the WhatsApp reminder could not be sent "
        f"because the lead's phone number is invalid.</p>"
        f"<table style='border-collapse: collapse; margin-top: 10px;'>"
        f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Lead ID:</td>"
        f"<td style='padding: 4px 0;'>{lead_id}</td></tr>"
        f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Name:</td>"
        f"<td style='padding: 4px 0;'>{lead_name}</td></tr>"
        f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Email:</td>"
        f"<td style='padding: 4px 0;'>{lead_email}</td></tr>"
        f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Phone (raw):</td>"
        f"<td style='padding: 4px 0; direction: ltr;'>{raw_phone}</td></tr>"
        f"<tr><td style='padding: 4px 12px 4px 0; font-weight: bold;'>Meeting:</td>"
        f"<td style='padding: 4px 0;'>{appointment_subject or 'N/A'}</td></tr>"
        f"</table>"
        f"<p style='margin-top: 16px; color: #666;'>Please update the phone number in "
        f"the CRM (Leads table, ID {lead_id}) so future reminders can be sent.</p>"
        f"</div>"
    )

    try:
        token = _get_access_token()
    except Exception:
        logger.exception("Failed to get token for email notification")
        return False

    sender = config.USER_EMAIL  # first configured mailbox
    url = f"{config.GRAPH_API_URL}/users/{sender}/sendMail"

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "toRecipients": [
                {"emailAddress": {"address": NOTIFICATION_EMAIL}}
            ],
        },
        "saveToSentItems": False,
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        _notified_leads.add(lead_id)
        logger.info(
            "Email notification sent for lead #%d (invalid phone '%s')",
            lead_id, raw_phone,
        )
        return True
    except requests.HTTPError as exc:
        logger.error(
            "Failed to send email notification for lead #%d: %s %s",
            lead_id, exc, exc.response.text if exc.response else "",
        )
        return False
    except Exception:
        logger.exception("Failed to send email notification for lead #%d", lead_id)
        return False
