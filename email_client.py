"""
Send daily digest emails via Resend (HTTPS) or Gmail SMTP.

Resend is preferred when RESEND_API_KEY is set (works on Render free tier).
Gmail SMTP is used as a fallback for local development.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


def _team_recipients() -> list[str]:
    return [e.strip() for e in os.environ.get("TEAM_EMAILS", "").split(",") if e.strip()]


def _resend_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY") and _email_from())


def _gmail_configured() -> bool:
    return bool(
        os.environ.get("GMAIL_ADDRESS")
        and os.environ.get("GMAIL_APP_PASSWORD")
    )


def _email_from() -> str:
    """Sender address. Resend requires a verified domain in EMAIL_FROM."""
    explicit = os.environ.get("EMAIL_FROM", "").strip()
    if explicit:
        return explicit
    gmail = os.environ.get("GMAIL_ADDRESS", "").strip()
    if gmail:
        return f"Call Summary Bot <{gmail}>"
    return ""


def is_configured() -> bool:
    return bool(_team_recipients() and (_resend_configured() or _gmail_configured()))


def _build_digest(calls: list[dict]) -> tuple[str, str]:
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
    return subject, body


def _send_via_resend(subject: str, body: str, recipients: list[str]) -> bool:
    import resend

    resend.api_key = os.environ["RESEND_API_KEY"]
    resend.Emails.send(
        {
            "from": _email_from(),
            "to": recipients,
            "subject": subject,
            "text": body,
        }
    )
    return True


def _send_via_gmail(subject: str, body: str, recipients: list[str]) -> bool:
    sender = os.environ.get("GMAIL_ADDRESS", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(sender, app_password)
        server.sendmail(sender, recipients, msg.as_string())
    return True


def send_digest(calls: list[dict], recipients: list[str]) -> bool:
    """Send a plain-text digest email summarizing processed calls."""
    if not recipients:
        logger.info("Email not sent: no TEAM_EMAILS configured")
        return False

    subject, body = _build_digest(calls)

    if _resend_configured():
        try:
            _send_via_resend(subject, body, recipients)
            logger.info("Digest email sent via Resend to %s", ", ".join(recipients))
            return True
        except Exception as e:
            logger.error("Failed to send email via Resend: %s", e)
            return False

    if not _gmail_configured():
        logger.warning(
            "Email not sent: set RESEND_API_KEY + EMAIL_FROM, or "
            "GMAIL_ADDRESS + GMAIL_APP_PASSWORD (see .env.example)"
        )
        return False

    try:
        _send_via_gmail(subject, body, recipients)
        logger.info("Digest email sent via Gmail to %s", ", ".join(recipients))
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Gmail auth failed. Use an App Password from "
            "https://myaccount.google.com/apppasswords (not your regular password)"
        )
        return False
    except Exception as e:
        logger.error("Failed to send email via Gmail: %s", e)
        return False
