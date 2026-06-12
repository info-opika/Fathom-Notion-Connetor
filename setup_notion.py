#!/usr/bin/env python3
"""
Notion Database Setup Helper
Verifies database access and required properties via the Notion REST API.
"""

import logging
import os
import sys

from dotenv import load_dotenv

from notion_client import NotionClient, REQUIRED_PROPERTIES, normalize_id

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 60)
    logger.info("Notion Database Setup Helper")
    logger.info("=" * 60)

    if not os.environ.get("NOTION_TOKEN"):
        logger.error("NOTION_TOKEN not set. Create an integration at https://www.notion.so/my-integrations")
        return False

    if not os.environ.get("NOTION_DATABASE_ID"):
        logger.error("NOTION_DATABASE_ID not set. Check your .env file.")
        return False

    token = os.environ.get("NOTION_TOKEN", "")
    logger.info("Using database ID: %s", os.environ.get("NOTION_DATABASE_ID"))
    logger.info("Token format: %s (ntn_ and secret_ are both valid)", token[:8] + "...")

    try:
        client = NotionClient()

        logger.info("\n1. Verifying database access...")
        resolved_id = client.resolve_database_access()
        if resolved_id != normalize_id(os.environ.get("NOTION_DATABASE_ID", "")):
            logger.info(
                "Update NOTION_DATABASE_ID in .env to: %s", resolved_id
            )
        db = client.get_database()
        logger.info("Connected to database: %s", db.get("title", [{}])[0].get("plain_text", "Unknown"))

        logger.info("\n2. Checking / adding required properties...")
        result = client.verify_and_update_properties()
        logger.info("Title property: %s", result["title_property"])
        logger.info("Existing properties: %s", ", ".join(result["existing"]))
        if result["created"]:
            logger.info("Created properties: %s", ", ".join(result["created"]))
        if result["missing"]:
            logger.warning("Still missing (add manually): %s", ", ".join(result["missing"]))
            for name in result["missing"]:
                logger.info("  - %s (%s)", name, list(REQUIRED_PROPERTIES[name].keys())[0])

        logger.info("\n3. Testing page creation...")
        page_url = client.create_test_page()
        logger.info("Test page created: %s", page_url)
        logger.info("You can delete the test page from Notion.")

    except Exception as e:
        logger.error("Setup failed:")
        for line in str(e).split("\n"):
            logger.error("  %s", line)
        return False

    logger.info("\n" + "=" * 60)
    logger.info("Setup verification complete!")
    logger.info("=" * 60)
    logger.info("\nYou can now run:")
    logger.info("  python check_config.py      # verify all credentials")
    logger.info("  python test_email.py        # test Gmail digest")
    logger.info("  python scheduler.py --once  # run full workflow")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
