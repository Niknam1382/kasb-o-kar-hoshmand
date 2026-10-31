from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from app.config import settings


class EmailServiceError(Exception):
    pass


async def send_otp_email(to_email: str, code: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = "کد تایید کسب‌وکار هوشمند"
    message.set_content(f"کد تایید شما: {code}")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
        )
    except Exception as exc:
        raise EmailServiceError(f"ارسال ایمیل ناموفق بود: {exc}") from exc
