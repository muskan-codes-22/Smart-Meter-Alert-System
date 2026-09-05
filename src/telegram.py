"""Telegram Bot API notification module.

Provides a simple Telegram sender using the Bot HTTP API.
No browser or session management required — just a bot token and chat ID.
"""

from __future__ import annotations

import time as time_mod
from datetime import datetime
from typing import Optional

import requests

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
# Constants
# ---------------------------------------------------------------------------

_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"
_SEND_MESSAGE_ENDPOINT = "/sendMessage"
_TIMEOUT_REQUEST = 30  # seconds

# Retry configuration
_MAX_SEND_RETRY = 2
_RETRY_DELAY = 2.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TelegramException(Exception):
    """Base exception for Telegram API errors."""


class AuthenticationException(TelegramException):
    """Raised when bot token is invalid."""


class MessageSendException(TelegramException):
    """Raised when a message fails to send."""


# ---------------------------------------------------------------------------
# TelegramSender Class
# ---------------------------------------------------------------------------

class TelegramSender:
    """Sends messages via the Telegram Bot API.

    Uses simple HTTP requests — no browser or long-polling needed.

    Attributes:
        bot_token: Telegram bot token from @BotFather.
    """

    def __init__(self, bot_token: str) -> None:
        """Initialize the Telegram sender.

        Args:
            bot_token: Bot token from @BotFather.
        """
        if not bot_token:
            raise TelegramException("Telegram bot token is required")

        self.bot_token = bot_token
        self._base_url = _TELEGRAM_API_BASE.format(token=bot_token)
        self._session = requests.Session()

    def _api_url(self, endpoint: str) -> str:
        """Build full API URL."""
        return f"{self._base_url}{endpoint}"

    def verify_token(self) -> bool:
        """Verify the bot token is valid by calling getMe.

        Returns:
            True if token is valid.

        Raises:
            AuthenticationException: If token is invalid.
        """
        _log().info("Verifying Telegram bot token...")

        try:
            resp = self._session.get(
                self._api_url("/getMe"),
                timeout=5,
            )
            data = resp.json()

            if not data.get("ok"):
                raise AuthenticationException(
                    f"Invalid bot token: {data.get('description', 'unknown error')}"
                )

            bot_info = data.get("result", {})
            bot_name = bot_info.get("username", "unknown")
            _log().info("Bot verified: @{}", bot_name)
            return True

        except requests.RequestException as exc:
            raise TelegramException(f"Failed to verify token: {exc}") from exc

    def send_message(self, chat_id: str, message: str) -> bool:
        """Send a text message to a Telegram chat.

        Args:
            chat_id: Target chat ID (numeric or @username for channels).
            message: Message text to send (supports Markdown/HTML parse mode).

        Returns:
            True if message was sent successfully.

        Raises:
            TelegramException: If sending fails.
        """
        start_time = time_mod.perf_counter()

        if not chat_id:
            _log().error("No chat_id provided")
            return False

        _log().info("Sending message to chat_id={}", chat_id)

        for attempt in range(1, _MAX_SEND_RETRY + 1):
            try:
                resp = self._session.post(
                    self._api_url(_SEND_MESSAGE_ENDPOINT),
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                    timeout=_TIMEOUT_REQUEST,
                )
                data = resp.json()

                if data.get("ok"):
                    duration = time_mod.perf_counter() - start_time
                    _log().info(
                        "Message sent to {} in {:.2f}s",
                        chat_id,
                        duration,
                    )
                    return True

                # Handle specific error codes
                error_code = data.get("error_code", 0)
                description = data.get("description", "unknown error")

                if error_code == 400:
                    _log().error("Bad request (chat_id={}): {}", chat_id, description)
                    return False
                elif error_code == 403:
                    _log().error(
                        "Bot blocked by user or not in chat (chat_id={}): {}",
                        chat_id,
                        description,
                    )
                    return False
                elif error_code == 404:
                    _log().error("Chat not found (chat_id={})", chat_id)
                    return False

                _log().warning(
                    "Attempt {}/{} failed: {} (code={})",
                    attempt,
                    _MAX_SEND_RETRY,
                    description,
                    error_code,
                )

            except requests.RequestException as exc:
                _log().warning(
                    "Attempt {}/{} failed: {}",
                    attempt,
                    _MAX_SEND_RETRY,
                    str(exc),
                )

            if attempt < _MAX_SEND_RETRY:
                time_mod.sleep(_RETRY_DELAY)

        duration = time_mod.perf_counter() - start_time
        _log().error(
            "Failed to send message to {} after {:.2f}s",
            chat_id,
            duration,
        )
        return False

    def send_notification(self, chat_id: str, message: str) -> bool:
        """Send a notification message.

        Args:
            chat_id: Target chat ID.
            message: Notification message text.

        Returns:
            True if notification sent successfully.
        """
        return self.send_message(chat_id, message)

    def send_test_message(self, chat_id: str) -> bool:
        """Send a test message to verify the setup.

        Args:
            chat_id: Target chat ID for the test message.

        Returns:
            True if test message was sent.
        """
        test_message = (
            "SBPDCL Monitor - Test Message\n\n"
            f"Bot is working correctly!\n"
            f"Sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(chat_id, test_message)

    def close(self) -> None:
        """Close the HTTP session."""
        try:
            self._session.close()
            _log().debug("Telegram session closed")
        except Exception:
            pass

    # -------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------

    def __enter__(self) -> TelegramSender:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.close()


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

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    print("=" * 60)
    print("TELEGRAM SENDER SELF TEST")
    print("=" * 60)

    if not token:
        print("\nSet TELEGRAM_BOT_TOKEN in .env to run this test")
        sys.exit(1)

    try:
        with TelegramSender(token) as sender:
            # Test 1: Verify token
            print("\n[Test 1] Verifying bot token...")
            sender.verify_token()
            print("  Token is valid!")

            # Test 2: Send test message (if chat_id provided)
            if chat_id:
                print(f"\n[Test 2] Sending test message to {chat_id}...")
                result = sender.send_test_message(chat_id)
                if result:
                    print("  Test message sent!")
                else:
                    print("  Failed to send test message")
            else:
                print("\n[Test 2] Skipped (set TELEGRAM_CHAT_ID in .env)")

    except TelegramException as exc:
        print(f"\nError: {exc}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("TELEGRAM SENDER TEST COMPLETE")
    print("=" * 60)
