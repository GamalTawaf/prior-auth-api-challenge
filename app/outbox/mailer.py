"""stdlib SMTP send; no-op when SMTP_HOST is empty (tests / local without MailDev)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings


def send_smtp(to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as client:
        client.send_message(msg)
