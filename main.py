"""SBPDCL Monitor - Entry Point.

Production-ready application that monitors SBPDCL Smart Meter balance
and sends WhatsApp notifications for low balance alerts.
"""

from __future__ import annotations

import sys
import time as time_mod
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

from src.config import AppConfig, ConsumerConfig, load_config
from src.logger import setup_logger, get_logger, log_exception
from src.models import Consumer, BalanceResult
from src.checker import SBPDCLChecker, SBPDCLException
from src.whatsapp import WhatsAppSender, WhatsAppException
from src.state import NotificationStateManager
from src.message_builder import build_notification_message
from src.utils import (
    append_csv_row,
    ensure_directory,
    format_currency,
    mask_ca_number,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).resolve().parent / "data"
_HISTORY_FILE = _DATA_DIR / "history.csv"
_HISTORY_HEADERS = [
    "timestamp",
    "consumer",
    "ca",
    "balance",
    "threshold",
    "notification_sent",
    "status",
]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _print_header() -> None:
    """Print application header."""
    print()
    print("=" * 60)
    print("  SBPDCL Monitor")
    print("  Smart Meter Balance Monitoring System")
    print("=" * 60)


def _print_summary(
    processed: int,
    alerts_sent: int,
    failures: int,
    duration: float,
) -> None:
    """Print execution summary.

    Args:
        processed: Number of consumers processed.
        alerts_sent: Number of alerts sent.
        failures: Number of failures.
        duration: Total execution time in seconds.
    """
    print()
    print("=" * 60)
    print("  SBPDCL Monitor Summary")
    print("-" * 60)
    print(f"  Consumers Processed : {processed}")
    print(f"  Alerts Sent         : {alerts_sent}")
    print(f"  Failures            : {failures}")
    print(f"  Execution Time      : {duration:.1f} sec")
    print("=" * 60)
    print()


def _save_history(
    consumer: Consumer,
    balance: float,
    notification_sent: bool,
    status: str,
) -> None:
    """Save balance reading to history CSV.

    Args:
        consumer: Consumer information.
        balance: Current balance value.
        notification_sent: Whether notification was sent.
        status: Status of the check (success, error, etc.).
    """
    timestamp = datetime.now().isoformat()
    row = [
        timestamp,
        consumer.name,
        consumer.ca,
        f"{balance:.2f}",
        f"{consumer.threshold:.2f}",
        str(notification_sent),
        status,
    ]

    append_csv_row(_HISTORY_FILE, row, headers=_HISTORY_HEADERS)


def _send_whatsapp_notification(
    whatsapp: WhatsAppSender,
    consumer: Consumer,
    balance: float,
    phone: str,
    language: str = "en",
) -> bool:
    """Send WhatsApp notification for low balance.

    Args:
        whatsapp: WhatsApp sender instance.
        consumer: Consumer information.
        balance: Current balance value.
        phone: Phone number for notification.
        language: Language code for the notification message.

    Returns:
        True if notification sent successfully.
    """
    # Build consumer config for message builder
    consumer_config = ConsumerConfig(
        name=consumer.name,
        ca=consumer.ca,
        threshold=consumer.threshold,
        whatsapp=consumer.whatsapp,
        phone=phone,
        language=language,
    )

    message = build_notification_message(consumer_config, balance)

    return whatsapp.send_notification(
        chat_name=consumer.whatsapp,
        phone=phone,
        message=message,
    )


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

