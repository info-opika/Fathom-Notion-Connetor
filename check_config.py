#!/usr/bin/env python3
"""
Pre-flight check: verify all credentials before running the workflow.
"""

import logging
import os
import sys

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check(name: str, ok: bool, detail: str = ""):
    status = "OK" if ok else "MISSING"
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    logger.info(msg)
    return ok


def main():
    logger.info("=" * 60)
    logger.info("Workflow Pre-flight Check")
    logger.info("=" * 60)

    all_ok = True

    # Anthropic
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    all_ok &= check("ANTHROPIC_API_KEY", bool(anthropic_key), anthropic_key[:12] + "..." if anthropic_key else "")

    # Fathom
    fathom_key = os.environ.get("FATHOM_API_KEY", "")
    all_ok &= check("FATHOM_API_KEY", bool(fathom_key))
    if fathom_key:
        try:
            r = requests.get(
                "https://api.fathom.ai/external/v1/meetings",
                headers={"X-Api-Key": fathom_key},
                params={"limit": 1},
                timeout=15,
            )
            check("Fathom API connection", r.status_code == 200, f"HTTP {r.status_code}")
            all_ok &= r.status_code == 200
        except Exception as e:
            check("Fathom API connection", False, str(e))
            all_ok = False

    # Notion
    notion_token = os.environ.get("NOTION_TOKEN", "")
    notion_db = os.environ.get("NOTION_DATABASE_ID", "")
    all_ok &= check("NOTION_TOKEN", bool(notion_token), notion_token[:8] + "..." if notion_token else "")
    all_ok &= check("NOTION_DATABASE_ID", bool(notion_db), notion_db or "")
    if notion_token and notion_db:
        try:
            from notion_client import NotionClient

            client = NotionClient()
            client.resolve_database_access()
            db = client.get_database()
            title = db.get("title", [{}])[0].get("plain_text", "Unknown")
            check("Notion database access", True, title)
        except Exception as e:
            check("Notion database access", False, str(e).split("\n")[0])
            all_ok = False

    # Gmail (optional but recommended)
    gmail_addr = os.environ.get("GMAIL_ADDRESS", "")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    team = os.environ.get("TEAM_EMAILS", "")
    email_ok = bool(gmail_addr and gmail_pass and team)
    check(
        "Gmail digest (GMAIL_ADDRESS + GMAIL_APP_PASSWORD + TEAM_EMAILS)",
        email_ok,
        "configured" if email_ok else "optional — digest will be skipped",
    )

    # Claude API quick test
    if anthropic_key:
        try:
            client = anthropic.Anthropic(api_key=anthropic_key)
            client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            check("Anthropic API connection", True)
        except Exception as e:
            check("Anthropic API connection", False, str(e)[:80])
            all_ok = False

    logger.info("=" * 60)
    if all_ok:
        logger.info("All checks passed. Run: python scheduler.py --once")
    else:
        logger.error("Some checks failed. Fix .env and re-run.")
    logger.info("=" * 60)
    return all_ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
