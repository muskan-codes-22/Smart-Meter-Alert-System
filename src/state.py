"""Notification state management module.

Prevents duplicate notifications by tracking the notification
state for each consumer. Persists state between program executions
using data/notified.json.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Logger (lazy initialization to avoid import issues during self-test)
# ---------------------------------------------------------------------------

_logger = None


def _log():
    """Get the logger, initializing on first use."""
    global _logger
    if _logger is None:
        from src.logger import get_logger
        _logger = get_logger(__name__)
    return _logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "notified.json"
_BACKUP_SUFFIX = "_backup.json"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class StateError(Exception):
    """Raised when state operations fail."""


# ---------------------------------------------------------------------------
# NotificationStateManager Class
# ---------------------------------------------------------------------------

class NotificationStateManager:
    """Manages notification state to prevent duplicate alerts.

    Tracks when notifications were last sent for each consumer and
    decides whether a new notification should be sent based on
    balance threshold changes.

    Attributes:
        state_file: Path to the state JSON file.
    """

    def __init__(self, state_file: Optional[Path] = None) -> None:
        """Initialize the state manager and load existing state.

        Args:
            state_file: Optional custom path to the state file.
                        Defaults to data/notified.json.
        """
        self.state_file = state_file or _STATE_FILE
        self._state: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        """Load state from the JSON file.

        If the file doesn't exist, creates it with an empty state.
        If the file is corrupted, backs it up and starts fresh.
        """
        _log().debug("Loading state from {}", self.state_file)

        if not self.state_file.exists():
            _log().info("State file not found, creating new state")
            self._state = {}
            self.save()
            return

        try:
            with self.state_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both formats: direct dict or wrapped in "last_notified"
            if isinstance(data, dict):
                if "last_notified" in data and isinstance(data["last_notified"], dict):
                    self._state = data["last_notified"]
                else:
                    self._state = data
            else:
                raise StateError("Invalid state file format")

            _log().info(
                "State loaded successfully ({} consumers tracked)",
                len(self._state),
            )

        except (json.JSONDecodeError, StateError, KeyError) as exc:
            _log().warning("State file corrupted: {}, creating backup", str(exc))
            self._backup_corrupted_file()
            self._state = {}
            self.save()

    def save(self) -> None:
        """Save state to the JSON file atomically.

        Writes to a temporary file first, then replaces the original
        to prevent corruption.
        """
        _log().debug("Saving state to {}", self.state_file)

        # Ensure data directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Wrap in the expected format
        data_to_write = {"last_notified": self._state}

        try:
            # Write to temporary file in the same directory
            fd, tmp_path = tempfile.mkstemp(
                dir=self.state_file.parent,
                suffix=".tmp",
                prefix="notified_",
            )

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data_to_write, f, indent=2, ensure_ascii=False)

                # Atomic replace
                os.replace(tmp_path, self.state_file)
                _log().debug("State saved successfully")

            except Exception:
                # Clean up temporary file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        except Exception as exc:
            _log().error("Failed to save state: {}", str(exc))
            raise StateError(f"Failed to save state: {exc}") from exc

    def get_state(self, consumer_name: str) -> Dict[str, Any]:
        """Get the notification state for a consumer.

        Args:
            consumer_name: Name of the consumer.

        Returns:
            Dictionary with notification state, or empty defaults.
        """
        return self._state.get(
            consumer_name,
            {
                "last_notification": None,
                "last_balance": None,
                "is_below_threshold": False,
            },
        )

    def update_state(
        self,
        consumer_name: str,
        balance: float,
        threshold: float,
        notification_sent: bool = False,
    ) -> None:
        """Update the state for a consumer.

        Args:
            consumer_name: Name of the consumer.
            balance: Current balance value.
            threshold: Current threshold value.
            notification_sent: Whether a notification was just sent.
        """
        now = datetime.now().isoformat()

        was_below = self._state.get(consumer_name, {}).get("is_below_threshold", False)

        self._state[consumer_name] = {
            "last_notification": now if notification_sent else (
                self._state.get(consumer_name, {}).get("last_notification")
            ),
            "last_balance": balance,
            "threshold": threshold,
            # Only mark as "below threshold" (notified) if notification was sent
            # or it was already marked as below. This ensures we retry if send failed.
            "is_below_threshold": (balance < threshold) and (notification_sent or was_below),
        }

        self.save()
        _log().debug(
            "State updated for {}: balance={}, notification_sent={}",
            consumer_name,
            balance,
            notification_sent,
        )

    def should_send_notification(
        self,
        consumer_name: str,
        current_balance: float,
        threshold: float,
    ) -> bool:
        """Determine whether a notification should be sent.

        Rules:
        - Case 1: Previous above threshold, current below → True
        - Case 2: Previous below, current still below → False
        - Case 3: Previous below, current above → False (recovered)
        - Case 4: First time user → True (if below threshold)

        Args:
            consumer_name: Name of the consumer.
            current_balance: Current balance value.
            threshold: Low balance threshold.

        Returns:
            True if notification should be sent, False otherwise.
        """
        state = self.get_state(consumer_name)
        prev_balance = state.get("last_balance")
        prev_below = state.get("is_below_threshold", False)
        current_below = current_balance < threshold

        # Case 4: First time user - notify if below threshold
        if prev_balance is None:
            _log().info(
                "First time checking {}: balance={}, below_threshold={}",
                consumer_name,
                current_balance,
                current_below,
            )
            if current_below:
                _log().info("Notification required (first time, below threshold)")
                return True
            else:
                _log().info("Notification not required (first time, above threshold)")
                return False

        # Case 1: Transition from above to below threshold
        if not prev_below and current_below:
            _log().info(
                "Notification required: {} went from above to below threshold",
                consumer_name,
            )
            return True

        # Case 2: Still below threshold (already notified)
        if prev_below and current_below:
            _log().info(
                "Notification skipped: {} still below threshold (already notified)",
                consumer_name,
            )
            return False

        # Case 3: Recovery - went from below to above threshold
        if prev_below and not current_below:
            _log().info(
                "Notification skipped: {} recovered above threshold",
                consumer_name,
            )
            # Update state to reflect recovery
            self._state[consumer_name] = {
                "last_notification": state.get("last_notification"),
                "last_balance": current_balance,
                "threshold": threshold,
                "is_below_threshold": False,
            }
            self.save()
            return False

        # Above threshold, no change needed
        _log().info(
            "Notification skipped: {} above threshold (no change)",
            consumer_name,
        )
        return False

    def clear_state(self, consumer_name: str) -> None:
        """Clear the state for a specific consumer.

        Args:
            consumer_name: Name of the consumer to clear.
        """
        if consumer_name in self._state:
            del self._state[consumer_name]
            self.save()
            _log().info("State cleared for {}", consumer_name)
        else:
            _log().debug("No state found for {}", consumer_name)

    def reset_all(self) -> None:
        """Reset all notification states.

        Clears the entire state file.
        """
        self._state = {}
        self.save()
        _log().info("All notification states reset")

    def _backup_corrupted_file(self) -> None:
        """Backup a corrupted state file."""
        if self.state_file.exists():
            backup_path = self.state_file.with_suffix(_BACKUP_SUFFIX)
            try:
                self.state_file.rename(backup_path)
                _log().info("Corrupted state backed up to {}", backup_path)
            except Exception as exc:
                _log().warning(
                    "Failed to backup corrupted state: {}", str(exc)
                )

    def __repr__(self) -> str:
        """String representation showing tracked consumers."""
        consumers = list(self._state.keys())
        return f"NotificationStateManager(consumers={consumers})"


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

    # Add parent directory to path for self-test
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from src.models import Consumer

    print("=" * 60)
    print("NOTIFICATION STATE MANAGER SELF TEST")
    print("=" * 60)

    # Create temporary state file for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        test_state_file = Path(tmpdir) / "test_notified.json"

        manager = NotificationStateManager(state_file=test_state_file)

        # Create dummy consumer
        consumer = Consumer(
            name="Home",
            ca="1234567890",
            threshold=100.0,
            chat_id="123456789",
        )

        print(f"\nConsumer: {consumer.name}")
        print(f"Threshold: ₹{consumer.threshold:.2f}")
        print()

        # Test Case 4: First time user, above threshold
        print("[Test 1] First time, above threshold (balance=150):")
        result = manager.should_send_notification(consumer.name, 150.0, consumer.threshold)
        print(f"  should_send_notification() = {result}")
        assert result is False, f"Expected False, got {result}"
        print("  ✓ PASS")

        # Test Case 4: First time user, below threshold
        print("\n[Test 2] First time, below threshold (balance=80):")
        result = manager.should_send_notification(consumer.name, 80.0, consumer.threshold)
        print(f"  should_send_notification() = {result}")
        assert result is True, f"Expected True, got {result}"
        print("  ✓ PASS")

        # Simulate notification sent
        manager.update_state(consumer.name, 80.0, consumer.threshold, notification_sent=True)
        print("  (State updated after notification sent)")

        # Test Case 2: Still below threshold
        print("\n[Test 3] Still below threshold (balance=75):")
        result = manager.should_send_notification(consumer.name, 75.0, consumer.threshold)
        print(f"  should_send_notification() = {result}")
        assert result is False, f"Expected False, got {result}"
        print("  ✓ PASS")

        # Test Case 3: Recovery - above threshold
        print("\n[Test 4] Recovered above threshold (balance=120):")
        result = manager.should_send_notification(consumer.name, 120.0, consumer.threshold)
        print(f"  should_send_notification() = {result}")
        assert result is False, f"Expected False, got {result}"
        print("  ✓ PASS")

        # Test Case 1: Drop below threshold again
        print("\n[Test 5] Dropped below threshold again (balance=90):")
        result = manager.should_send_notification(consumer.name, 90.0, consumer.threshold)
        print(f"  should_send_notification() = {result}")
        assert result is True, f"Expected True, got {result}"
        print("  ✓ PASS")

        # Simulate notification sent after Test 5
        manager.update_state(consumer.name, 90.0, consumer.threshold, notification_sent=True)
        print("  (State updated after notification sent)")

        # Verify state persistence
        print("\n[State Persistence Test]")
        manager2 = NotificationStateManager(state_file=test_state_file)
        state = manager2.get_state(consumer.name)
        print(f"  Loaded state: {state}")
        assert state["last_balance"] == 90.0
        print("  ✓ PASS")

        # Test clear state
        print("\n[Clear State Test]")
        manager2.clear_state(consumer.name)
        state = manager2.get_state(consumer.name)
        print(f"  After clear: {state}")
        assert state["last_notification"] is None
        print("  ✓ PASS")

        # Test reset all
        print("\n[Reset All Test]")
        manager2.update_state("Test", 100.0, 100.0)
        manager2.reset_all()
        print(f"  After reset: {repr(manager2)}")

    print("\n" + "=" * 60)
    print("ALL STATE MANAGER TESTS PASSED!")
    print("=" * 60)
