"""Simple web server for SBPDCL Smart Meter Dashboard.

Serves the frontend dashboard and provides live API endpoints to fetch
data and trigger balance checks.
Zero external dependencies required (uses Python standard library).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

_PORT = 5000
_ROOT = Path(__file__).resolve().parent
_DATA_DIR = _ROOT / "data"
_HISTORY_FILE = _DATA_DIR / "history.csv"
_CONSUMERS_FILE = _DATA_DIR / "consumers.json"
_NOTIFIED_FILE = _DATA_DIR / "notified.json"


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for SBPDCL dashboard."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(_ROOT), **kwargs)

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/" or self.path == "/index.html":
            self.path = "/index.html"
            return super().do_GET()

        if self.path == "/api/data":
            self._handle_api_data()
            return

        return super().do_GET()

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/api/run":
            self._handle_api_run()
            return

        self.send_error(404, "Endpoint not found")

    def _handle_api_data(self) -> None:
        """Return current status, consumers, and recent history as JSON."""
        # 1. Read consumers
        consumers = []
        if _CONSUMERS_FILE.exists():
            try:
                consumers = json.loads(_CONSUMERS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 2. Read notified state
        notified = {}
        if _NOTIFIED_FILE.exists():
            try:
                notified = json.loads(_NOTIFIED_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 3. Read history rows
        history = []
        if _HISTORY_FILE.exists():
            try:
                with _HISTORY_FILE.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        history.append(row)
            except Exception:
                pass

        # Extract latest stats
        latest_row = history[-1] if history else {}
        balance = float(latest_row.get("balance", 1155.94))
        threshold = float(latest_row.get("threshold", 100.0))

        response = {
            "consumers": consumers,
            "balance": balance,
            "threshold": threshold,
            "is_low": balance < threshold,
            "notified": notified,
            "recent_history": history[-10:],
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def _handle_api_run(self) -> None:
        """Execute main.py and return result."""
        python_exe = sys.executable
        main_script = _ROOT / "main.py"

        try:
            # Run main.py in headless mode
            env = dict(**dict(subprocess.os.environ))
            env["HEADLESS"] = "true"

            proc = subprocess.run(
                [python_exe, str(main_script)],
                cwd=str(_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )

            # Re-read latest history
            history = []
            if _HISTORY_FILE.exists():
                with _HISTORY_FILE.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        history.append(row)

            latest = history[-1] if history else {}
            balance = float(latest.get("balance", 0.0))

            res = {
                "success": proc.returncode == 0,
                "balance": balance,
                "output": proc.stdout[-500:] if proc.stdout else "",
            }
            status_code = 200
        except Exception as exc:
            res = {"success": False, "error": str(exc)}
            status_code = 500

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(res).encode("utf-8"))


def run_server() -> None:
    """Start the HTTP server and open the browser."""
    server_address = ("127.0.0.1", _PORT)
    httpd = HTTPServer(server_address, DashboardHandler)

    url = f"http://localhost:{_PORT}"
    print("=" * 60)
    print("  SBPDCL SMART METER DASHBOARD SERVER")
    print("=" * 60)
    print(f"  Dashboard URL: {url}")
    print("  Press Ctrl+C to stop the server\n")

    # Open browser automatically
    webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
