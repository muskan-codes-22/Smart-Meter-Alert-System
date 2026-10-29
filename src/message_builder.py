"""Message builder module for multi-language notifications.

Provides centralized message templates for all supported languages.
To add a new language, add a new template dictionary and update the
MESSAGES mapping.
"""

from __future__ import annotations

from typing import Any

from src.config import ConsumerConfig


# ---------------------------------------------------------------------------
# Message Templates
# ---------------------------------------------------------------------------

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "title": "<b>\u26a1 SBPDCL Balance Alert</b>",
        "greeting": "Dear Consumer,",
        "body": "Your smart meter balance is running low.",
        "ca_label": "CA Number",
        "balance_label": "Available Balance",
        "action": (
            "<b>\u26a0\ufe0f Please recharge your smart meter at the earliest to avoid "
            "interruption in electricity supply.</b>"
        ),
        "footer": "\u2014 SBPDCL Monitor",
    },
    "hi": {
        "title": "<b>⚡ एसबीपीडीसीएल बैलेंस अलर्ट</b>",
        "greeting": "प्रिय उपभोक्ता,",
        "body": "आपके स्मार्ट मीटर का बैलेंस कम हो गया है।",
        "ca_label": "सीए नंबर",
        "balance_label": "उपलब्ध बैलेंस",
        "action": (
            "<b>⚠️ कृपया बिजली आपूर्ति बाधित होने से बचने के लिए "
            "जल्द से जल्द रिचार्ज कर लें।</b>"
        ),
        "footer": "— SBPDCL Monitor",
    },
}

SUPPORTED_LANGUAGES = tuple(_MESSAGES.keys())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_notification_message(
    consumer: ConsumerConfig,
    balance: float,
) -> str:
    """Build a low-balance notification message.

    Args:
        consumer: Consumer configuration (provides name, ca, language).
        balance: Current available balance in rupees.

    Returns:
        Formatted notification message string.
    """
    lang = consumer.language if consumer.language in _MESSAGES else "en"
    t = _MESSAGES[lang]
    balance_display = f"-₹{abs(balance):.2f}" if balance < 0 else f"₹{balance:.2f}"

    return (
        f"{t['title']}\n\n"
        f"{t['greeting']}\n\n"
        f"{t['body']}\n\n"
        f"{t['ca_label']}: {consumer.ca}\n"
        f"{t['balance_label']}: <b>{balance_display}</b>\n\n"
        f"{t['action']}\n\n"
        f"{t['footer']}"
    )


# ---------------------------------------------------------------------------
# Self Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import io

    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    from src.config import ConsumerConfig

    print("=" * 50)
    print("MESSAGE BUILDER SELF TEST")
    print("=" * 50)

    # Test English
    en_consumer = ConsumerConfig(
        name="Test EN",
        ca="1234567890",
        threshold=1000,
        chat_id="123456789",
        language="en",
    )
    print("\n[English]")
    print(build_notification_message(en_consumer, 568.07))

    # Test Hindi
    hi_consumer = ConsumerConfig(
        name="Test HI",
        ca="1234567890",
        threshold=1000,
        chat_id="123456789",
        language="hi",
    )
    print("\n[Hindi]")
    print(build_notification_message(hi_consumer, 568.07))

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)
