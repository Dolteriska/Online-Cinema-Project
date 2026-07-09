import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import delete

from src.config.settings import settings
from src.database.session import AsyncSessionLocal, engine
from src.database.models.users import ActivationTokenModel


@shared_task(name="debug_task")
def debug_task(message: str):
    print(f"Celery task executed with message: {message}")
    return f"Done: {message}"

async def _async_send_password_reset_email(email: str, password_reset_url: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Password reset - Online Cinema"
    msg["From"] = settings.SMTP_USER
    msg["To"] = email
    html = f"""
    <html>
        <body>
            <p>Here is your password reset link below:</p>
            <a href="{password_reset_url}">Reset Password</a>
        </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=False,
        )
        return f"Email sent successfully to {email}"
    except Exception as e:
        return f"Failed to send email to {email}. Error: {str(e)}"

@shared_task(name="send_password_reset_email")
def send_password_reset_email(email: str, password_reset_url: str):
    return asyncio.run(_async_send_password_reset_email(email, password_reset_url))


async def _async_send_activation_email(email: str, activation_url: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Account activation - Online Cinema"
    msg["From"] = settings.SMTP_USER
    msg["To"] = email

    html = f"""
    <html>
        <body>
            <p>Welcome! Please activate your account by clicking the link below:</p>
            <a href="{activation_url}">Activate Account</a>
        </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=False,
        )
        return f"Email sent successfully to {email}"
    except Exception as e:
        return f"Failed to send email to {email}. Error: {str(e)}"

@shared_task(name="send_activation_email")
def send_activation_email(email: str, activation_url: str):
    return asyncio.run(_async_send_activation_email(email, activation_url))


@shared_task(name="cleanup_expired_tokens_task")
def cleanup_expired_tokens_task():
    return asyncio.run(_async_cleanup_wrapper())

async def _async_cleanup_wrapper() -> str:
    try:
        return await _async_cleanup_expired_tokens()
    finally:
        await engine.dispose()

async def _async_cleanup_expired_tokens() -> str:
    now_utc = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        try:
            stmt = delete(ActivationTokenModel).where(ActivationTokenModel.expires_at < now_utc)
            result = await db.execute(stmt)
            await db.commit()
            return f"Successfully deleted {result.rowcount} expired activation tokens"
        except Exception as e:
            await db.rollback()
            return f"Failed to auto-clean expired tokens. Error: {str(e)}"
