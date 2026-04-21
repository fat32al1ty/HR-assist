from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core.config import settings


class EmailDeliveryError(RuntimeError):
    pass


def send_email(*, to_email: str, subject: str, body: str) -> None:
    mode = settings.auth_email_delivery_mode.lower().strip()
    if mode == "console":
        print(f"[auth-email][to={to_email}] {subject}\n{body}")
        return
    if mode != "smtp":
        raise EmailDeliveryError(
            f"Unsupported email delivery mode: {settings.auth_email_delivery_mode}"
        )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.auth_email_from
    message["To"] = to_email
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=settings.auth_email_from.split("@")[-1])
    message.set_content(body)

    try:
        if settings.auth_email_smtp_ssl:
            with smtplib.SMTP_SSL(
                settings.auth_email_smtp_host, settings.auth_email_smtp_port, timeout=10
            ) as client:
                if settings.auth_email_smtp_username:
                    client.login(
                        settings.auth_email_smtp_username, settings.auth_email_smtp_password or ""
                    )
                client.send_message(message)
            return

        with smtplib.SMTP(
            settings.auth_email_smtp_host, settings.auth_email_smtp_port, timeout=10
        ) as client:
            if settings.auth_email_smtp_starttls:
                client.starttls()
            if settings.auth_email_smtp_username:
                client.login(
                    settings.auth_email_smtp_username, settings.auth_email_smtp_password or ""
                )
            client.send_message(message)
    except Exception as error:
        raise EmailDeliveryError("Failed to deliver email") from error
