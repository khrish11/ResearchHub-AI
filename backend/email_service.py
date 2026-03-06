import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from jinja2 import Template
from models import User
from sqlalchemy.orm import Session

try:
    from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
except Exception:  # pragma: no cover - optional dependency in local/dev
    FastMail = None  # type: ignore[assignment]
    MessageSchema = None  # type: ignore[assignment]
    ConnectionConfig = None  # type: ignore[assignment]

MAIL_USERNAME = os.getenv("MAIL_USERNAME", "").strip()
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").strip()
MAIL_FROM = os.getenv("MAIL_FROM", "noreply@researchhub.ai").strip() or "noreply@researchhub.ai"
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com").strip() or "smtp.gmail.com"
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))

MAIL_ENABLED = bool(
    FastMail
    and ConnectionConfig
    and MessageSchema
    and MAIL_USERNAME
    and MAIL_PASSWORD
    and MAIL_FROM
)

if MAIL_ENABLED:
    conf = ConnectionConfig(
        MAIL_USERNAME=MAIL_USERNAME,
        MAIL_PASSWORD=MAIL_PASSWORD,
        MAIL_FROM=MAIL_FROM,
        MAIL_PORT=MAIL_PORT,
        MAIL_SERVER=MAIL_SERVER,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    fm = FastMail(conf)
else:
    conf = None
    fm = None

def generate_verification_token() -> str:
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)

def get_verification_token_expiry() -> datetime:
    """Get the expiry time for verification tokens (24 hours from now)."""
    return datetime.utcnow() + timedelta(hours=24)

async def send_verification_email(email: str, token: str, user_name: Optional[str] = None):
    """Send email verification email to user."""
    if not MAIL_ENABLED or not fm or not MessageSchema:
        logging.getLogger(__name__).info("Email sending skipped (mail service not configured).")
        return

    verification_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/verify-email?token={token}"

    # Email template
    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verify Your Email - Soyog AI</title>
        <style>
            body { font-family: 'Space Grotesk', sans-serif; margin: 0; padding: 0; background-color: #f6f8ff; }
            .container { max-width: 600px; margin: 0 auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }
            .header { background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 40px 30px; text-align: center; color: white; }
            .content { padding: 40px 30px; color: #334155; line-height: 1.6; }
            .button { display: inline-block; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }
            .footer { background-color: #f8fafc; padding: 20px 30px; text-align: center; color: #64748b; font-size: 14px; }
            .code { background-color: #f1f5f9; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 18px; font-weight: bold; color: #475569; margin: 20px 0; text-align: center; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Verify Your Email</h1>
                <p>Welcome to Soyog AI</p>
            </div>
            <div class="content">
                <h2>Hello{{ name and ' ' + name or '' }}!</h2>
                <p>Thank you for signing up for Soyog AI. To complete your registration and start building your research workflow, please verify your email address.</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ verification_url }}" class="button">Verify Email Address</a>
                </div>

                <p>If the button above doesn't work, you can copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #6366f1; font-size: 14px;">{{ verification_url }}</p>

                <p><strong>This verification link will expire in 24 hours.</strong></p>

                <p>If you didn't create an account with Soyog AI, you can safely ignore this email.</p>

                <p>Best regards,<br>The Soyog AI Team</p>
            </div>
            <div class="footer">
                <p>This email was sent to {{ email }}. If you have any questions, please contact our support team.</p>
                <p>&copy; 2024 Soyog AI. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """)

    html_content = template.render(
        name=user_name,
        email=email,
        verification_url=verification_url
    )

    message = MessageSchema(
        subject="Verify Your Email - Soyog AI",
        recipients=[email],
        body=html_content,
        subtype="html"
    )

    await fm.send_message(message)

async def send_password_reset_email(email: str, token: str, user_name: Optional[str] = None):
    """Send password reset email to user."""
    if not MAIL_ENABLED or not fm or not MessageSchema:
        logging.getLogger(__name__).info("Password reset email skipped (mail service not configured).")
        return

    reset_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/reset-password?token={token}"

    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reset Your Password - Soyog AI</title>
        <style>
            body { font-family: 'Space Grotesk', sans-serif; margin: 0; padding: 0; background-color: #f6f8ff; }
            .container { max-width: 600px; margin: 0 auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }
            .header { background: linear-gradient(135deg, #ef4444, #dc2626); padding: 40px 30px; text-align: center; color: white; }
            .content { padding: 40px 30px; color: #334155; line-height: 1.6; }
            .button { display: inline-block; background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 12px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }
            .footer { background-color: #f8fafc; padding: 20px 30px; text-align: center; color: #64748b; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Reset Your Password</h1>
                <p>Secure your Soyog AI account</p>
            </div>
            <div class="content">
                <h2>Hello{{ name and ' ' + name or '' }}!</h2>
                <p>We received a request to reset your password for your Soyog AI account. Click the button below to create a new password.</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ reset_url }}" class="button">Reset Password</a>
                </div>

                <p>If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>

                <p><strong>This reset link will expire in 1 hour.</strong></p>

                <p>Best regards,<br>The Soyog AI Team</p>
            </div>
            <div class="footer">
                <p>This email was sent to {{ email }}. If you have any questions, please contact our support team.</p>
                <p>&copy; 2024 Soyog AI. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """)

    html_content = template.render(
        name=user_name,
        email=email,
        reset_url=reset_url
    )

    message = MessageSchema(
        subject="Reset Your Password - Soyog AI",
        recipients=[email],
        body=html_content,
        subtype="html"
    )

    await fm.send_message(message)

def verify_email_token(db: Session, token: str) -> Optional[User]:
    """Verify email verification token and return user if valid."""
    user = db.query(User).filter(
        User.verification_token == token,
        User.verification_token_expires > datetime.utcnow(),
        User.is_active == True
    ).first()

    if user:
        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires = None
        db.commit()
        db.refresh(user)

    return user
