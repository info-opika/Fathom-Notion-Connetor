# Fathom → Notion → Email Workflow
## Python Automation with Claude API & MCP Servers

A complete Python workflow that automates call recording summaries from Fathom to Notion with daily email digests using Claude's API and connected MCP servers.

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Setup Instructions](#setup-instructions)
3. [Configuration](#configuration)
4. [Running the Workflow](#running-the-workflow)
5. [Scheduling Options](#scheduling-options)
6. [How It Works](#how-it-works)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys and settings

# 3. Test the workflow once
python scheduler.py --once

# 4. Start the scheduler (runs daily at 9 AM)
python scheduler.py
```

---

## Setup Instructions

### Step 1: Get Required API Keys

#### Anthropic API Key
1. Go to https://console.anthropic.com/account/keys
2. Create a new API key
3. Copy it to your `.env` file

#### Fathom API Key
1. Log into Fathom
2. Click your **profile/avatar** → **Settings**
3. Go to **API Access** section
4. Click **"Generate API Key"**
5. Copy it to your `.env` file

#### Notion Database ID
1. Open your Notion call summaries database
2. Copy the URL: `https://notion.so/abc123def456?v=xyz`
3. Extract the ID: `abc123def456` (part after `/`)
4. Paste into `.env`

### Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
ANTHROPIC_API_KEY=sk-ant-...
FATHOM_API_KEY=your_fathom_key
NOTION_DATABASE_ID=abc123def456
TEAM_EMAILS=john@company.com,sarah@company.com,mike@company.com
SCHEDULE_TIME=09:00
TIMEZONE=America/New_York
```

### Step 3: Verify Connections

The workflow uses Claude's API with these MCP servers:
- ✅ **Fathom MCP**: Fetches call recordings
- ✅ **Notion MCP**: Creates call summary pages
- ✅ **Gmail MCP**: Sends daily digests

These are already connected to your Claude.ai account.

### Step 4: Test the Workflow

```bash
# Run once to verify everything works
python scheduler.py --once
```

You should see:
```
INFO - Fetching new calls from Fathom...
INFO - Creating Notion page for: Client Strategy Meeting
INFO - ✓ Notion page created
INFO - ✓ Daily digest email sent
INFO - Workflow completed successfully
```

---

## Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key | `sk-ant-...` |
| `FATHOM_API_KEY` | Yes | Fathom API key | `fathom_...` |
| `NOTION_DATABASE_ID` | Yes | Notion database ID | `abc123def456` |
| `TEAM_EMAILS` | Yes | Recipients for digest | `email1@co.com,email2@co.com` |
| `SCHEDULE_TIME` | No | Daily run time (24h format) | `09:00` (default) |
| `TIMEZONE` | No | Timezone for scheduling | `America/New_York` (default: UTC) |

### Notion Database Structure

The workflow creates pages with these properties:

```
📞 Call Title
━━━━━━━━━━━━━━━━━━━━━━━
🆔 Fathom_Call_ID: call_abc123
📅 Date: 2024-06-12
⏱️  Duration: 45 minutes
👥 Attendees: John, Sarah, Mike
📋 Status: New

## Summary
Discussion of Q3 planning and deliverables...

## Action Items
- John: Prepare pricing proposal (Due: 2024-06-15)
- Sarah: Update timeline with feedback
- Mike: Schedule follow-up call
```

---

## Running the Workflow

### Option 1: Run Once (Testing)

```bash
python scheduler.py --once
```

Use this to:
- Test your configuration
- Debug issues
- Verify Fathom/Notion/Gmail connections

### Option 2: Start the Scheduler (Production)

```bash
python scheduler.py
```

This will:
- Run daily at your configured `SCHEDULE_TIME`
- Log all activity to `workflow.log`
- Continue running in background

Press `Ctrl+C` to stop the scheduler.

---

## Scheduling Options

### Option A: Python Scheduler (Built-in)

**Recommended for development.** The scheduler runs in the foreground.

```bash
python scheduler.py
```

**To run in background:**

#### Linux/Mac
```bash
nohup python scheduler.py > workflow.log 2>&1 &
# Check if running:
ps aux | grep scheduler.py
# Stop:
pkill -f scheduler.py
```

#### Windows
```cmd
# In Command Prompt (run as Administrator):
python scheduler.py
# Or use Task Scheduler (see below)
```

---

### Option B: System Cron (Linux/Mac)

**Best for production.** Runs automatically even if computer restarts.

1. Edit crontab:
```bash
crontab -e
```

2. Add this line (runs daily at 9 AM):
```cron
0 9 * * * cd /path/to/workflow && python scheduler.py --once >> workflow.log 2>&1
```

3. Verify:
```bash
crontab -l
```

**Common cron times:**
- `0 9 * * *` → 9:00 AM daily
- `0 */6 * * *` → Every 6 hours
- `*/30 * * * *` → Every 30 minutes

---

### Option C: Windows Task Scheduler

**Best for Windows production environments.**

1. Open Task Scheduler (search "Task Scheduler")
2. Click **Create Basic Task**
3. Name: `Fathom Notion Workflow`
4. Trigger: **Daily** at 9:00 AM
5. Action:
   - Program: `python`
   - Arguments: `C:\path\to\scheduler.py --once`
   - Start in: `C:\path\to\workflow`
6. Click OK

---

### Option D: Systemd Service (Linux)

**For always-running production service.**

1. Create `/etc/systemd/system/fathom-notion.service`:

```ini
[Unit]
Description=Fathom Notion Workflow
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/workflow
ExecStart=/usr/bin/python3 /path/to/scheduler.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

2. Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable fathom-notion
sudo systemctl start fathom-notion
```

3. Check status:
```bash
sudo systemctl status fathom-notion
```

---

## How It Works

### Workflow Architecture

```
1. Daily Trigger (9 AM or on schedule)
   ↓
2. Connect to Fathom via Claude API + Fathom MCP
   Fetch calls from last 24 hours
   ↓
3. Check Deduplication
   Compare Fathom Call IDs with processed_calls.json
   ↓
4. For Each New Call:
   a) Use Claude to extract action items
   b) Use Notion MCP to create page
   c) Add Fathom_Call_ID for deduplication
   ↓
5. Send Daily Digest
   Gmail MCP sends email to team with summaries
   ↓
6. Save State
   Update processed_calls.json to prevent duplicates
```

### Key Features

**Deduplication**
- Tracks processed Fathom Call IDs in `processed_calls.json`
- Prevents duplicate Notion pages on multiple runs
- Stores processed ID in Notion page for reference

**Claude API Integration**
- Uses Claude Sonnet 4.6 (cost-optimized)
- Extracts action items from call transcripts
- Processes multiple calls in parallel when possible

**MCP Server Usage**
- **Fathom MCP**: Real-time call data fetching
- **Notion MCP**: Page creation with formatting
- **Gmail MCP**: Professional email delivery

**Error Handling**
- Logs all errors with timestamps
- Continues processing remaining calls if one fails
- Provides actionable error messages

---

## Troubleshooting

### Workflow Not Running

**Check 1: Verify Python is installed**
```bash
python --version
# Should be Python 3.8 or higher
```

**Check 2: Verify dependencies are installed**
```bash
pip list | grep anthropic
# Should show: anthropic (version)
```

If missing:
```bash
pip install -r requirements.txt
```

**Check 3: Check logs**
```bash
tail -f workflow.log
```

---

### API Key Issues

**"Invalid API Key" error**

1. Verify key is in `.env`:
```bash
cat .env | grep ANTHROPIC_API_KEY
```

2. Verify key format:
- Anthropic keys start with `sk-ant-`
- Fathom keys are provided by Fathom

3. Test key directly:
```bash
echo $ANTHROPIC_API_KEY
```

---

### No Calls Processed

**Check 1: Verify Fathom has calls**
- Log into Fathom
- Check that calls are being recorded

**Check 2: Check if already processed**
```bash
cat processed_calls.json
# Should show processed call IDs
```

To reset (start fresh):
```bash
rm processed_calls.json
python scheduler.py --once
```

**Check 3: Check Fathom API key**
```bash
# In Python:
import os
from dotenv import load_dotenv
load_dotenv()
print(os.environ.get("FATHOM_API_KEY"))
```

---

### Notion Pages Not Created

**Check 1: Verify Notion database ID**
```bash
# Should be 26 characters (without hyphens)
echo $NOTION_DATABASE_ID | wc -c
```

**Check 2: Verify Notion access**
- Go to your Notion database
- Share with the email associated with Claude/MCP connection

**Check 3: Check Notion page structure**
The workflow creates pages with:
- Title: Call title from Fathom
- Properties: Date, Duration, Attendees, Fathom_Call_ID
- Content: Summary and action items

---

### Emails Not Sent

**Check 1: Verify team emails**
```bash
echo $TEAM_EMAILS
# Should show comma-separated emails
```

**Check 2: Verify Gmail MCP connection**
- Check that Gmail is connected in Claude.ai
- Verify email addresses are valid

**Check 3: Check for errors in logs**
```bash
grep -i "email\|gmail" workflow.log
```

---

### High API Costs

The workflow is designed to minimize costs:

- Uses Claude Sonnet 4.6 (fastest, most cost-effective)
- Fetches calls once per day
- Action item extraction uses efficient prompts
- Caches processed calls to avoid re-processing

**Cost estimate (monthly):**
- 30 calls/day × 30 days = 900 calls
- ~$0.15 per Fathom + Notion + Gmail operations
- **Total: ~$135/month** (varies by call volume)

To reduce costs further:
- Reduce frequency (run every 2 days instead)
- Batch multiple runs into single workflow

---

## Advanced Configuration

### Custom Prompt for Action Items

Edit `fathom_notion_workflow.py` in the `extract_action_items` method to customize how action items are extracted.

### Custom Email Template

Edit the `send_daily_digest` method to customize email formatting.

### Webhook Integration (Real-Time)

Currently the workflow runs on a schedule. To make it real-time:

1. Set up Fathom webhook to your server
2. Expose an HTTP endpoint that calls `workflow.run()`
3. Update scheduling logic to accept webhook triggers

---

## Support

- **Anthropic API Docs**: https://docs.claude.com/en/api/overview
- **Fathom Webhooks**: https://developers.fathom.ai/webhooks
- **Notion API**: https://developers.notion.com/reference
- **Schedule Library**: https://schedule.readthedocs.io/

---

**Last Updated**: June 12, 2026  
**Version**: 1.0.0
