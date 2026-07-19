# SBPDCL Monitor

A production-ready application that monitors SBPDCL (South Bihar Power Distribution Company Limited) Smart Meter balance and sends Telegram notifications for low balance alerts.

## Features

- **Automated Balance Checking** — Uses Playwright for headless browser automation to fetch meter balance from the SBPDCL portal
- **Telegram Notifications** — Sends instant alerts via Telegram Bot API when balance falls below threshold
- **Multi-Consumer Support** — Monitor multiple meters from a single configuration
- **State Management** — Prevents duplicate notifications and tracks notification history
- **Scheduled Execution** — Runs automatically every 3 hours via Windows Task Scheduler (silent, no window)
- **Configurable Thresholds** — Set custom low balance thresholds per consumer
- **Multi-Language Messages** — Supports English and Hindi notification templates

## Folder Structure

```
sbpdcl-monitor/
├── src/
│   ├── checker.py           # Playwright browser automation for balance checking
│   ├── config.py            # Configuration management
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
├── .env                     # Environment variables (bot token, chat_id, etc.)
├── .env.example             # Environment variables template
├── run_hidden.ps1           # Silent runner for Task Scheduler
├── requirements.txt         # Python dependencies
├── main.py                  # Application entry point
└── README.md                # This file
```

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

# SBPDCL Portal Configuration (if needed)
SBPDCL_URL=https://www.sbpdcl.co.in

# Browser Configuration
HEADLESS=true
DEFAULT_TIMEOUT=30000
BROWSER_PROFILE=browser

# Logging
LOG_LEVEL=INFO
```

### 7. Configure Consumers

Edit `data/consumers.json`:

```json
[
    {
        "name": "Nana - Shop",
        "ca": "241111117048",
        "threshold": 1000,
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

## Running the Project

```bash
# Ensure virtual environment is activated
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
  State manager ready
[3/6] Launching browser...
  SBPDCL checker browser ready
[4/6] Checking balances...

  [1/1] Nana - Shop
      CA: XXXXXXXX7048
      Balance: ₹448.58
      Threshold: ₹1,000.00
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

## Scheduling (Windows Task Scheduler)

The application runs automatically every 3 hours via Windows Task Scheduler. No CMD window opens — it runs silently in the background.

### Task Details

| Property | Value |
|----------|-------|
| Task Name | `SBPDCL Monitor` |
| Schedule | Every 3 hours (00:00, 03:00, 06:00, ...) |
| Action | `powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File run_hidden.ps1` |
| Log File | `logs/task_scheduler.log` |

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

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather | — |
| `TELEGRAM_CHAT_ID` | Default Telegram chat ID for notifications | — |
| `SBPDCL_URL` | SBPDCL portal URL | `https://www.sbpdcl.co.in` |
| `HEADLESS` | Run browser in headless mode | `true` |
| `DEFAULT_TIMEOUT` | Playwright timeout (ms) | `30000` |
| `BROWSER_PROFILE` | Browser profile directory | `browser` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

### Notification Logic

| Scenario | Action |
|----------|--------|
| First check, balance below threshold | Send alert |
| Balance drops below threshold (was above) | Send alert |
| Balance still below threshold (already notified) | Skip |
| Balance recovers above threshold | Skip |

## Development

### Code Quality

- Follows PEP 8 style guidelines
- Uses `pathlib` for file operations
- Type hints for better code clarity
- Comprehensive logging throughout

### Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

## License

MIT License - See LICENSE file for details.

## Disclaimer

This application is for educational purposes. Ensure you have proper authorization to access SBPDCL services programmatically.
