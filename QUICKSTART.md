# Fathom → Notion → Email Workflow - Quick Start

Get the workflow running in 5 minutes.

---

## Step 1: Install Dependencies (1 min)

```bash
cd /path/to/workflow
pip install -r requirements.txt
```

---

## Step 2: Get API Keys (3 min)

### Anthropic API Key
1. Go to: https://console.anthropic.com/account/keys
2. Create new API key
3. Copy the key (starts with `sk-ant-`)

### Fathom API Key
1. Log into Fathom
2. Click profile → **Settings**
3. Go to **API Access**
4. Click **"Generate API Key"**
5. Copy the key

### Notion Database ID
1. Open your Notion call summaries database
2. Copy the URL: `https://notion.so/abc123def456?v=xyz`
3. Extract ID: `abc123def456` (26 characters after `/`)

---

## Step 3: Configure Environment (1 min)

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
FATHOM_API_KEY=xxxxx
NOTION_DATABASE_ID=abc123def456
TEAM_EMAILS=john@company.com,sarah@company.com
SCHEDULE_TIME=09:00
```

---

## Step 4: Verify Notion Setup (optional but recommended)

```bash
python setup_notion.py
```

This will:
- ✓ Verify Notion database exists
- ✓ Create required properties (Date, Duration, Attendees, etc.)
- ✓ Test page creation
- ✓ Delete test page

---

## Step 5: Test the Workflow (1 min)

```bash
python scheduler.py --once
```

Expected output:
```
INFO - Starting Fathom → Notion → Email Workflow
INFO - Fetching new calls from Fathom...
INFO - Found 2 new calls
INFO - Creating Notion page for: Client Strategy Meeting
INFO - ✓ Notion page created
INFO - Sending digest email to 2 recipients...
INFO - ✓ Daily digest email sent
INFO - Workflow completed successfully
```

---

## Step 6: Start the Scheduler

### Option A: Console (Development)
```bash
python scheduler.py
```

Press `Ctrl+C` to stop.

### Option B: Background (Linux/Mac)
```bash
nohup python scheduler.py > workflow.log 2>&1 &
```

### Option C: Background (Windows)
Open Command Prompt as Administrator:
```cmd
python scheduler.py
```
Then minimize the window.

### Option D: Cron (Linux/Mac - Automatic)
```bash
crontab -e
```

Add this line (runs daily at 9 AM):
```cron
0 9 * * * cd /path/to/workflow && python scheduler.py --once >> workflow.log 2>&1
```

### Option E: Task Scheduler (Windows - Automatic)
1. Press `Win + R`
2. Type `taskschd.msc`
3. Right-click → **Create Basic Task**
4. Name: `Fathom Notion Workflow`
5. Trigger: **Daily** at 9:00 AM
6. Action: `python C:\path\to\scheduler.py --once`
7. Click OK

---

## What Happens Next

**Every day at 9 AM (or whenever you schedule it):**

1. Fathom API is queried for calls from the last 24 hours
2. New calls are identified (compared against `processed_calls.json`)
3. For each new call:
   - Claude extracts action items from transcript
   - Notion page is created with:
     - Call title, date, duration, attendees
     - AI-generated summary
     - Extracted action items with owners
     - Fathom Call ID (for deduplication)
4. Daily email digest is sent to your team with:
   - All call summaries from that day
   - Action items with owners and due dates
   - Link to Notion database

---

## Common Issues

### "ModuleNotFoundError: No module named 'anthropic'"
Install dependencies:
```bash
pip install -r requirements.txt
```

### "Invalid API Key"
Check your `.env` file:
```bash
cat .env | grep ANTHROPIC_API_KEY
```

Must start with `sk-ant-`

### "No calls found"
This is normal if:
- Fathom hasn't recorded any new calls in last 24 hours
- Calls were already processed (check `processed_calls.json`)

To reset and reprocess:
```bash
rm processed_calls.json
python scheduler.py --once
```

### No Notion pages created
Run the setup helper:
```bash
python setup_notion.py
```

This verifies your Notion database is accessible.

---

## Check Status

### View logs
```bash
tail -f workflow.log
```

### Check if scheduler is running (Mac/Linux)
```bash
ps aux | grep scheduler.py
```

### Stop the scheduler (background process)
```bash
pkill -f scheduler.py
```

---

## Files

| File | Purpose |
|------|---------|
| `fathom_notion_workflow.py` | Main workflow logic |
| `scheduler.py` | Scheduling and orchestration |
| `setup_notion.py` | Notion database verification |
| `.env` | Your API keys (keep private!) |
| `processed_calls.json` | Tracks processed calls (auto-generated) |
| `workflow.log` | Logs (auto-generated) |
| `README.md` | Full documentation |

---

## Next Steps

- **Customize the workflow**: Edit `fathom_notion_workflow.py` to change email templates, action item extraction, etc.
- **Monitor logs**: Keep `workflow.log` open to see what's happening
- **Test with real calls**: Record a Fathom call and watch it automatically appear in Notion within minutes

---

Need help? Check the full README.md for advanced configuration and troubleshooting.
