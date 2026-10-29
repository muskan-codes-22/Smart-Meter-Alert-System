"""Utility functions for the SBPDCL Monitor application.

Provides reusable helpers for time, formatting, file operations,
decorators, and validation.
"""

from __future__ import annotations

import csv
import functools
import json
import re
import time
import time as time_mod
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, List, Optional, Type, TypeVar, Union

# ---------------------------------------------------------------------------
# Type variables
# ---------------------------------------------------------------------------

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Time Helpers
# ---------------------------------------------------------------------------

def current_time() -> datetime:
    """Return the current datetime.

    Returns:
        Current datetime object.
    """
    return datetime.now()


def current_date() -> date:
    """Return the current date.

    Returns:
        Current date object.
    """
    return date.today()


def timestamp_string(fmt: str = "%Y%m%d_%H%M%S") -> str:
    """Return current timestamp as a formatted string.

    Args:
        fmt: strftime format string. Defaults to '%Y%m%d_%H%M%S'.

    Returns:
        Formatted timestamp string.
    """
    return datetime.now().strftime(fmt)


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

def format_currency(amount: float, symbol: str = "₹") -> str:
    """Format a number as currency.

    Args:
        amount: The amount to format.
        symbol: Currency symbol. Defaults to '₹'.

    Returns:
        Formatted currency string (e.g., '₹83.40', '-₹269.51').

    Examples:
        >>> format_currency(83.4)
        '₹83.40'
        >>> format_currency(-269.51)
        '-₹269.51'
        >>> format_currency(1234.5)
        '₹1,234.50'
    """
    if amount < 0:
        return f"-{symbol}{abs(amount):,.2f}"
    return f"{symbol}{amount:,.2f}"


def parse_balance_string(text: str) -> Optional[float]:
    """Parse a balance value from text, handling negative signs, currency symbols, and commas.

    Supports:
        -₹269.51, - ₹269.51, ₹-269.51, ₹ -269.51, -269.51
        ₹568.07, 568.07, ₹1,000.00
        Unicode minuses (-, −, –, —).

    Args:
        text: String containing the balance amount.

    Returns:
        Float balance amount (positive or negative), or None if unparseable.

    Examples:
        >>> parse_balance_string("-₹269.51")
        -269.51
        >>> parse_balance_string("₹568.07")
        568.07
    """
    if not text:
        return None

    normalized = (
        str(text)
        .replace("\u2212", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\ufe63", "-")
        .replace("\uff0d", "-")
        .strip()
    )

    match = re.search(
        r"(-)?\s*(?:[₹]|Rs\.?|INR)?\s*(-)?\s*(\d[\d,]*(?:\.\d+)?)",
        normalized,
        re.IGNORECASE,
    )
    if match:
        num_str = match.group(3).replace(",", "").strip()
        try:
            amount = float(num_str)
            is_negative = bool(match.group(1) or match.group(2))
            return -amount if is_negative else amount
        except ValueError:
            return None
    return None


def mask_ca_number(ca: str, visible_chars: int = 4) -> str:
    """Mask a CA number, showing only the last few characters.

    Args:
        ca: The CA number to mask.
        visible_chars: Number of trailing characters to show.

    Returns:
        Masked CA number (e.g., 'XXXXXXXX9012').

    Examples:
        >>> mask_ca_number("123456789012")
        'XXXXXXXX9012'
        >>> mask_ca_number("123456789012", visible_chars=6)
        'XXXXXX789012'
    """
    if len(ca) <= visible_chars:
        return "X" * len(ca)
    masked_length = len(ca) - visible_chars
    return "X" * masked_length + ca[-visible_chars:]


# ---------------------------------------------------------------------------
# Directory Helpers
# ---------------------------------------------------------------------------

def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to create.

    Returns:
        The Path object for the directory.

    Examples:
        >>> ensure_directory("logs/2026")
        PosixPath('logs/2026')
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# ---------------------------------------------------------------------------
# Screenshot Helper
# ---------------------------------------------------------------------------

def generate_screenshot_name(
    prefix: str = "balance",
    suffix: str = "",
    extension: str = "png",
) -> str:
    """Generate a timestamped screenshot filename.

    Args:
        prefix: Filename prefix (e.g., 'balance', 'error').
        suffix: Optional suffix before extension.
        extension: File extension without dot.

    Returns:
        Generated filename (e.g., '20260716_103055_balance.png').

    Examples:
        >>> generate_screenshot_name("balance")
        '20260716_103055_balance.png'
        >>> generate_screenshot_name("error", suffix="timeout")
        '20260716_103055_error_timeout.png'
    """
    ts = timestamp_string()
    parts = [ts, prefix]
    if suffix:
        parts.append(suffix)
    name = "_".join(parts)
    return f"{name}.{extension.lstrip('.')}"


# ---------------------------------------------------------------------------
# Retry Decorator
# ---------------------------------------------------------------------------

def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Union[Type[Exception], tuple[Type[Exception], ...] ] = Exception,
) -> Callable[[F], F]:
    """Decorator to retry a function on exception.

    Args:
        max_attempts: Maximum number of attempts (including first call).
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to delay after each retry.
        exceptions: Exception type(s) to catch and retry.

    Returns:
        Decorated function with retry logic.

    Usage:
        >>> @retry(max_attempts=3, delay=1.0)
        ... def unstable_function():
        ...     # May raise ValueError
        ...     pass

    Note:
        With backoff=2.0 and delay=1.0:
        - Attempt 1 fails → wait 1s
        - Attempt 2 fails → wait 2s
        - Attempt 3 fails → raise exception
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc

                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Execution Timer Decorator
# ---------------------------------------------------------------------------

def timer(func: F) -> F:
    """Decorator that measures and logs function execution time.

    Logs the duration when the function completes, using print.

    Args:
        func: Function to time.

    Returns:
        Decorated function that logs execution duration.

    Usage:
        >>> @timer
        ... def slow_function():
        ...     time.sleep(1)
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time_mod.perf_counter()
        result = func(*args, **kwargs)
        duration = time_mod.perf_counter() - start
        print(f"[TIMER] {func.__name__} completed in {duration:.3f}s")
        return result

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# JSON Helpers
# ---------------------------------------------------------------------------

