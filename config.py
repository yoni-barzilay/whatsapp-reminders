"""
Configuration for WhatsApp Appointment Reminder Service.

Azure AD Setup Guide:
  1. Go to https://portal.azure.com → Azure Active Directory → App registrations → New
  2. Name: "SafeShare Calendar Reader", Supported account types: Single tenant
  3. Copy: Application (client) ID → AZURE_CLIENT_ID
  4. Copy: Directory (tenant) ID → AZURE_TENANT_ID
  5. Go to Certificates & secrets → New client secret → copy value → AZURE_CLIENT_SECRET
  6. Go to API permissions → Add permission → Microsoft Graph → Application permissions
  7. Add: Calendars.Read → Click "Grant admin consent for [your org]"
  8. Set all env vars below (or use a .env file)
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """Raised when a required environment variable is missing."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


# WhatsApp Business API
WHATSAPP_TOKEN: str = _require("WHATSAPP_TOKEN")
PHONE_NUMBER_ID: str = _require("PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN: str = _require("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_API_URL: str = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

# Microsoft Graph API (Outlook Calendar)
AZURE_CLIENT_ID: str = _require("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET: str = _require("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID: str = _require("AZURE_TENANT_ID")
USER_EMAIL: str = _require("USER_EMAIL")
GRAPH_API_URL: str = "https://graph.microsoft.com/v1.0"

# MySQL Database (reuse safeshare-chat's DB)
MYSQL_HOST: str = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT: int = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER: str = os.environ.get("MYSQL_USER", "root")
MYSQL_PASS: str = os.environ.get("MYSQL_PASS", "")
MYSQL_DB: str = os.environ.get("MYSQL_DB", "safeshare")

# Application
REMINDER_API_KEY: str = os.environ.get("REMINDER_API_KEY", "")
PORT: int = int(os.environ.get("PORT", "5002"))
SCHEDULER_HOUR: int = int(os.environ.get("SCHEDULER_HOUR", "9"))
SCHEDULER_MINUTE: int = int(os.environ.get("SCHEDULER_MINUTE", "0"))
TIMEZONE: str = "Asia/Jerusalem"

# Booking / Reschedule
BOOKING_URL: str = os.environ.get("BOOKING_URL", "https://calendly.com/safeshare/30min")

# Your number for reschedule notifications (digits only, no +)
MY_WHATSAPP_NUMBER: str = os.environ.get("MY_WHATSAPP_NUMBER", "972555537434")

# Only process meetings that include this attendee
REQUIRED_ATTENDEE: str = os.environ.get("REQUIRED_ATTENDEE", "asi@safeshare.co.il")
