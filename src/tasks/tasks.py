import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.celery_app import celery_app
from src.config.settings import settings

@celery_app.task
def debug_task(message: str):
    print(f"Celery task executed with message: {message}")
    return f"Done: {message}"



@celery_app.task
def send_activation_email(email: str, activation_url: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Account activation - Online Cinema"
    msg["From"] = settings.SMTP_USER
    msg["To"] = email

    html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h2>Welcome to Online Cinema!</h2>
            <p>To activate your account use link below:</p>
            <a href="{activation_url}" style="display: inline-block; padding: 10px 20px; background-color: #e50914; color: white; text-decoration: none; border-radius: 5px;">
                Activate account
            </a>
          </body>
        </html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USER != "mock_user":
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, email, msg.as_string())
        return f"Email sent successfully to {email}"
    except Exception as e:
        return f"Failed to send email to {email}. Error: {str(e)}"
