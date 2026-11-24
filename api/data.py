from http.server import BaseHTTPRequestHandler
import json
import csv
from pathlib import Path


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function to serve live meter data."""

    def do_GET(self):
        root = Path(__file__).resolve().parent.parent
        history_file = root / "data" / "history.csv"
        consumers_file = root / "data" / "consumers.json"
        notified_file = root / "data" / "notified.json"

        consumers = []
        if consumers_file.exists():
            try:
                consumers = json.loads(consumers_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        notified = {}
        if notified_file.exists():
            try:
                notified = json.loads(notified_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        history = []
        if history_file.exists():
            try:
                with history_file.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        history.append(row)
            except Exception:
                pass

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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
