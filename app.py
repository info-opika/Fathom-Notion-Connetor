"""
Render web service entrypoint for FastCron integration.

GET /health  — keep-alive ping (no auth)
GET /run?secret=...  — start workflow in background (requires CRON_SECRET)
GET /status  — last run state (optional debugging)
"""

import logging
import os
import threading
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_running = False
_run_lock = threading.Lock()
_last_run: dict = {}


def _run_workflow():
    from fathom_notion_workflow import FathomNotionWorkflow

    FathomNotionWorkflow().run()


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.get("/status")
def status():
    with _run_lock:
        return jsonify({"running": _running, "last_run": _last_run}), 200


@app.get("/run")
def run_workflow():
    global _running, _last_run

    expected = os.environ.get("CRON_SECRET", "")
    if not expected:
        logger.error("CRON_SECRET is not configured")
        return jsonify({"error": "server misconfigured"}), 500

    if request.args.get("secret") != expected:
        return jsonify({"error": "unauthorized"}), 401

    with _run_lock:
        if _running:
            return jsonify({"status": "already_running", "last_run": _last_run}), 409
        _running = True
        _last_run = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    def background():
        global _running, _last_run
        try:
            logger.info("Background workflow started")
            _run_workflow()
            with _run_lock:
                _last_run = {
                    "status": "completed",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
            logger.info("Background workflow completed")
        except Exception as exc:
            logger.exception("Background workflow failed")
            with _run_lock:
                _last_run = {
                    "status": "error",
                    "error": str(exc),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            with _run_lock:
                _running = False

    threading.Thread(target=background, daemon=True).start()
    return jsonify({"status": "started", "message": "Workflow running in background"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
