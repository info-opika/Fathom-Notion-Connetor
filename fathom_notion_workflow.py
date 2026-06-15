#!/usr/bin/env python3
"""
Fathom → Notion → Email Workflow
Fetches calls via Fathom API, writes to Notion, extracts action items via Claude, emails digest.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta

import anthropic
import requests
from dotenv import load_dotenv

from email_client import is_configured as email_configured, send_digest
from notion_client import NotionClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

FATHOM_API_BASE = "https://api.fathom.ai/external/v1"


class FathomNotionWorkflow:
    """Main workflow: Fathom API + Notion API + Claude + Gmail SMTP."""

    def __init__(self):
        self._validate_config()

        self.anthropic_client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
        self.fathom_api_key = os.environ.get("FATHOM_API_KEY")
        self.notion = NotionClient()
        self.team_emails = [
            e.strip()
            for e in os.environ.get("TEAM_EMAILS", "").split(",")
            if e.strip()
        ]
        self.processed_calls_file = "processed_calls.json"
        self.lookback_hours = int(os.environ.get("FATHOM_LOOKBACK_HOURS", "24"))
        self.processed_calls = self._load_processed_calls()

    def _validate_config(self):
        missing = []
        for var in ("ANTHROPIC_API_KEY", "FATHOM_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID"):
            if not os.environ.get(var):
                missing.append(var)
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

        if not email_configured():
            logger.warning(
                "Email not fully configured — digest will be skipped. "
                "Set RESEND_API_KEY + EMAIL_FROM + TEAM_EMAILS (Render), or "
                "GMAIL_ADDRESS + GMAIL_APP_PASSWORD + TEAM_EMAILS (local)."
            )

    def _load_processed_calls(self) -> set:
        if os.path.exists(self.processed_calls_file):
            try:
                with open(self.processed_calls_file, "r") as f:
                    data = json.load(f)
                    return set(data.get("call_ids", []))
            except Exception as e:
                logger.warning("Could not load processed calls file: %s", e)
        return set()

    def _save_processed_calls(self):
        try:
            with open(self.processed_calls_file, "w") as f:
                json.dump(
                    {
                        "call_ids": list(self.processed_calls),
                        "last_updated": datetime.now().isoformat(),
                    },
                    f,
                )
        except Exception as e:
            logger.error("Could not save processed calls: %s", e)

    def _format_duration(self, meeting: dict) -> str:
        start = meeting.get("recording_start_time")
        end = meeting.get("recording_end_time")
        if not start or not end:
            return "Unknown"
        try:
            s = datetime.fromisoformat(start.replace("Z", "+00:00"))
            e = datetime.fromisoformat(end.replace("Z", "+00:00"))
            minutes = max(1, int((e - s).total_seconds() / 60))
            return f"{minutes} minutes"
        except ValueError:
            return "Unknown"

    def _format_transcript(self, items: list | None) -> str:
        if not items:
            return ""
        return "\n".join(
            f"{item.get('speaker', {}).get('display_name', 'Unknown')}: {item.get('text', '')}"
            for item in items
        )

    def _meeting_to_call(self, meeting: dict) -> dict:
        summary_obj = meeting.get("default_summary") or {}
        summary = summary_obj.get("markdown_formatted") or ""
        attendees = [
            inv.get("name") or inv.get("email") or "Unknown"
            for inv in meeting.get("calendar_invitees", [])
        ]
        created_at = meeting.get("created_at", "")
        date = created_at[:10] if created_at else datetime.now().strftime("%Y-%m-%d")

        return {
            "call_id": str(meeting.get("recording_id")),
            "title": meeting.get("title") or meeting.get("meeting_title") or "Untitled Call",
            "date": date,
            "duration": self._format_duration(meeting),
            "attendees": attendees,
            "summary": summary,
            "transcript": self._format_transcript(meeting.get("transcript")),
            "url": meeting.get("url", ""),
        }

    def fetch_new_calls(self) -> list:
        since = (datetime.utcnow() - timedelta(hours=self.lookback_hours)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        logger.info("Fetching calls from Fathom API (last %s hours, since %s)...", self.lookback_hours, since)

        try:
            headers = {"X-Api-Key": self.fathom_api_key}
            params = {
                "created_after": since,
                "include_summary": "true",
                "include_transcript": "true",
            }

            all_meetings = []
            cursor = None

            while True:
                if cursor:
                    params["cursor"] = cursor
                elif "cursor" in params:
                    del params["cursor"]

                response = requests.get(
                    f"{FATHOM_API_BASE}/meetings",
                    headers=headers,
                    params=params,
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
                all_meetings.extend(data.get("items", []))
                cursor = data.get("next_cursor")
                if not cursor:
                    break

            calls = [self._meeting_to_call(m) for m in all_meetings]
            new_calls = [
                c for c in calls if c.get("call_id") and c["call_id"] not in self.processed_calls
            ]
            logger.info("Found %s new call(s)", len(new_calls))
            return new_calls

        except requests.HTTPError as e:
            logger.error("Fathom API error: %s", e)
            if e.response is not None and e.response.status_code == 401:
                logger.error("Invalid FATHOM_API_KEY.")
            return []
        except Exception as e:
            logger.error("Error fetching calls: %s", e)
            return []

    def extract_action_items(self, call_summary: str, transcript: str) -> list:
        default_due = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        try:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Extract all action items from this call.

Summary:
{call_summary}

Transcript:
{transcript[:8000]}

Return ONLY a JSON array:
[{{"owner": "Name", "task": "Task description", "due_date": "YYYY-MM-DD"}}]

If no due date is mentioned, use {default_due}. If none found, return [].""",
                    }
                ],
            )
            text = response.content[0].text
            match = re.search(r"\[.*\]", text, re.DOTALL)
            return json.loads(match.group()) if match else []
        except Exception as e:
            logger.error("Error extracting action items: %s", e)
            return []

    def create_notion_page(self, call_data: dict, action_items: list) -> str | None:
        """Create Notion page. Returns page URL on success, None on failure."""
        logger.info("Creating Notion page for: %s", call_data.get("title"))
        try:
            page_url = self.notion.create_call_page(call_data, action_items)
            logger.info("Notion page created: %s", page_url)
            self.processed_calls.add(str(call_data.get("call_id")))
            return page_url
        except Exception as e:
            logger.error("Error creating Notion page: %s", e)
            return None

    def send_daily_digest(self, calls_processed: list) -> bool:
        if not calls_processed:
            return False
        return send_digest(calls_processed, self.team_emails)

    def run(self):
        logger.info("=" * 60)
        logger.info("Starting Fathom -> Notion -> Email Workflow")
        logger.info("=" * 60)

        new_calls = self.fetch_new_calls()
        if not new_calls:
            logger.info("No new calls to process")
            logger.info("=" * 60)
            return

        logger.info("Processing %s new call(s)", len(new_calls))
        processed = []

        for call in new_calls:
            try:
                action_items = self.extract_action_items(
                    call.get("summary", ""),
                    call.get("transcript", ""),
                )
                page_url = self.create_notion_page(call, action_items)
                if page_url:
                    call["action_items"] = action_items
                    call["notion_url"] = page_url
                    processed.append(call)
            except Exception as e:
                logger.error("Error processing call %s: %s", call.get("title"), e)

        self._save_processed_calls()

        if processed:
            if email_configured():
                self.send_daily_digest(processed)
            else:
                logger.info(
                    "Processed %s call(s) to Notion. Email skipped (not configured).",
                    len(processed),
                )
            logger.info("Successfully processed %s call(s)", len(processed))

        logger.info("=" * 60)
        logger.info("Workflow completed")
        logger.info("=" * 60)


def main():
    FathomNotionWorkflow().run()


if __name__ == "__main__":
    main()
