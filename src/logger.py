"""Logging configuration module.

Provides a centralized logging setup using Loguru with:
- Daily rotating file handlers
- Console output with concise formatting
- Zip compression for archived logs
- Child logger creation for individual modules
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from typing import Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} | "
    "{message}"
)

_MAX_LOG_FILES = 30
_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_log_dir() -> None:
    """Create the logs directory if it does not exist."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _rotation_handler(message: str) -> None:
    """Custom rotation callback.

    Zips the previous day's log file before a new one is started.
    """
    record = message.record
    log_file = Path(record["file"].path)

    if not log_file.exists():
        return

    # Only zip files older than today
    import datetime

    log_date = record["time"].date()
    today = datetime.date.today()

    if log_date >= today:
        return

    zip_path = log_file.with_suffix(".zip")
    if zip_path.exists():
        return

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(log_file, log_file.name)
        log_file.unlink()
    except OSError:
        pass  # Best effort - don't crash on rotation failure


def _cleanup_old_logs() -> None:
    """Remove log files exceeding the retention count."""
    import datetime

    log_files = sorted(
        _LOG_DIR.glob("*.log"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    for old_file in log_files[_MAX_LOG_FILES:]:
        try:
            old_file.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logger(log_level: str = "INFO") -> logger.__class__:
    """Initialize and configure the application logger.

    Sets up console and file handlers with appropriate formatting,
    rotation, and retention policies.

    Args:
        log_level: Minimum log level to capture. Supported values:
            DEBUG, INFO, WARNING, ERROR, CRITICAL.

    Returns:
        The configured Loguru logger instance.

    Raises:
        ValueError: If log_level is not a supported level.
    """
    level = log_level.strip().upper()
    if level not in _VALID_LEVELS:
        raise ValueError(
            f"Invalid log level: {level!r}. "
            f"Supported: {', '.join(sorted(_VALID_LEVELS))}"
        )

    _ensure_log_dir()

    # Remove default handler to allow reconfiguration
    logger.remove()

    # Console handler - skip when running from Task Scheduler (print only)
    import os
    if not os.getenv("SBPDCL_TASK_SCHEDULER"):
        logger.add(
            sys.stdout,
            level=level,
            format=_CONSOLE_FORMAT,
            colorize=True,
            backtrace=True,
            diagnose=False,
        )

    # File handler - detailed format with daily rotation
    log_file = _LOG_DIR / "{time:YYYY-MM-DD}.log"
    logger.add(
        str(log_file),
        level=level,
        format=_FILE_FORMAT,
        rotation="00:00",  # Rotate at midnight
        retention=_MAX_LOG_FILES,
        compression=_zip_compression,
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # Run cleanup of old logs on setup
    _cleanup_old_logs()

    logger.debug("Logger initialized at {} level", level)
    return logger


def _zip_compression(path: Path) -> None:
    """Compress a log file into a zip archive.

    Args:
        path: Path to the log file to compress.
    """
    zip_path = path.with_suffix(".zip")
    if zip_path.exists():
        return

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(path, path.name)
        path.unlink()
    except OSError:
        pass


def get_logger(name: str) -> logger.__class__:
    """Return a child logger bound to the given module name.

    Usage::

        from src.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Application started")

    Args:
        name: Module or component name (typically ``__name__``).

    Returns:
        A Loguru logger bound to the specified name.
    """
    return logger.bind(name=name)


def log_exception(
    exception: BaseException,
    *,
    extra: Optional[str] = None,
) -> None:
    """Log an exception with full traceback and context.

    Args:
        exception: The exception to log.
        extra: Optional additional context message.
    """
    context = f" ({extra})" if extra else ""
    logger.opt(exception=True).error(
        "Exception{context}: {exc_type}: {exc_msg}",
        context=context,
        exc_type=type(exception).__name__,
        exc_msg=str(exception),
    )


# ---------------------------------------------------------------------------
# Self test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Add parent directory to path for self-test
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from src.config import load_config

    try:
        cfg = load_config()
        setup_logger(cfg.log_level)
    except Exception:
        setup_logger("INFO")

    test_logger = get_logger("test_module")

    test_logger.debug("This is a DEBUG message")
    test_logger.info("This is an INFO message")
    test_logger.warning("This is a WARNING message")
    test_logger.error("This is an ERROR message")
    test_logger.critical("This is a CRITICAL message")

    try:
        raise ValueError("Something went wrong during testing")
    except ValueError as exc:
        log_exception(exc, extra="self-test")

    print(f"\nLog files created in: {_LOG_DIR}")
    for f in _LOG_DIR.iterdir():
        print(f"  {f.name} ({f.stat().st_size} bytes)")