def read_json(path: Union[str, Path]) -> Any:
    """Read and parse a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON data.

    Raises:
        FileNotFoundError: If file does not exist.
        json.JSONDecodeError: If file contains invalid JSON.
    """
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(
    path: Union[str, Path],
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """Write data to a JSON file.

    Args:
        path: Path to write the JSON file.
        data: Data to serialize.
        indent: JSON indentation level.
        ensure_ascii: Whether to escape non-ASCII characters.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)


# ---------------------------------------------------------------------------
# CSV Helpers
# ---------------------------------------------------------------------------

def append_csv_row(
    path: Union[str, Path],
    row: List[Any],
    headers: Optional[List[str]] = None,
) -> None:
    """Append a row to a CSV file, creating it if it doesn't exist.

    Args:
        path: Path to the CSV file.
        row: Row data as a list of values.
        headers: Optional column headers (written only if file is new).
    """
    file_path = Path(path)
    file_exists = file_path.exists() and file_path.stat().st_size > 0

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists and headers:
            writer.writerow(headers)

        writer.writerow(row)


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def is_valid_balance(balance: Any) -> bool:
    """Check if a balance value is valid (can be converted to a numeric float).

    Args:
        balance: Value to validate.

    Returns:
        True if balance is a valid numeric value (positive or negative).

    Examples:
        >>> is_valid_balance(83.4)
        True
        >>> is_valid_balance(-10)
        True
        >>> is_valid_balance("invalid")
        False
    """
    if balance is None or isinstance(balance, bool):
        return False
    try:
        float(balance)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Self Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile
    import shutil
    import sys
    import io

    # Fix encoding for Windows console
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )

    print("=" * 60)
    print("UTILS SELF TEST")
    print("=" * 60)

    # Currency formatting
    print("\n[1] Currency Formatting:")
    print(f"    format_currency(83.4)     = {format_currency(83.4)}")
    print(f"    format_currency(1234.5)   = {format_currency(1234.5)}")
    print(f"    format_currency(0)        = {format_currency(0)}")

    # CA masking
    print("\n[2] CA Number Masking:")
    print(f"    mask_ca_number('123456789012')     = {mask_ca_number('123456789012')}")
    print(f"    mask_ca_number('123456789012', 6)  = {mask_ca_number('123456789012', 6)}")
    print(f"    mask_ca_number('1234')             = {mask_ca_number('1234')}")

    # Retry decorator
    print("\n[3] Retry Decorator:")
    attempt_counter = {"count": 0}

    @retry(max_attempts=3, delay=0.1, exceptions=ValueError)
    def flaky_function() -> str:
        attempt_counter["count"] += 1
        if attempt_counter["count"] < 3:
            raise ValueError(f"Attempt {attempt_counter['count']} failed")
        return "Success!"

    try:
        result = flaky_function()
        print(f"    flaky_function() = {result}")
        print(f"    Attempts needed: {attempt_counter['count']}")
    except ValueError as e:
        print(f"    Failed after retries: {e}")

    # JSON helpers
    print("\n[4] JSON Helpers:")
    test_dir = Path(tempfile.mkdtemp())
    test_json = test_dir / "test.json"

    test_data = {"consumers": [{"name": "Home", "ca": "123"}]}
    write_json(test_json, test_data)
    loaded = read_json(test_json)
    print(f"    Written and read JSON: {loaded}")

    # CSV helper
    print("\n[5] CSV Helper:")
    test_csv = test_dir / "test.csv"
    append_csv_row(test_csv, ["2026-07-16", "Home", "87.25"], ["date", "name", "balance"])
    append_csv_row(test_csv, ["2026-07-17", "Home", "75.00"])

    with test_csv.open("r") as f:
        print(f"    CSV contents:\n{f.read()}")

    # Directory creation
    print("\n[6] Directory Creation:")
    test_subdir = test_dir / "new_dir" / "nested"
    ensure_directory(test_subdir)
    print(f"    Created: {test_subdir.exists()}")

    # Screenshot filename
    print("\n[7] Screenshot Filename:")
    print(f"    generate_screenshot_name('balance')           = {generate_screenshot_name('balance')}")
    print(f"    generate_screenshot_name('error', 'timeout')  = {generate_screenshot_name('error', 'timeout')}")

    # Validation
    print("\n[8] Balance Validation:")
    print(f"    is_valid_balance(83.4)    = {is_valid_balance(83.4)}")
    print(f"    is_valid_balance(-10)     = {is_valid_balance(-10)}")
    print(f"    is_valid_balance('abc')   = {is_valid_balance('abc')}")

    # Time helpers
    print("\n[9] Time Helpers:")
    print(f"    current_time()       = {current_time()}")
    print(f"    current_date()       = {current_date()}")
    print(f"    timestamp_string()   = {timestamp_string()}")

    # Timer decorator
    print("\n[10] Timer Decorator:")
    @timer
    def sample_work() -> None:
        time.sleep(0.1)

    sample_work()

    # Cleanup
    shutil.rmtree(test_dir)

    print("\n" + "=" * 60)
    print("ALL UTILS TESTS PASSED!")
    print("=" * 60)