def run() -> int:
    """Run the SBPDCL Monitor application.

    Returns:
        Exit code (0 for success, 1 for fatal error).
    """
    start_time = time_mod.perf_counter()
    _print_header()

    # ------------------------------------------------------------------
    # Step 1: Load configuration
    # ------------------------------------------------------------------
    print("[1/6] Loading configuration...")
    try:
        config = load_config()
    except Exception as exc:
        print(f"  ✗ Fatal: Could not load configuration: {exc}")
        return 1

    # ------------------------------------------------------------------
    # Step 2: Initialize logger
    # ------------------------------------------------------------------
    setup_logger(config.log_level)
    logger = get_logger("main")
    logger.info("SBPDCL Monitor starting")
    print(f"  ✓ Configuration loaded ({len(config.consumers)} consumers)")

    # ------------------------------------------------------------------
    # Step 3: Initialize services
    # ------------------------------------------------------------------
    print("[2/6] Initializing services...")
    state_manager = NotificationStateManager()
    print("  ✓ State manager ready")

    # ------------------------------------------------------------------
    # Step 4: Launch checker browser
    # ------------------------------------------------------------------
    print("[3/6] Launching browser...")
    checker: SBPDCLChecker | None = None

    try:
        checker = SBPDCLChecker(config)
        checker.launch_browser()
        print("  ✓ SBPDCL checker browser ready")
    except SBPDCLException as exc:
        logger.error("Failed to launch checker browser: {}", str(exc))
        print(f"  ✗ Checker browser failed: {exc}")
        print("  ✗ Cannot continue without checker browser")
        return 1

    # ------------------------------------------------------------------
    # Step 5: Process consumers
    # ------------------------------------------------------------------
    print("[4/6] Checking balances...")

    processed = 0
    alerts_sent = 0
    failures = 0

    for idx, consumer_config in enumerate(config.consumers, 1):
        consumer = Consumer(
            name=consumer_config.name,
            ca=consumer_config.ca,
            threshold=consumer_config.threshold,
            whatsapp=consumer_config.whatsapp,
        )

        print(f"\n  [{idx}/{len(config.consumers)}] {consumer.name}")
        print(f"      CA: {mask_ca_number(consumer.ca)}")

        # Check balance
        if checker is None:
            print("      ✗ Checker not available")
            failures += 1
            continue

        try:
            result = checker.check_balance(consumer)
        except SBPDCLException as exc:
            logger.error("Balance check failed for {}: {}", consumer.name, str(exc))
            print(f"      ✗ Balance check failed: {exc}")
            _save_history(consumer, 0.0, False, "error")
            failures += 1
            continue

        balance = result.balance
        balance_str = format_currency(balance)
        threshold_str = format_currency(consumer.threshold)

        print(f"      Balance: {balance_str}")
        print(f"      Threshold: {threshold_str}")

        # Determine if notification needed
        should_notify = state_manager.should_send_notification(
            consumer.name,
            balance,
            consumer.threshold,
        )

        notification_sent = False

        if should_notify:
            print("      → Notification required")

            # Close checker browser first (Playwright can't run 2 browsers)
            if checker is not None:
                try:
                    checker.close_browser()
                except Exception:
                    pass

            # Launch WhatsApp browser and send notification
            whatsapp: WhatsAppSender | None = None
            try:
                whatsapp = WhatsAppSender(config)
                whatsapp.launch_browser()
                whatsapp.ensure_logged_in()

                success = _send_whatsapp_notification(
                    whatsapp, consumer, balance, consumer_config.phone,
                    language=consumer_config.language,
                )
                if success:
                    notification_sent = True
                    alerts_sent += 1
                    print("      ✓ Alert sent!")
                else:
                    print("      ✗ WhatsApp send failed")
            except WhatsAppException as exc:
                logger.error("WhatsApp error for {}: {}", consumer.name, str(exc))
                print(f"      ✗ WhatsApp error: {exc}")
            finally:
                # Always close WhatsApp browser after use
                if whatsapp is not None:
                    try:
                        whatsapp.close_browser()
                    except Exception:
                        pass

                # Re-launch checker browser for remaining consumers
                if checker is not None and idx < len(config.consumers):
                    try:
                        checker.launch_browser()
                    except Exception:
                        pass
        else:
            print("      → No notification needed")

        # Update state
        state_manager.update_state(
            consumer.name,
            balance,
            consumer.threshold,
            notification_sent=notification_sent,
        )

        # Save history
        status = "notified" if notification_sent else "ok"
        _save_history(consumer, balance, notification_sent, status)

        processed += 1
        print(f"      ✓ Complete")

    # ------------------------------------------------------------------
    # Step 6: Summary
    # ------------------------------------------------------------------
    print("[5/6] Finalizing...")
    logger.info(
        "Monitor completed: processed={}, alerts={}, failures={}",
        processed,
        alerts_sent,
        failures,
    )

    # ------------------------------------------------------------------
    # Cleanup: Close checker browser
    # ------------------------------------------------------------------
    print("[6/6] Closing browser...")

    if checker is not None:
        try:
            checker.close_browser()
        except Exception:
            pass

    # Print summary
    duration = time_mod.perf_counter() - start_time
    _print_summary(processed, alerts_sent, failures, duration)

    logger.info("SBPDCL Monitor finished in {:.1f}s", duration)

    return 0 if failures == 0 else 1


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Application entry point."""
    try:
        exit_code = run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        exit_code = 1
    except Exception as exc:
        print(f"\nFatal error: {exc}")
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
