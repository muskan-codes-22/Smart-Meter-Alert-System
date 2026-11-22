"""Unit tests for balance parsing, formatting, and notification logic."""

import pytest
from src.utils import format_currency, parse_balance_string, is_valid_balance
from src.message_builder import build_notification_message
from src.config import ConsumerConfig
from src.state import NotificationStateManager


class TestBalanceParsing:
    """Test suite for parsing electricity balance strings."""

    def test_parse_negative_balance_with_rupee(self):
        # Format seen on SBPDCL portal
        assert parse_balance_string("-₹269.51") == -269.51
        assert parse_balance_string(" -₹269.51 ") == -269.51

    def test_parse_negative_balance_rupee_first(self):
        assert parse_balance_string("₹-269.51") == -269.51
        assert parse_balance_string("₹ -269.51") == -269.51

    def test_parse_negative_balance_spaced(self):
        assert parse_balance_string("- ₹ 269.51") == -269.51
        assert parse_balance_string("- 269.51") == -269.51

    def test_parse_negative_balance_unicode_minuses(self):
        # Unicode minus U+2212, en-dash U+2013, em-dash U+2014
        assert parse_balance_string("−₹269.51") == -269.51
        assert parse_balance_string("–₹269.51") == -269.51
        assert parse_balance_string("—₹269.51") == -269.51

    def test_parse_positive_balance(self):
        assert parse_balance_string("₹568.07") == 568.07
        assert parse_balance_string("568.07") == 568.07
        assert parse_balance_string("₹ 1,000.00") == 1000.0
        assert parse_balance_string("0.00") == 0.0

    def test_parse_non_balance_strings(self):
        assert parse_balance_string("") is None
        assert parse_balance_string(None) is None
        assert parse_balance_string("Connected") is None
        assert parse_balance_string("Available Balance(Rs)") is None


class TestCurrencyFormatting:
    """Test currency formatting."""

    def test_positive_currency(self):
        assert format_currency(568.07) == "₹568.07"
        assert format_currency(1000.0) == "₹1,000.00"

    def test_negative_currency(self):
        assert format_currency(-269.51) == "-₹269.51"
        assert format_currency(-1000.0) == "-₹1,000.00"

    def test_zero_currency(self):
        assert format_currency(0.0) == "₹0.00"


class TestValidation:
    """Test balance validation."""

    def test_valid_balances(self):
        assert is_valid_balance(100.5) is True
        assert is_valid_balance(-269.51) is True
        assert is_valid_balance("0") is True
        assert is_valid_balance("-10") is True

    def test_invalid_balances(self):
        assert is_valid_balance("abc") is False
        assert is_valid_balance(None) is False
        assert is_valid_balance(True) is False


class TestNotificationMessages:
    """Test notification message building with negative balances."""

    def test_negative_balance_message_en(self):
        consumer = ConsumerConfig(
            name="Test Consumer",
            ca="241111117048",
            threshold=100.0,
            chat_id="12345",
            language="en",
        )
        msg = build_notification_message(consumer, -269.51)
        assert "-₹269.51" in msg
        assert "241111117048" in msg

    def test_negative_balance_message_hi(self):
        consumer = ConsumerConfig(
            name="Test Consumer",
            ca="241111117048",
            threshold=100.0,
            chat_id="12345",
            language="hi",
        )
        msg = build_notification_message(consumer, -269.51)
        assert "-₹269.51" in msg


class TestStateTransitions:
    """Test notification state manager handling of negative balances."""

    def test_drop_to_negative_balance_triggers_notification(self, tmp_path):
        state_file = tmp_path / "notified.json"
        manager = NotificationStateManager(state_file)

        # Previously positive balance 269.51 above threshold 100.0
        manager.update_state("Local Shop", 269.51, 100.0, notification_sent=False)

        # Now balance drops to -269.51
        should_notify = manager.should_send_notification("Local Shop", -269.51, 100.0)
        assert should_notify is True

    def test_positive_below_threshold_to_negative_triggers_notification(self, tmp_path):
        state_file = tmp_path / "notified.json"
        manager = NotificationStateManager(state_file)

        # Previously below threshold 50.0 (below 100.0), already notified
        manager.update_state("Local Shop", 50.0, 100.0, notification_sent=True)

        # Now balance drops below 0 to -269.51
        should_notify = manager.should_send_notification("Local Shop", -269.51, 100.0)
        assert should_notify is True


class TestPageTextExtraction:
    """Test regex extraction patterns used in SBPDCLChecker against portal HTML/text."""

    def test_extract_negative_balance_from_portal_text(self):
        sample_page_text = """
Consumer Details
CA Number: 241111117048
Name: REKHA DEVI
Division: JAGDISHPUR
Sub Division: JAGDISHPUR
Last Recharge Date: 15-10-2026 20:00:34 PM
Last Recharge Amount: ₹1,000.00
Consumer Type: Prepaid
Latest Bill: View Bill
AMISP Vendor: EESL
Current Balance Details
Current Status: Connected
Available Balance(Rs) -₹269.51
AMISP Vendor: EESL
"""
        import re
        normalized = sample_page_text.replace("\u2212", "-")
        pat = r"Available\s+Balance\s*(?:\(Rs\))?\s*:?\s*(-)?\s*(?:[₹]|Rs\.?|INR)?\s*(-)?\s*(\d[\d,]*(?:\.\d+)?)"
        match = re.search(pat, normalized, re.IGNORECASE)
        assert match is not None
        amount = float(match.group(3).replace(",", ""))
        is_negative = bool(match.group(1) or match.group(2))
        balance = -amount if is_negative else amount
        assert balance == -269.51
