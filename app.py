"""Flask application for WhatsApp appointment reminder service."""

import logging
from functools import wraps

from flask import Flask, jsonify, request

import config
import db
from whatsapp_client import send_text_message
from message_templates import (
    build_confirm_ack,
    build_reschedule_ack,
    build_owner_reschedule_notification,
)
from scheduler import start_scheduler, scan_and_send_reminders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


def require_api_key(f):
    """Decorator to protect admin endpoints with API key."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key", "")
        if not config.REMINDER_API_KEY or api_key != config.REMINDER_API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── WhatsApp Webhook ─────────────────────────────────────────────────────────


@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """WhatsApp webhook verification (hub.challenge handshake)."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == config.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_handler():
    """Handle incoming WhatsApp messages (button clicks)."""
    # Always return 200 to WhatsApp to prevent retries
    try:
        body = request.get_json(silent=True) or {}
        _process_webhook(body)
    except Exception:
        logger.exception("Error processing webhook")
    return "OK", 200


def _process_webhook(body: dict):
    """Parse and handle a webhook payload from WhatsApp."""
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                if message.get("type") == "interactive":
                    _handle_button_reply(message)


def _handle_button_reply(message: dict):
    """Handle a button reply from a client."""
    interactive = message.get("interactive", {})
    button_reply = interactive.get("button_reply", {})
    button_id = button_reply.get("id", "")
    sender_phone = message.get("from", "")

    if not button_id:
        return

    # Parse button ID: "confirm_123" or "reschedule_123"
    parts = button_id.split("_", 1)
    if len(parts) != 2:
        logger.warning("Unknown button ID format: %s", button_id)
        return

    action, reminder_id_str = parts
    try:
        reminder_id = int(reminder_id_str)
    except ValueError:
        logger.warning("Invalid reminder ID in button: %s", button_id)
        return

    reminder = db.get_reminder_by_id(reminder_id)
    if not reminder:
        logger.warning("Reminder #%d not found", reminder_id)
        return

    # Skip if already processed (idempotent)
    if reminder["status"] in ("confirmed", "reschedule_requested"):
        logger.debug("Reminder #%d already %s, ignoring", reminder_id, reminder["status"])
        return

    if action == "confirm":
        db.update_reminder_status(reminder_id, "confirmed")
        ack = build_confirm_ack(sender_phone, reminder["appointment_time"])
        send_text_message(ack)
        logger.info("Reminder #%d confirmed by client", reminder_id)

    elif action == "reschedule":
        db.update_reminder_status(reminder_id, "reschedule_requested")

        # Send Calendly link to client
        ack = build_reschedule_ack(sender_phone)
        send_text_message(ack)

        # Notify the business owner
        notification = build_owner_reschedule_notification(
            customer_name=reminder["customer_name"],
            customer_phone=reminder["customer_phone"],
            appointment_time=reminder["appointment_time"],
            appointment_subject=reminder["appointment_subject"] or "",
        )
        send_text_message(notification)
        logger.info("Reminder #%d — client requested reschedule", reminder_id)

    else:
        logger.warning("Unknown action '%s' in button ID: %s", action, button_id)


# ── Admin API ────────────────────────────────────────────────────────────────


@app.route("/api/scan-calendar", methods=["POST"])
@require_api_key
def manual_scan():
    """Manually trigger a calendar scan."""
    count = scan_and_send_reminders()
    return jsonify({"status": "ok", "reminders_sent": count})


@app.route("/api/reminders", methods=["GET"])
@require_api_key
def list_reminders():
    """List reminders with optional filters."""
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    limit = request.args.get("limit", 50, type=int)

    reminders = db.get_reminders(
        status=status, date_from=date_from, date_to=date_to, limit=limit
    )

    # Convert datetime objects to ISO strings for JSON
    for r in reminders:
        for key in ("appointment_time", "reminder_sent_at", "response_at", "created_at", "updated_at"):
            if r.get(key) and hasattr(r[key], "isoformat"):
                r[key] = r[key].isoformat()

    return jsonify(reminders)


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    checks = {"status": "ok", "service": "whatsapp-reminders"}

    # Check DB connection
    try:
        with db.get_cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"

    return jsonify(checks)


# ── App Startup ──────────────────────────────────────────────────────────────


def create_app():
    """Application factory."""
    db.run_migration()
    start_scheduler()
    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=config.PORT, debug=False)
