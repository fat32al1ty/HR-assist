from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core.config import settings

logger = logging.getLogger("auth_email")


class EmailDeliveryError(RuntimeError):
    pass


def _redact_email(address: str) -> str:
    """Mask the local part of an email for log lines.

    Keeps enough signal to debug ('a***@example.com') without exposing the
    full identity to anyone who can read container logs.
    """
    if "@" not in address:
        return "***"
    local, _, domain = address.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def send_email(*, to_email: str, subject: str, body: str) -> None:
    mode = settings.auth_email_delivery_mode.lower().strip()
    if mode == "console":
        # Never log the OTP code itself at INFO — only the fact that we would
        # have delivered it. The raw body is behind DEBUG for local dev.
        logger.info(
            "auth_email_console to=%s subject=%s body_len=%d",
            _redact_email(to_email),
            subject,
            len(body or ""),
        )
        logger.debug("auth_email_console_body to=%s body=%s", to_email, body)
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
            logger.info(
                "auth_email_sent to=%s subject=%s transport=smtps",
                _redact_email(to_email),
                subject,
            )
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
        logger.info(
            "auth_email_sent to=%s subject=%s transport=smtp",
            _redact_email(to_email),
            subject,
        )
    except Exception as error:
        logger.warning(
            "auth_email_failed to=%s subject=%s error=%s",
            _redact_email(to_email),
            subject,
            type(error).__name__,
        )
        raise EmailDeliveryError("Failed to deliver email") from error
