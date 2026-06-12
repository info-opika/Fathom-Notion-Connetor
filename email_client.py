"""
Send daily digest emails via Gmail SMTP.
Requires a Google App Password (not your regular Gmail password).
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


def is_configured() -> bool:
    return bool(
        os.environ.get("GMAIL_ADDRESS")
        and os.environ.get("GMAIL_APP_PASSWORD")
        and os.environ.get("TEAM_EMAILS")
    )


def send_digest(calls: list[dict], recipients: list[str]) -> bool:
    """Send a plain-text digest email summarizing processed calls."""
    sender = os.environ.get("GMAIL_ADDRESS", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")

    if not sender or not app_password:
        logger.warning(
            "Email not sent: set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env "
            "(Google Account -> Security -> App passwords)"
        )
        return False

    if not recipients:
        logger.info("Email not sent: no TEAM_EMAILS configured")
        return False

    subject_date = calls[0].get("date") if calls else ""
    subject = f"Daily Call Summaries - {subject_date}" if subject_date else "Daily Call Summaries"

    sections = []
    for call in calls:
        action_lines = []
        for item in call.get("action_items", []):
            action_lines.append(
                f"  - {item.get('owner', 'Unassigned')}: {item.get('task', '')} "
                f"(Due: {item.get('due_date', 'TBD')})"
            )
        actions_block = "\n".join(action_lines) if action_lines else "  (none identified)"

        section = f"""Call: {call.get('title', 'Untitled')}
Date: {call.get('date', '')}
Duration: {call.get('duration', '')}
Attendees: {', '.join(call.get('attendees', []))}

Summary:
{call.get('summary', 'No summary available')}

Action Items:
{actions_block}"""

        if call.get("notion_url"):
            section += f"\n\nNotion: {call['notion_url']}"
        if call.get("url"):
            section += f"\nFathom: {call['url']}"

        sections.append(section)

    body = f"""Hi Team,

Here are your call summaries and action items:

{'=' * 40}

{chr(10).join(sections)}

{'=' * 40}

Best regards,
Call Summary Bot
"""

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(sender, app_password)
            server.sendmail(sender, recipients, msg.as_string())

        logger.info("Digest email sent to %s", ", ".join(recipients))
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail auth failed. Use an App Password from "
            "https://myaccount.google.com/apppasswords (not your regular password)"
        )
        return False
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False
