import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
from datetime import datetime, timezone
from typing import Optional
from celery import shared_task
from sqlalchemy import delete, select



from src.config.settings import settings
from src.database.session import AsyncSessionLocal, engine
from src.database.models.users import ActivationTokenModel, UserModel
from src.database.models.movie_interactions import NotificationEnum, UserNotification


@shared_task(name="debug_task")
def debug_task(message: str):
    print(f"Celery task executed with message: {message}")
    return f"Done: {message}"


def run_async(coro):
    """Function to safely start async function inside Celery worker"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)


#HELPER FUNCTION FOR ALL EMAIL SENDING STUFF
async def send_async_email(to_email: str, subject: str, html_content: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=False,
    )

# --- 1. PASSWORD RESET AND ACTIVATION ---
async def _async_send_password_reset_email(email: str, password_reset_url: str):
    html = f"""
    <html>
        <body>
            <p>Here is your password reset link below:</p>
            <a href="{password_reset_url}">Reset Password</a>
        </body>
    </html>
    """
    await send_async_email(email, "Password reset - Online Cinema", html)
    return f"Email sent successfully to {email}"


@shared_task(name="send_password_reset_email", bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, email: str, password_reset_url: str):
    try:
        return run_async(_async_send_password_reset_email(email, password_reset_url))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _async_send_activation_email(email: str, activation_url: str):
    html = f"""
    <html>
        <body>
            <p>Welcome! Please activate your account by clicking the link below:</p>
            <a href="{activation_url}">Activate Account</a>
        </body>
    </html>
    """
    await send_async_email(email, "Account activation - Online Cinema", html)
    return f"Email sent successfully to {email}"


@shared_task(name="send_activation_email", bind=True, max_retries=3, default_retry_delay=60)
def send_activation_email(self, email: str, activation_url: str):
    try:
        return run_async(_async_send_activation_email(email, activation_url))
    except Exception as exc:
        raise self.retry(exc=exc)


# --- 2. TOKEN CLEANUP ---
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


@shared_task(name="cleanup_expired_tokens_task")
def cleanup_expired_tokens_task() -> str:
    return run_async(_async_cleanup_expired_tokens())


# --- 3. NOTIFICATIONS (Like / Reply / Release) ---
async def _async_create_and_send_notification(
    user_id: int,
    notification_type: str,
    movie_comment_id: Optional[int] = None,
    movie_id: Optional[int] = None,
    extra_text: str = "",
):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()

            if not user or not user.email:
                return f"User {user_id} not found or has no email"

            notification = UserNotification(
                user_id=user_id,
                notification_type=NotificationEnum(notification_type),
                movie_comment_id=movie_comment_id,
                movie_id=movie_id,
                is_read=False
            )
            session.add(notification)
            await session.commit()

            subject = ""
            html_content = ""

            if notification_type == NotificationEnum.COMMENT_REPLY.value:
                subject = "New reply to your comment — Online Cinema"
                html_content = f"<p>Your comment got a new reply:</p><p><b>{extra_text}</b></p>"

            elif notification_type == NotificationEnum.COMMENT_LIKE.value:
                subject = "Your comment received a like! — Online Cinema"
                username = extra_text or "Another user"
                html_content = f"<p>{username} liked your comment</p>"

            elif notification_type == NotificationEnum.NEW_RELEASE.value:
                subject = "New release! — Online Cinema"
                html_content = f"<h3>Meet a new movie</h3><p>{extra_text}</p>"

            await send_async_email(user.email, subject, html_content)
            return f"Notification created and email sent to {user.email}"

        except Exception as exc:
            await session.rollback()
            raise exc


@shared_task(name="create_and_send_notification", bind=True, max_retries=3, default_retry_delay=60)
def create_and_send_notification(
    self,
    user_id: int,
    notification_type: str,
    movie_comment_id: Optional[int] = None,
    movie_id: Optional[int] = None,
    extra_text: str = "",
):
    try:
        return run_async(
            _async_create_and_send_notification(
                user_id, notification_type, movie_comment_id, movie_id, extra_text
            )
        )
    except Exception as exc:
        raise self.retry(exc=exc)


# --- 4. BATCHING RELEASE ---
async def _async_notify_users_about_new_release(movie_id: int, movie_title: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel.id))
        user_ids = result.scalars().all()

        for u_id in user_ids:
            create_and_send_notification.delay(
                user_id=u_id,
                notification_type=NotificationEnum.NEW_RELEASE.value,
                movie_id=movie_id,
                extra_text=f"Movie '{movie_title}' is already at our digital shelf's!"
            )
        return f"Pushed release notifications for {len(user_ids)} users to Queue."


@shared_task(name="notify_all_about_new_movie")
def notify_users_about_new_release(movie_id: int, movie_title: str):
    return run_async(_async_notify_users_about_new_release(movie_id, movie_title))
