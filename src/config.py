"""Configuration management module.

Loads environment variables and consumer configurations,
validates them, and exposes strongly typed configuration objects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv
import os


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConsumerConfig:
    """Configuration for a single consumer/meter.

    Attributes:
        name: Human-readable name for the consumer.
        ca: Consumer Account (CA) number.
        threshold: Low balance threshold in kWh.
        whatsapp: WhatsApp recipient identifier (chat name or phone).
        phone: Phone number for direct WhatsApp messaging.
        language: Language for notifications ("en" or "hi").
    """

    name: str
    ca: str
    threshold: float
    whatsapp: str
    phone: str = ""
    language: str = "en"


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration.

    Attributes:
        headless: Whether to run the browser in headless mode.
        default_timeout: Default Playwright timeout in milliseconds.
        browser_profile: Path to the browser profile directory.
        log_level: Logging verbosity level.
        consumers: List of consumer configurations to monitor.
    """

    headless: bool
    default_timeout: int
    browser_profile: Path
    log_level: str
    consumers: List[ConsumerConfig] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_environment(env_path: Path | None = None) -> None:
    """Load environment variables from a .env file.

    If *env_path* is ``None`` the default ``.env`` in the project root
    is used.

    Args:
        env_path: Optional path to a custom .env file.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    if env_path is not None and not env_path.exists():
        raise FileNotFoundError(
            f"Environment file not found: {env_path}"
        )

    load_dotenv(dotenv_path=env_path, override=False)


# ---------------------------------------------------------------------------
# Consumer helpers
# ---------------------------------------------------------------------------

def _validate_consumer(raw: dict, index: int) -> ConsumerConfig:
    """Validate and convert a raw dict into a *ConsumerConfig*.

    Args:
        raw: Dictionary loaded from consumers.json.
        index: Position of the consumer in the list (for error messages).

    Returns:
        A validated *ConsumerConfig* instance.

    Raises:
        ConfigError: If required fields are missing or invalid.
    """
    label = raw.get("name") or f"consumer at index {index}"

    # --- required fields ---------------------------------------------------
    missing = [k for k in ("name", "ca", "threshold", "whatsapp") if k not in raw]
    if missing:
        raise ConfigError(
            f"Invalid consumer configuration: "
            f"Missing field(s) {', '.join(missing)} for {label}"
        )

    name: str = raw["name"]
    ca: str = str(raw["ca"]).strip()
    whatsapp: str = str(raw["whatsapp"]).strip()
    phone: str = str(raw.get("phone", "")).strip()
    language: str = str(raw.get("language", "en")).strip().lower()

    # Validate language
    if language not in ("en", "hi"):
        raise ConfigError(
            f"Invalid consumer configuration: "
            f"Language must be 'en' or 'hi' for consumer {name!r}, got '{language}'"
        )

    if not ca:
        raise ConfigError(
            f"Invalid consumer configuration: "
            f"CA number is empty for consumer {name!r}"
        )

    # --- threshold ---------------------------------------------------------
    try:
        threshold: float = float(raw["threshold"])
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"Invalid consumer configuration: "
            f"Threshold must be a number for consumer {name!r}"
        ) from exc

    if threshold <= 0:
        raise ConfigError(
            f"Invalid consumer configuration: "
            f"Threshold must be greater than 0 for consumer {name!r}"
        )

    return ConsumerConfig(
        name=name,
        ca=ca,
        threshold=threshold,
        whatsapp=whatsapp,
        phone=phone,
        language=language,
    )


def load_consumers(path: Path | None = None) -> List[ConsumerConfig]:
    """Load and validate the consumers configuration file.

    Args:
        path: Path to ``consumers.json``. Defaults to ``data/consumers.json``
              relative to the project root.

    Returns:
        A list of validated *ConsumerConfig* objects.

    Raises:
        FileNotFoundError: If the file does not exist.
        ConfigError: If the JSON is invalid or data is missing/invalid.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "consumers.json"

    if not path.exists():
        raise FileNotFoundError(
            f"Consumers file not found: {path}"
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Invalid JSON in consumers file: {exc}"
        ) from exc

    # Accept either a list directly or an object with a "consumers" key
    if isinstance(data, dict):
        data = data.get("consumers", [])

    if not isinstance(data, list):
        raise ConfigError(
            "Invalid consumers file: expected a JSON list or an object "
            "with a 'consumers' key"
        )

    if not data:
        raise ConfigError(
            "Invalid consumers file: no consumers defined"
        )

    consumers: List[ConsumerConfig] = []
    for idx, raw in enumerate(data):
        consumers.append(_validate_consumer(raw, idx))

    return consumers


# ---------------------------------------------------------------------------
# App config
# ---------------------------------------------------------------------------

def _env_bool(key: str, default: bool) -> bool:
    """Read a boolean environment variable.

    Accepts ``true``, ``1``, ``yes`` (case-insensitive) as ``True``.
    """
    raw = os.getenv(key, str(default)).strip().lower()
    return raw in ("true", "1", "yes")


def _env_int(key: str, default: int) -> int:
    """Read an integer environment variable."""
    raw = os.getenv(key, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"Invalid integer for {key}: {raw!r}"
        ) from exc


def load_config(
    env_path: Path | None = None,
    consumers_path: Path | None = None,
) -> AppConfig:
    """Build a fully validated *AppConfig*.

    Args:
        env_path: Optional path to a custom .env file.
        consumers_path: Optional path to consumers.json.

    Returns:
        A populated *AppConfig* instance.
    """
    load_environment(env_path)

    consumers = load_consumers(consumers_path)

    browser_profile = Path(
        os.getenv("BROWSER_PROFILE", "browser")
    )

    return AppConfig(
        headless=_env_bool("HEADLESS", False),
        default_timeout=_env_int("DEFAULT_TIMEOUT", 30000),
        browser_profile=browser_profile,
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        consumers=consumers,
    )


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        cfg = load_config()
        print("Configuration loaded successfully!\n")
        print(f"  Headless:          {cfg.headless}")
        print(f"  Default timeout:   {cfg.default_timeout} ms")
        print(f"  Browser profile:   {cfg.browser_profile}")
        print(f"  Log level:         {cfg.log_level}")
        print(f"  Consumers:         {len(cfg.consumers)}")
        for consumer in cfg.consumers:
            print(
                f"    - {consumer.name} "
                f"(CA: {consumer.ca}, "
                f"threshold: {consumer.threshold}, "
                f"whatsapp: {consumer.whatsapp})"
            )
    except (ConfigError, FileNotFoundError) as exc:
        print(f"Configuration error: {exc}")
