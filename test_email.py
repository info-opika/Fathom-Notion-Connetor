#!/usr/bin/env python3
"""Send a test digest email to verify Gmail SMTP config."""

import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from email_client import send_digest

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    recipients = [e.strip() for e in os.environ.get("TEAM_EMAILS", "").split(",") if e.strip()]
    if not recipients:
        logger.error("Set TEAM_EMAILS in .env")
        return False

    test_call = {
        "title": "Test Call - Email Verification",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "duration": "5 minutes",
        "attendees": ["Test Bot"],
        "summary": "This is a test email from the Fathom-to-Notion workflow.",
        "action_items": [{"owner": "You", "task": "Delete this test email", "due_date": "2099-01-01"}],
        "notion_url": "https://notion.so",
        "url": "https://fathom.video",
    }

    ok = send_digest([test_call], recipients)
    if ok:
        logger.info("Test email sent to: %s", ", ".join(recipients))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
