"""
Notion REST API client for call summary pages.
"""

import logging
import os
import re
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

REQUIRED_PROPERTIES = {
    "Fathom_Call_ID": {"rich_text": {}},
    "Date": {"date": {}},
    "Duration": {"rich_text": {}},
    "Attendees": {"rich_text": {}},
    "Status": {
        "select": {
            "options": [
                {"name": "New", "color": "blue"},
                {"name": "In Progress", "color": "yellow"},
                {"name": "Completed", "color": "green"},
                {"name": "Archived", "color": "gray"},
            ]
        }
    },
    "Summary": {"rich_text": {}},
    "Action Items": {"rich_text": {}},
}


def normalize_id(notion_id: str) -> str:
    """Strip hyphens from a Notion UUID."""
    return re.sub(r"-", "", notion_id.strip())


def format_uuid(notion_id: str) -> str:
    """Format a 32-char hex ID as UUID with hyphens."""
    raw = normalize_id(notion_id)
    if len(raw) != 32:
        return notion_id
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


class NotionClient:
    """Thin wrapper around the Notion REST API."""

    def __init__(self, token: str | None = None, database_id: str | None = None):
        self.token = token or os.environ.get("NOTION_TOKEN", "")
        self.database_id = normalize_id(database_id or os.environ.get("NOTION_DATABASE_ID", ""))
        self._title_property: str | None = None

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, *, raise_on_error: bool = True, **kwargs) -> dict | requests.Response:
        url = f"{NOTION_API_BASE}{path}"
        response = requests.request(method, url, headers=self.headers, timeout=60, **kwargs)
        if not response.ok:
            logger.error("Notion API %s %s failed: %s", method, path, response.text)
            if raise_on_error:
                response.raise_for_status()
            return response
        return response.json()

    def _find_inline_databases(self, page_id: str) -> list[dict]:
        """Find inline child_database blocks on a page (block id == database id)."""
        found = []
        cursor = None
        while True:
            path = f"/blocks/{format_uuid(page_id)}/children"
            if cursor:
                path += f"?start_cursor={cursor}"
            data = self._request("GET", path)
            for block in data.get("results", []):
                if block.get("type") == "child_database":
                    title = block.get("child_database", {}).get("title", "Untitled")
                    found.append({"id": normalize_id(block["id"]), "title": title})
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return found

    def _list_accessible_databases(self) -> list[dict]:
        """Search for databases the integration can already access."""
        data = self._request(
            "POST",
            "/search",
            json={"filter": {"property": "object", "value": "database"}, "page_size": 20},
        )
        results = []
        for item in data.get("results", []):
            title = "Untitled"
            title_parts = item.get("title", [])
            if title_parts:
                title = title_parts[0].get("plain_text", title)
            results.append({"id": normalize_id(item["id"]), "title": title})
        return results

    def resolve_database_access(self) -> str:
        """
        Verify or resolve the database ID.
        Handles full-page databases and inline databases embedded in a page.
        """
        db_uuid = format_uuid(self.database_id)

        # 1. Direct database access (full-page database with correct sharing)
        db_response = self._request(
            "GET", f"/databases/{db_uuid}", raise_on_error=False
        )
        if isinstance(db_response, dict):
            return self.database_id

        # 2. Maybe the ID is a regular page containing an inline database
        page_response = self._request(
            "GET", f"/pages/{db_uuid}", raise_on_error=False
        )
        if isinstance(page_response, dict):
            inline = self._find_inline_databases(self.database_id)
            if len(inline) == 1:
                logger.info(
                    "Resolved inline database on page: %s (id: %s)",
                    inline[0]["title"],
                    inline[0]["id"],
                )
                self.database_id = inline[0]["id"]
                self._title_property = None
                return self.database_id
            if len(inline) > 1:
                names = ", ".join(f"{d['title']} ({d['id']})" for d in inline)
                raise ValueError(
                    f"Page contains multiple databases. Set NOTION_DATABASE_ID to one of: {names}"
                )
            raise ValueError(
                "NOTION_DATABASE_ID points to a page, not a database. "
                "Open your table as a full page (click ... -> Open as full page) "
                "and copy the ID from that URL, or paste the inline database ID."
            )

        # 3. Neither worked — almost always a sharing/permissions issue
        accessible = self._list_accessible_databases()
        msg = (
            "Integration cannot access this database. "
            "Open the database in Notion -> top-right ... -> Connections -> "
            "add your integration (Fathom-Notion-Connector)."
        )
        if accessible:
            msg += "\n\nDatabases your integration CAN access:"
            for db in accessible:
                msg += f"\n  - {db['title']}: {db['id']}"
            msg += "\n\nCopy one of those IDs into NOTION_DATABASE_ID if needed."
        else:
            msg += (
                "\n\nNo databases found for this integration yet. "
                "Share at least one database via Connections, then re-run setup."
            )
        raise ValueError(msg)

    def get_database(self) -> dict:
        self.resolve_database_access()
        return self._request("GET", f"/databases/{format_uuid(self.database_id)}")

    def get_title_property_name(self) -> str:
        if self._title_property:
            return self._title_property
        db = self.get_database()
        for name, schema in db.get("properties", {}).items():
            if schema.get("type") == "title":
                self._title_property = name
                return name
        raise ValueError("Database has no title property")

    def verify_and_update_properties(self) -> dict:
        """
        Check required properties exist; add any that are missing.
        Returns summary dict with existing, created, and missing lists.
        """
        db = self.get_database()
        existing = db.get("properties", {})
        title_prop = self.get_title_property_name()

        result = {
            "title_property": title_prop,
            "existing": list(existing.keys()),
            "created": [],
            "missing": [],
        }

        to_add = {}
        for name, schema in REQUIRED_PROPERTIES.items():
            if name not in existing:
                to_add[name] = schema

        if to_add:
            logger.info("Adding missing Notion properties: %s", list(to_add.keys()))
            self._request(
                "PATCH",
                f"/databases/{format_uuid(self.database_id)}",
                json={"properties": to_add},
            )
            result["created"] = list(to_add.keys())

        # Refresh and verify
        db = self.get_database()
        for name in REQUIRED_PROPERTIES:
            if name not in db.get("properties", {}):
                result["missing"].append(name)

        return result

    def _rich_text(self, content: str) -> dict:
        # Notion rich_text blocks max 2000 chars each
        text = content[:2000] if content else ""
        return {"rich_text": [{"type": "text", "text": {"content": text}}]}

    def _title_value(self, content: str) -> dict:
        return {"title": [{"type": "text", "text": {"content": content[:2000]}}]}

    def _page_blocks(self, summary: str, action_items_text: str, fathom_url: str = "") -> list:
        blocks = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Summary"}}]},
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": (summary or "No summary available")[:2000]}}]},
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Action Items"}}]},
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": (action_items_text or "No action items identified")[:2000]},
                        }
                    ]
                },
            },
        ]
        if fathom_url:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {"type": "text", "text": {"content": "Fathom recording: "}},
                            {"type": "text", "text": {"content": fathom_url, "link": {"url": fathom_url}}},
                        ]
                    },
                }
            )
        return blocks

    def create_call_page(self, call_data: dict, action_items: list) -> str:
        """Create a database page for a call. Returns the page URL."""
        title_prop = self.get_title_property_name()
        title = call_data.get("title") or "Untitled Call"

        action_items_text = "\n".join(
            f"- {item.get('owner', 'Unassigned')}: {item.get('task', '')} "
            f"(Due: {item.get('due_date', 'TBD')})"
            for item in action_items
        )

        summary = call_data.get("summary", "")
        attendees = ", ".join(call_data.get("attendees", []))
        date = call_data.get("date") or datetime.now().strftime("%Y-%m-%d")

        properties = {
            title_prop: self._title_value(title),
            "Fathom_Call_ID": self._rich_text(str(call_data.get("call_id", ""))),
            "Date": {"date": {"start": date}},
            "Duration": self._rich_text(call_data.get("duration", "")),
            "Attendees": self._rich_text(attendees),
            "Status": {"select": {"name": "New"}},
            "Summary": self._rich_text(summary[:2000]),
            "Action Items": self._rich_text(action_items_text[:2000]),
        }

        # Only include properties that exist on the database
        db = self.get_database()
        db_props = set(db.get("properties", {}).keys())
        filtered = {k: v for k, v in properties.items() if k in db_props}

        page = self._request(
            "POST",
            "/pages",
            json={
                "parent": {"database_id": format_uuid(self.database_id)},
                "properties": filtered,
                "children": self._page_blocks(
                    summary, action_items_text, call_data.get("url", "")
                ),
            },
        )
        return page.get("url", "")

    def create_test_page(self) -> str:
        """Create a setup verification test page. Returns the page URL."""
        return self.create_call_page(
            {
                "call_id": "test_setup_verification",
                "title": "Test Call - Setup Verification",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "duration": "5 minutes",
                "attendees": ["Setup Bot"],
                "summary": "This is a test page created during setup. You can delete it.",
                "url": "",
            },
            [],
        )
