"""Data models for the SBPDCL Monitor application.

Provides reusable dataclasses for consumer information, balance results,
notification state, and automation outcomes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class Consumer:
    """Represents an electricity consumer to monitor.

    Attributes:
        name: Human-readable consumer name.
        ca: Consumer Account (CA) number.
        threshold: Low balance threshold in kWh.
        chat_id: Telegram chat ID for notifications.
    """

    name: str
    ca: str
    threshold: float
    chat_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of the consumer.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Consumer:
        """Create Consumer from dictionary.

        Args:
            data: Dictionary with consumer fields.

        Returns:
            Consumer instance.
        """
        return cls(
            name=data["name"],
            ca=str(data["ca"]),
            threshold=float(data["threshold"]),
            chat_id=data["chat_id"],
        )

    def __str__(self) -> str:
        """String representation with masked CA number."""
        masked = self.ca[-4:].rjust(len(self.ca), "X") if len(self.ca) >= 4 else "XXXX"
        return f"Consumer({self.name}, CA: {masked})"


@dataclass
class BalanceResult:
    """Result of a balance check operation.

    Attributes:
        consumer: The consumer whose balance was checked.
        balance: Current balance in kWh.
        status: Status message (e.g., 'success', 'error', 'low_balance').
        checked_at: Timestamp of the balance check.
    """

    consumer: Consumer
    balance: float
    status: str
    checked_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation with datetime as ISO string.
        """
        data = asdict(self)
        data["checked_at"] = self.checked_at.isoformat()
        data["consumer"] = self.consumer.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BalanceResult:
        """Create BalanceResult from dictionary.

        Args:
            data: Dictionary with balance result fields.

        Returns:
            BalanceResult instance.
        """
        checked_at = data.get("checked_at")
        if isinstance(checked_at, str):
            checked_at = datetime.fromisoformat(checked_at)

        return cls(
            consumer=Consumer.from_dict(data["consumer"]),
            balance=float(data["balance"]),
            status=data["status"],
            checked_at=checked_at or datetime.now(),
        )

    @property
    def is_low(self) -> bool:
        """Check if balance is below consumer's threshold."""
        return self.balance < self.consumer.threshold

    def __str__(self) -> str:
        """String representation showing balance and status."""
        return (
            f"BalanceResult({self.consumer.name}, "
            f"₹{self.balance:.2f}, {self.status})"
        )


@dataclass
class NotificationState:
    """Tracks notification history for a consumer.

    Attributes:
        consumer_name: Name of the consumer.
        last_notification: Timestamp of last notification sent.
        last_balance: Last known balance value.
        is_below_threshold: Whether balance is currently low.
    """

    consumer_name: str
    last_notification: Optional[datetime] = None
    last_balance: Optional[float] = None
    is_below_threshold: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation with datetimes as ISO strings.
        """
        return {
            "consumer_name": self.consumer_name,
            "last_notification": (
                self.last_notification.isoformat()
                if self.last_notification
                else None
            ),
            "last_balance": self.last_balance,
            "is_below_threshold": self.is_below_threshold,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NotificationState:
        """Create NotificationState from dictionary.

        Args:
            data: Dictionary with notification state fields.

        Returns:
            NotificationState instance.
        """
        last_notification = data.get("last_notification")
        if isinstance(last_notification, str):
            last_notification = datetime.fromisoformat(last_notification)

        return cls(
            consumer_name=data["consumer_name"],
            last_notification=last_notification,
            last_balance=(
                float(data["last_balance"])
                if data.get("last_balance") is not None
                else None
            ),
            is_below_threshold=bool(data.get("is_below_threshold", False)),
        )

    def __str__(self) -> str:
        """String representation showing notification status."""
        last = (
            self.last_notification.strftime("%Y-%m-%d %H:%M")
            if self.last_notification
            else "never"
        )
        return (
            f"NotificationState({self.consumer_name}, "
            f"last: {last}, below: {self.is_below_threshold})"
        )


@dataclass
class AutomationResult:
    """Result of an automation operation (e.g., balance check).

    Attributes:
        success: Whether the operation succeeded.
        message: Human-readable status message.
        duration_seconds: Time taken for the operation.
        screenshot: Optional path to a screenshot taken.
    """

    success: bool
    message: str
    duration_seconds: float
    screenshot: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation with Path as string.
        """
        return {
            "success": self.success,
            "message": self.message,
            "duration_seconds": self.duration_seconds,
            "screenshot": str(self.screenshot) if self.screenshot else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AutomationResult:
        """Create AutomationResult from dictionary.

        Args:
            data: Dictionary with automation result fields.

        Returns:
            AutomationResult instance.
        """
        screenshot = data.get("screenshot")
        return cls(
            success=bool(data["success"]),
            message=data["message"],
            duration_seconds=float(data["duration_seconds"]),
            screenshot=Path(screenshot) if screenshot else None,
        )

    def __str__(self) -> str:
        """String representation showing success and duration."""
        status = "✓" if self.success else "✗"
        return (
            f"AutomationResult({status} {self.message}, "
            f"{self.duration_seconds:.2f}s)"
        )
