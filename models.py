"""Data models for the appointment reminder system."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Appointment:
    """An appointment from Outlook calendar."""
    event_id: str
    subject: str
    start_time: datetime
    end_time: datetime
    attendee_email: str
    attendee_name: str


@dataclass(frozen=True)
class Lead:
    """A lead from the MySQL Leads table."""
    id: int
    first_name: str
    last_name: str
    phone: str
    email: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True)
class ReminderRecord:
    """A reminder record from the appointment_reminders table."""
    id: int
    outlook_event_id: str
    lead_id: Optional[int]
    customer_phone: str
    customer_name: str
    appointment_time: datetime
    appointment_subject: Optional[str]
    reminder_sent_at: Optional[datetime]
    whatsapp_message_id: Optional[str]
    status: str
    response_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
