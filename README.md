# SBPDCL Monitor

A production-ready application that monitors SBPDCL (South Bihar Power Distribution Company Limited) Smart Meter balance and sends WhatsApp notifications for low balance alerts.

## Features

- **Automated Balance Checking**: Uses Playwright for browser automation to fetch meter balance
- **WhatsApp Notifications**: Sends instant alerts via WhatsApp API when balance falls below threshold
- **Multi-Consumer Support**: Monitor multiple meters from a single configuration
- **State Management**: Prevents duplicate notifications and tracks notification history
- **Logging**: Comprehensive logging with file rotation for debugging and audit
- **Configurable Thresholds**: Set custom low balance thresholds per consumer

## Folder Structure

```
sbpdcl-monitor/
│
├── src/
│   ├── __init__.py          # Package initialization
│   ├── checker.py           # Browser automation for balance checking
│   ├── whatsapp.py          # WhatsApp notification handler
│   ├── config.py            # Configuration management
│   ├── logger.py            # Logging setup
│   ├── state.py             # State management
│   ├── models.py            # Data models
│   └── utils.py             # Utility functions
│
├── data/
│   ├── consumers.json       # Consumer configuration
│   ├── notified.json        # Notification tracking
│   └── history.csv          # Balance history logs
│
├── browser/                 # Browser profile data (auto-created)
├── logs/                    # Application logs
├── screenshots/             # Debug screenshots
├── tests/                   # Unit tests
│
├── .env.example             # Environment variables template
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── README.md                # Documentation
└── main.py                  # Application entry point
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/sbpdcl-monitor.git
cd sbpdcl-monitor
```

### 2. Virtual Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
# Install Chromium browser (required for automation)
playwright install chromium

# Install system dependencies (if needed)
playwright install-deps
```

### 5. Configure Environment Variables

```bash
# Copy the example configuration
cp .env.example .env

# Edit .env with your credentials
# Use your preferred text editor
```

## Running the Project

```bash
# Ensure virtual environment is activated
# Run the application
python main.py
```

## Configuration

### consumers.json

Configure your meter details in `data/consumers.json`:

```json
{
  "consumers": [
    {
      "id": "YOUR_CONSUMER_ID",
      "name": "Your Name",
      "meter_number": "YOUR_METER_NUMBER",
      "phone": "+91XXXXXXXXXX",
      "notify_threshold": 100.00
    }
  ]
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WHATSAPP_API_URL` | WhatsApp Business API endpoint | - |
| `WHATSAPP_API_TOKEN` | API authentication token | - |
| `SBPDCL_URL` | SBPDCL portal URL | https://www.sbpdcl.co.in |
| `CHECK_INTERVAL_MINUTES` | Balance check frequency | 60 |
| `LOW_BALANCE_THRESHOLD` | Default low balance threshold | 100.00 |
| `LOG_LEVEL` | Logging verbosity | INFO |

## Future Modules

This project is designed for modular implementation. The following modules will be developed in subsequent phases:

### Phase 2: Core Checker Module
- Playwright browser automation
- SBPDCL portal login
- Balance extraction logic
- Screenshot capture

### Phase 3: WhatsApp Integration
- WhatsApp Business API integration
- Message template management
- Notification retry mechanism

### Phase 4: State & History
- Consumer state tracking
- History logging to CSV
- Duplicate notification prevention

### Phase 5: Advanced Features
- Scheduled execution with cron/APScheduler
- Multiple browser profiles
- Email fallback notifications
- Dashboard/reporting

## Development

### Code Quality

- Follows PEP 8 style guidelines
- Uses `pathlib` for file operations
- Type hints for better code clarity
- Comprehensive logging throughout

### Testing

```bash
# Run tests (when available)
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

## License

MIT License - See LICENSE file for details.

## Disclaimer

This application is for educational purposes. Ensure you have proper authorization to access SBPDCL services programmatically.
