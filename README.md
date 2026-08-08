# SBPDCL Smart Meter Monitor

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4.svg)](https://www.microsoft.com/windows)
[![Playwright](https://img.shields.io/badge/Browser-Playwright-2EAD33.svg)](https://playwright.dev/python/)
[![Telegram Bot API](https://img.shields.io/badge/Messaging-Telegram-26A5E4.svg)](https://core.telegram.org/bots/api)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)](CONTRIBUTING.md)

Automated prepaid smart meter balance monitoring for South Bihar Power Distribution Company (SBPDCL) with intelligent Telegram alerts, email fallback, persistent notification state, and scheduled background execution.

---

## Overview

SBPDCL Smart Meter Monitor is a production-oriented automation application that continuously monitors prepaid electricity smart meter balances and sends Telegram notifications whenever the available balance falls below a configurable threshold.

The application was built to solve a real-world problem observed in everyday usage.

Although payment applications such as Google Pay, PhonePe, and Paytm support recharging SBPDCL prepaid smart meters, they do not display the current available balance. As a result, users often have to repeatedly visit the SBPDCL portal simply to check their remaining balance, making it difficult to know the right time to recharge and occasionally leading to unexpected power interruptions.

**This project automates that entire process.**

Running silently every hour using Windows Task Scheduler, it retrieves the latest balance from the SBPDCL portal through browser automation and immediately sends Telegram alerts (or email fallback if Telegram is unavailable) whenever the balance falls below a configured threshold.

---

## Key Features

- Automated smart meter balance monitoring
- Playwright-based browser automation
- Instant Telegram notifications
- Email fallback when Telegram is blocked/unavailable
- Configurable low balance thresholds
- Multi-consumer monitoring
- Duplicate notification prevention
- Persistent notification state
- Historical balance logging
- Multi-language notifications (English & Hindi)
- Rotating application logs
- Environment-based configuration
- Silent background execution via Windows Task Scheduler
- Modular and extensible architecture

---

## Why This Project Exists

Checking the remaining balance of an SBPDCL prepaid smart meter is surprisingly inconvenient.

Users can recharge their meters through various UPI applications, but none of them provide the current available balance. Consequently, the only reliable method is repeatedly logging into the SBPDCL portal.

This project removes that manual effort by automatically monitoring balances in the background and notifying users only when attention is required.

**Instead of checking multiple times every day, users receive alerts only when the remaining balance becomes low.**

---

## Features in Detail

### Automated Balance Retrieval

Uses Microsoft Playwright with Chromium to securely navigate the SBPDCL portal and retrieve the latest smart meter balance.

### Telegram Notifications

Automatically sends beautifully formatted Telegram messages whenever:

- Balance drops below threshold
- Balance remains healthy (no notification)
- Duplicate notifications are prevented

Supports both:

- English
- Hindi

### Email Fallback

If Telegram is blocked, unavailable, or the bot is removed from the chat, the application automatically sends an HTML-formatted email alert instead. This ensures notifications are never missed.

The email includes:

- Consumer name and current balance
- Error details from the Telegram failure
- Clear action prompt to recharge

Configured via three environment variables:

```env
EMAIL_ADDRESS=your_gmail@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
RECEIVER_EMAIL=recipient@example.com
```

> **Note:** Use a [Gmail App Password](https://support.google.com/accounts/answer/185833), not your regular Gmail password.

### Multi Consumer Support

Monitor multiple SBPDCL consumer accounts simultaneously using a single configuration file.

Example:

```json
[
  {
    "name": "Home",
    "ca": "XXXXXXXXXXXX",
    "threshold": 500,
    "language": "en"
  },
  {
    "name": "Shop",
    "ca": "XXXXXXXXXXXX",
    "threshold": 800,
    "language": "hi"
  }
]
```

### Intelligent Notification State

The application remembers previously sent notifications.

Instead of repeatedly sending alerts every execution cycle, notifications are sent only when required.

**Example flow:**

```
₹1200
  ↓
₹800
  ↓
₹450 → Alert Sent
  ↓
₹430 → No Alert
  ↓
₹410 → No Alert
  ↓
₹1300 → State Reset
  ↓
₹470 → Alert Sent Again
```

### Historical Logging

Every execution records:

- Timestamp
- Consumer Name
- Current Balance
- Threshold
- Notification Status

This enables future reporting and balance trend analysis.

### Scheduled Background Execution

Designed to run every hour via Windows Task Scheduler. Requires manual setup of the scheduled task (see [Windows Task Scheduler](#windows-task-scheduler)).

---

## Project Structure

```
sbpdcl-monitor/
│
├── src/
│   ├── checker.py           # Playwright browser automation for balance checking
│   ├── config.py            # Configuration management
│   ├── email_notifier.py    # Email fallback (Gmail SMTP)
│   ├── logger.py            # Logging setup with rotation
│   ├── message_builder.py   # Multi-language message templates
│   ├── models.py            # Data models (Consumer, BalanceResult, etc.)
│   ├── state.py             # Notification state management
│   ├── telegram.py          # Telegram Bot API sender
│   └── utils.py             # Utility functions
│
├── data/
│   ├── consumers.json       # Consumer configuration
│   ├── notified.json        # Notification tracking state
│   └── history.csv          # Balance history logs
│
├── logs/                    # Application and task scheduler logs
├── tests/                   # Unit tests
│
├── .env                     # Environment variables (bot token, chat_id, email, etc.)
├── .env.example             # Environment variables template
├── run_hidden.ps1           # Silent runner for Task Scheduler
├── requirements.txt         # Python dependencies
├── main.py                  # Application entry point
└── README.md                # This file
```

---

## Architecture

```
                Windows Task Scheduler
                          │
                          ▼
                     main.py
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
 Configuration                  Notification State
          │                               │
          ▼                               ▼
     Playwright Checker ─────────► Telegram Bot
          │                               │
          │                          (on failure)
          │                               │
          │                               ▼
          │                       Email Fallback
          ▼                        (Gmail SMTP)
     SBPDCL Portal
          │
          ▼
    Current Meter Balance
```

---

## Technology Stack

| Category         | Technology              |
|------------------|-------------------------|
| Language         | Python 3.10+            |
| Browser Automation | Playwright            |
| Messaging        | Telegram Bot API        |
| Email Fallback   | Gmail SMTP (SSL)        |
| Scheduler        | Windows Task Scheduler  |
| Configuration    | JSON + dotenv           |
| Logging          | Python Logging          |
| Data Storage     | JSON + CSV              |
| Testing          | Pytest                  |

---

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git
- A Telegram bot (create via [@BotFather](https://t.me/BotFather))

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/sbpdcl-monitor.git
cd sbpdcl-monitor
```

### 2. Virtual Environment Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
# Install Chromium browser (required for SBPDCL portal automation)
playwright install chromium

# Install system dependencies (if needed)
playwright install-deps
```

### 5. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** you receive
4. Message your new bot, then visit:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
5. Find your **chat_id** in the response (`result[0].message.chat.id`)

### 6. Configure Environment Variables

Copy the template and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Email Fallback (Gmail)
EMAIL_ADDRESS=your_gmail@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
RECEIVER_EMAIL=recipient@example.com

# Browser Configuration
HEADLESS=true
DEFAULT_TIMEOUT=30000

# Logging
LOG_LEVEL=INFO
```

### 7. Configure Consumers

Edit `data/consumers.json`:

```json
[
    {
        "name": "Home",
        "ca": "XXXXXXXXXXXX",
        "threshold": 500,
        "language": "en"
    }
]
```

| Field | Description |
|-------|-------------|
| `name` | Human-readable consumer name |
| `ca` | Consumer Account (CA) number from SBPDCL |
| `threshold` | Low balance threshold (₹) — alert triggers below this |
| `chat_id` | *(optional)* Override Telegram chat ID for this consumer |
| `language` | `"en"` for English, `"hi"` for Hindi |

If `chat_id` is omitted, the default from `TELEGRAM_CHAT_ID` in `.env` is used.

---

## Running

```bash
python main.py
```

### Sample Output

```
============================================================
  SBPDCL Monitor
  Smart Meter Balance Monitoring System
============================================================
[1/6] Loading configuration...
  Configuration loaded (1 consumers)
[2/6] Initializing services...
  Telegram bot verified
  Email fallback configured
  State manager ready
[3/6] Launching browser...
  SBPDCL checker browser ready
[4/6] Checking balances...

  [1/1] Home
      CA: XXXXXXXX7048
      Balance: ₹448.58
      Threshold: ₹500.00
      Notification required
      Alert sent!

[5/6] Finalizing...
[6/6] Cleaning up...

============================================================
  SBPDCL Monitor Summary
------------------------------------------------------------
  Consumers Processed : 1
  Alerts Sent         : 1
  Failures            : 0
  Execution Time      : 11.6 sec
============================================================
```

When Telegram is unavailable, the app continues with email fallback:

```
[2/6] Initializing services...
  Telegram verification failed (will use email fallback)
  Email fallback configured
  State manager ready
...
[4/6] Checking balances...

  [1/1] Home
      Balance: ₹448.58
      Threshold: ₹500.00
      Notification required
      Alert sent via email!
```

---

## Windows Task Scheduler

The project is designed for unattended execution via Windows Task Scheduler. You need to manually create the scheduled task.

### Manual Setup

Open Task Scheduler and create a new task with the following settings:

| Property | Value |
|----------|-------|
| Task Name | `SBPDCL Monitor` |
| Schedule | Every hour |
| Action | Start a program |
| Program | `powershell.exe` |
| Arguments | `-ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\PK\Projects\sbpdcl-monitor\run_hidden.ps1"` |

Alternatively, create the task via command line:

```powershell
schtasks /Create /TN "SBPDCL Monitor" /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File \"C:\PK\Projects\sbpdcl-monitor\run_hidden.ps1\"" /SC HOURLY /MO 1
```

### Useful Commands

```powershell
# Run manually now
schtasks /Run /TN "SBPDCL Monitor"

# Check full task details (triggers, actions, settings)
schtasks /Query /TN "SBPDCL Monitor" /V /FO LIST

# Check status
schtasks /Query /TN "SBPDCL Monitor"

# Stop a running instance
schtasks /End /TN "SBPDCL Monitor"

# Delete the task
schtasks /Delete /TN "SBPDCL Monitor" /F
```

---

## Notification Logic

| Current State | Previous State | Action |
|---------------|----------------|--------|
| Above Threshold | Above Threshold | Ignore |
| Above Threshold | Below Threshold | Reset State |
| Below Threshold | Above Threshold | Send Alert |
| Below Threshold | Below Threshold | Ignore |

---

## Logging

The application maintains detailed execution logs for debugging and monitoring.

```
logs/
├── application.log
└── task_scheduler.log
```

---

## Future Improvements

- Docker deployment
- GitHub Actions scheduling
- Recharge prediction using historical usage
- Monthly balance analytics dashboard
- WhatsApp integration
- Web dashboard
- Cloud deployment (AWS Lambda / Azure Functions)
- REST API
- Automatic health monitoring and retry mechanism

---

## Contributing

Contributions, feature requests, and bug reports are welcome.

If you have ideas to improve this project, feel free to open an issue or submit a pull request.

---

## Disclaimer

This project is intended for educational and personal automation purposes. Users are responsible for ensuring that automated access to the SBPDCL portal complies with applicable terms of service and regulations.
