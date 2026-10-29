"""Email notification module.

Provides a fallback email sender when Telegram is blocked or unavailable.
Uses Gmail SMTP over SSL for delivery.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional

from src.logger import get_logger, log_exception

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_logger = None


def _log():
    """Get the logger, initializing on first use."""
    global _logger
    if _logger is None:
        _logger = get_logger(__name__)
    return _logger


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class EmailException(Exception):
    """Base exception for email errors."""


# ---------------------------------------------------------------------------
# EmailSender Class
# ---------------------------------------------------------------------------

class EmailSender:
    """Sends emails via Gmail SMTP.

    Attributes:
        sender_email: Gmail address used to send.
        app_password: Gmail App Password (not regular password).
        receiver_email: Target email address for notifications.
    """

    def __init__(
        self,
        sender_email: str,
        app_password: str,
        receiver_email: str,
    ) -> None:
        if not sender_email or not app_password or not receiver_email:
            raise EmailException(
                "EMAIL_ADDRESS, EMAIL_PASSWORD, and RECEIVER_EMAIL are all required"
            )

        self.sender_email = sender_email
        self.app_password = app_password
        self.receiver_email = receiver_email

    def send_alert(
        self,
        subject: str,
        body: str,
        receiver: Optional[str] = None,
        html: bool = False,
    ) -> bool:
        """Send an email alert.

        Args:
            subject: Email subject line.
            body: Email body (plain text or HTML).
            receiver: Optional override for receiver email.
            html: If True, body is treated as HTML.

        Returns:
            True if the email was sent successfully.

        Raises:
            EmailException: If sending fails.
        """
        to = receiver or self.receiver_email

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"SBPDL Bot <{self.sender_email}>"
        msg["To"] = to

        if html:
            msg.set_content(body, subtype="html")
        else:
            msg.set_content(body)

        _log().info("Sending email alert to {}", to)

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(self.sender_email, self.app_password)
                smtp.send_message(msg)

            _log().info("Email alert sent successfully to {}", to)
            return True

        except Exception as exc:
            _log().error("Failed to send email to {}: {}", to, str(exc))
            log_exception(exc, extra="email send")
            raise EmailException(f"Email send failed: {exc}") from exc

    def send_telegram_block_notification(
        self,
        consumer_name: str,
        balance: float,
        error_detail: str = "",
    ) -> bool:
        """Send a Telegram-blocked fallback email.

        Args:
            consumer_name: Consumer name for the alert.
            balance: Current balance value.
            error_detail: Additional error context from Telegram.

        Returns:
            True if email was sent successfully.
        """
        balance_display = f"-₹{abs(balance):.2f}" if balance < 0 else f"₹{balance:.2f}"
        subject = f"SBPDCL Alert - {consumer_name} - Low Balance"
        body = f"""
<html>
<body>

    <p><b>LOW BALANCE ALERT</b></p>

    <p>
        <b>Consumer:</b> {consumer_name}<br>
        <b>Balance:</b> <strong>{balance_display}</strong><br>
        <b>Action:</b> Recharge your account to avoid service disruption.
    </p>

    <p>
        Telegram notification failed.
        This email was sent as a fallback.
    </p>
</body>
</html>
"""
        return self.send_alert(subject, body, html=True)


# ---------------------------------------------------------------------------
# Self Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os
    import io
    from pathlib import Path

    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from dotenv import load_dotenv

    load_dotenv()

    sender_email = os.getenv("EMAIL_ADDRESS", "")
    app_password = os.getenv("EMAIL_PASSWORD", "")
    receiver_email = os.getenv("RECEIVER_EMAIL", "")

    print("=" * 60)
    print("EMAIL SENDER SELF TEST")
    print("=" * 60)

    if not all([sender_email, app_password, receiver_email]):
        print("\nSet EMAIL_ADDRESS, EMAIL_PASSWORD, and RECEIVER_EMAIL in .env")
        sys.exit(1)

    try:
        emailer = EmailSender(sender_email, app_password, receiver_email)
        result = emailer.send_alert(
            subject="SBPDCL Monitor - Test Email",
            body="This is a test email from SBPDCL Monitor.\n\nIf you received this, email fallback is working.",
        )
        if result:
            print("\nTest email sent successfully!")
        else:
            print("\nFailed to send test email")
    except EmailException as exc:
        print(f"\nError: {exc}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("EMAIL SENDER TEST COMPLETE")
    print("=" * 60)
