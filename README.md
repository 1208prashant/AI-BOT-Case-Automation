# AI-BOT-Case-Automation

AI-powered Slack bot that monitors support cases (Salesforce or mock data), analyzes severity and request type, routes cases to the right engineer, and sends automatic Slack DM notifications — no manual manager intervention required.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start Summary](#quick-start-summary)
- [Step 1 — Get the Project](#step-1--get-the-project)
- [Step 2 — Install Python Dependencies](#step-2--install-python-dependencies)
- [Step 3 — Create a Slack App (Full Walkthrough)](#step-3--create-a-slack-app-full-walkthrough)
- [Step 4 — Configure Environment Variables](#step-4--configure-environment-variables)
- [Step 5 — Configure Engineers](#step-5--configure-engineers)
- [Step 6 — Run the Bot](#step-6--run-the-bot)
- [Step 7 — Verify It Works](#step-7--verify-it-works)
- [Step 8 — Push to GitHub](#step-8--push-to-github)
- [How It Works](#how-it-works)
- [Slack Commands](#slack-commands)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Production Roadmap](#production-roadmap)

---

## Overview

### Problem

Support managers manually watch Salesforce for high-priority cases (Sev1/Sev2, escalations, remote sessions) and DM engineers on Slack. This is slow, manual, and hard to scale.

### Solution

**AI-BOT-Case-Automation** acts as a digital assistant:

```
Customer → Case Created → Bot Monitors → AI Analyzes → Engineer Routed → Slack DM Sent
```

### What triggers a notification?

| Category | Examples |
|----------|----------|
| **Severity** | Sev1, Sev2, Sev3 (optional) |
| **Customer requests** | Remote sessions, troubleshooting, product expertise |
| **Escalations** | Customer escalations, key customer requests |
| **Service requests** | Cases needing engineer involvement |

Low-priority cases (e.g. billing questions) are automatically skipped.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.9+** | Check with `python3 --version` |
| **Slack workspace** | Free plan works for testing |
| **Git** | Optional, for GitHub upload |
| **Salesforce** | **Not required** — mock mode included |
| **OpenAI API key** | **Not required** — rule-based analysis included |

---

## Quick Start Summary

```bash
# 1. Clone or extract project
cd slackbotagent

# 2. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with Slack tokens (see Step 4)

# 4. Set your Slack user ID in config/engineers.json

# 5. Run
python main.py
```

Within ~15 seconds you should receive an automatic DM — no slash commands needed.

---

## Step 1 — Get the Project

### Option A — Clone from GitHub (after you upload)

```bash
git clone https://github.com/YOUR_USERNAME/AI-BOT-Case-Automation.git
cd AI-BOT-Case-Automation
```

### Option B — Extract the archive

```bash
unzip AI-BOT-Case-Automation.zip
cd slackbotagent
```

---

## Step 2 — Install Python Dependencies

```bash
cd slackbotagent
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

Verify installation:

```bash
python scripts/demo_pipeline.py
```

You should see JSON output routing sample cases to engineers (no Slack needed).

---

## Step 3 — Create a Slack App (Full Walkthrough)

This section walks through **every click** needed to configure Slack from scratch.

### 3.1 Create the app

1. Open [https://api.slack.com/apps](https://api.slack.com/apps) in your browser
2. Sign in with the account linked to your Slack workspace
3. Click **Create New App**
4. Choose **From scratch**
5. **App Name:** `AI-BOT-Case-Automation`
6. **Pick a workspace:** select your test workspace
7. Click **Create App**

---

### 3.2 Enable Socket Mode

Socket Mode lets the bot connect from your laptop without a public URL (ideal for local development and free Slack workspaces).

1. Left sidebar → **Settings** → **Socket Mode**
2. Toggle **Enable Socket Mode** → **ON**
3. Slack prompts you to create an **App-Level Token**:
   - **Token Name:** `socket-token`
   - **Scope:** `connections:write`
4. Click **Generate**
5. **Copy the token** (starts with `xapp-`) — you will paste this into `.env` as `SLACK_APP_TOKEN`

> Save this token now. Slack only shows it once.

---

### 3.3 Add Bot Token Scopes

1. Left sidebar → **Features** → **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Click **Add an OAuth Scope** and add each of these:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Send messages and DMs |
| `im:write` | Open DM channels with users |
| `users:read` | Look up workspace members |
| `commands` | Handle slash commands |
| `app_mentions:read` | Respond when @mentioned |

---

### 3.4 Install the app to your workspace

1. Scroll to the top of **OAuth & Permissions**
2. Click **Install to Workspace** (or **Reinstall to Workspace**)
3. Review permissions → click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`) — paste into `.env` as `SLACK_BOT_TOKEN`

---

### 3.5 Copy the Signing Secret

1. Left sidebar → **Settings** → **Basic Information**
2. Under **App Credentials**, find **Signing Secret**
3. Click **Show** → copy the value — paste into `.env` as `SLACK_SIGNING_SECRET`

---

### 3.6 Enable the Messages Tab (required for DMs)

Without this, Slack shows *"Sending messages to this app has been turned off"*.

1. Left sidebar → **Features** → **App Home**
2. Under **Show Tabs**:
   - Turn **Messages Tab** → **ON**
   - Check **Allow users to send Slash commands and messages from the messages tab**
3. Save changes

---

### 3.7 Create Slash Commands

1. Left sidebar → **Features** → **Slash Commands**
2. Click **Create New Command** for each:

| Command | Request URL | Short Description | Usage Hint |
|---------|-------------|-------------------|------------|
| `/aibot-status` | `https://example.com` | Pipeline stats | (leave empty) |
| `/aibot-engineers` | `https://example.com` | View engineer roster | (leave empty) |
| `/aibot-simulate` | `https://example.com` | Simulate a test case | `Sev1 \| Outage \| Platform A \| AMER` |

> The Request URL is a placeholder. Socket Mode handles commands — no public server needed.

---

### 3.8 Enable Event Subscriptions (optional)

Allows the bot to respond when @mentioned.

1. Left sidebar → **Features** → **Event Subscriptions**
2. Toggle **Enable Events** → **ON**
3. Under **Subscribe to bot events**, click **Add Bot User Event**
4. Add: `app_mention`
5. Click **Save Changes**

---

### 3.9 Reinstall after changes

If Slack prompts you to reinstall after adding scopes or events:

1. **Settings** → **Install App** → **Reinstall to Workspace**
2. Click **Allow**

---

### 3.10 Token summary

After completing the above, you should have **three values**:

| Variable | Where to find it | Starts with |
|----------|------------------|-------------|
| `SLACK_BOT_TOKEN` | OAuth & Permissions → Bot User OAuth Token | `xoxb-` |
| `SLACK_APP_TOKEN` | Socket Mode → App-Level Token | `xapp-` |
| `SLACK_SIGNING_SECRET` | Basic Information → Signing Secret | (random string) |

---

## Step 4 — Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required — paste your three Slack tokens
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here

# Mock mode — no Salesforce needed for testing
MOCK_SALESFORCE=true
POLL_INTERVAL_SECONDS=15
MOCK_CASE_INTERVAL_SECONDS=45

# Optional — leave blank for rule-based analysis
OPENAI_API_KEY=

# Optional — only needed for live Salesforce (not mock mode)
SALESFORCE_INSTANCE_URL=
SALESFORCE_CLIENT_ID=
SALESFORCE_CLIENT_SECRET=
SALESFORCE_USERNAME=
SALESFORCE_PASSWORD=
SALESFORCE_SECURITY_TOKEN=
```

> **Never commit `.env` to GitHub.** It is already listed in `.gitignore`.

---

## Step 5 — Configure Engineers

Edit `config/engineers.json` and replace placeholder Slack user IDs with real ones from your workspace.

### Find your Slack User ID

**Desktop Slack:**
1. Click your profile picture → **Profile**
2. Click **⋮** (three dots) → **Copy member ID**
3. You get a value like `U07ABC123XY`

**Or use the helper script:**

```bash
source .venv/bin/activate
python scripts/list_slack_users.py
```

### Update engineers.json

For solo testing, set **your** user ID on every engineer:

```json
{
  "engineers": [
    {
      "id": "eng-001",
      "name": "Alex Chen",
      "slack_user_id": "U07ABC123XY",
      "email": "you@company.com",
      "skills": ["networking", "kubernetes", "sev1", "sev2"],
      "products": ["Platform A", "Platform B"],
      "regions": ["AMER", "APAC"],
      "on_call": true,
      "max_active_cases": 5
    }
  ]
}
```

Repeat for all engineers, or keep one engineer with your ID for solo demos.

---

## Step 6 — Run the Bot

```bash
source .venv/bin/activate
python main.py
```

**Expected terminal output:**

```
Running in MOCK Salesforce mode — cases auto-generate every 45s and trigger DMs
Starting Salesforce poll loop (interval=15s)
Mock Salesforce emitted startup case CS-1001 (auto-DM)
Processing case CS-1001: PRODUCTION OUTAGE...
Sent DM to Alex Chen for case CS-1001
AI-BOT-Case-Automation is running — mock cases will auto-DM engineers (no slash commands needed)
⚡ Bolt app is running!
```

Leave this terminal open. The bot runs until you press `Ctrl+C`.

---

## Step 7 — Verify It Works

### Automatic DMs (primary test)

1. Keep `python main.py` running
2. Open Slack → **Apps** → **AI-BOT-Case-Automation**
3. Wait **~15 seconds** — you should receive a DM automatically
4. Another DM arrives every **~45 seconds** (for actionable cases)

No slash commands required.

### Manual tests (optional)

```
/aibot-status
/aibot-engineers
/aibot-simulate Sev1 | Production outage | Platform A | AMER
```

### Test script

```bash
python scripts/send_test_notification.py --user-id U07ABC123XY
```

### Verification checklist

| Test | Expected result |
|------|-----------------|
| Bot appears under **Apps** in Slack | ✓ |
| Auto DM within 15 seconds | ✓ |
| DM shows severity, case details, Acknowledge button | ✓ |
| `/aibot-status` responds | ✓ |
| Low-priority cases skipped (no DM) | ✓ |

---

## Step 8 — Push to GitHub

### 8.1 Create a new repository on GitHub

1. Go to [https://github.com/new](https://github.com/new)
2. **Repository name:** `AI-BOT-Case-Automation`
3. **Description:** `AI-powered Slack bot for automated support case routing and notifications`
4. Choose **Public** or **Private**
5. **Do NOT** check "Add a README" (you already have one)
6. Click **Create repository**

### 8.2 Initialize Git and push (first time)

Run these commands from the project folder:

```bash
cd ~/slackbotagent

# Initialize git
git init

# Add all files (.env and .venv are excluded by .gitignore)
git add .

# First commit
git commit -m "Initial commit: AI-BOT-Case-Automation Slack bot prototype"

# Rename default branch to main
git branch -M main

# Add your GitHub repo (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/AI-BOT-Case-Automation.git

# Push
git push -u origin main
```

GitHub may prompt you to sign in via browser — use the account you're already logged into.

### 8.3 Push updates later

```bash
git add .
git commit -m "Describe your changes"
git push
```

### 8.4 Using GitHub CLI (alternative)

If you have `gh` installed:

```bash
cd ~/slackbotagent
git init
git add .
git commit -m "Initial commit: AI-BOT-Case-Automation Slack bot prototype"
gh repo create AI-BOT-Case-Automation --public --source=. --push
```

### 8.5 What gets uploaded (and what doesn't)

| Uploaded to GitHub | Excluded (in .gitignore) |
|------------------|--------------------------|
| Source code (`src/`, `main.py`) | `.env` (secrets) |
| `config/engineers.json` | `.venv/` |
| `.env.example` | `__pycache__/` |
| `README.md` | `*.log` |
| `requirements.txt` | |

> Review `config/engineers.json` before pushing if it contains real email addresses or Slack IDs you want to keep private.

---

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌────────────┐
│  Salesforce │     │  AI Analyzer │     │ Engineer      │     │  Slack DM  │
│  (or Mock)  │────▶│  (GPT/Rules) │────▶│ Router        │────▶│  + @mention│
└─────────────┘     └──────────────┘     └───────────────┘     └────────────┘
```

1. **Monitor** — Polls Salesforce (or generates mock cases on a timer)
2. **Analyze** — Classifies severity, request type, required skills
3. **Route** — Scores engineers by skills, region, product, on-call status, load
4. **Notify** — Sends rich DM with case details and action buttons

---

## Slack Commands

| Command | Description |
|---------|-------------|
| `/aibot-status` | Pipeline stats (processed, notified, skipped) |
| `/aibot-engineers` | View configured engineer roster and load |
| `/aibot-simulate` | Manually inject a test case through the pipeline |

**Example:**

```
/aibot-simulate Sev1 | Production outage | Platform A | AMER
```

---

## Configuration Reference

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_BOT_TOKEN` | — | Bot OAuth token (`xoxb-`) |
| `SLACK_APP_TOKEN` | — | App-level token for Socket Mode (`xapp-`) |
| `SLACK_SIGNING_SECRET` | — | App signing secret |
| `MOCK_SALESFORCE` | `true` | Use mock cases instead of real Salesforce |
| `POLL_INTERVAL_SECONDS` | `15` | How often to check for new cases |
| `MOCK_CASE_INTERVAL_SECONDS` | `45` | How often mock cases are generated |
| `NOTIFY_SEV3` | `false` | Also notify for Sev3 cases |
| `OPENAI_API_KEY` | — | Enable GPT-based analysis (optional) |
| `WEBHOOK_PORT` | `3000` | Port for Salesforce webhook endpoint |

### Routing rules

Edit `config/routing_rules.json` to customize keywords and triggers.

### Bot display name

Edit `src/config.py`:

```python
BOT_DISPLAY_NAME = "AI-BOT-Case-Automation"
BOT_SLASH_PREFIX = "aibot"
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Sending messages to this app has been turned off` | **App Home** → enable **Messages Tab** (Step 3.6) |
| `user_not_found` | Update `slack_user_id` in `config/engineers.json` with real `U...` IDs |
| `invalid_auth` | Reinstall Slack app, copy fresh `SLACK_BOT_TOKEN` |
| Slash command not found | Create `/aibot-*` commands in Slack app settings, reinstall app |
| No auto DMs | Confirm `MOCK_SALESFORCE=true`, real engineer IDs, bot is running |
| Bot crashes on DM | Check terminal logs; run `python scripts/list_slack_users.py` |
| No notification sound | Slack → Preferences → Notifications → enable sounds and DMs |
| Command works, no DM | Engineer `slack_user_id` doesn't match your Slack user ID |

### Enable notification sounds

1. Slack → **Preferences** → **Notifications**
2. Enable **Play a sound when I receive a notification**
3. Set **Notify me about** → **Direct messages, mentions & keywords**

DMs include an `@mention` to trigger alert notifications.

---

## Project Structure

```
slackbotagent/
├── main.py                          # Entry point
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template (copy to .env)
├── config/
│   ├── engineers.json               # Engineer roster & Slack user IDs
│   └── routing_rules.json           # Triage keywords & rules
├── src/
│   ├── config.py                    # Settings & bot display name
│   ├── models.py                    # Data models
│   ├── ai/analyzer.py               # AI + rule-based case analysis
│   ├── salesforce/client.py         # Salesforce REST + mock generator
│   ├── routing/router.py            # Engineer scoring & assignment
│   ├── slack/
│   │   ├── bot.py                   # Slack Bolt app & commands
│   │   └── notifications.py         # Rich DM message blocks
│   └── services/case_processor.py   # End-to-end pipeline
└── scripts/
    ├── demo_pipeline.py             # Local demo (no Slack)
    ├── list_slack_users.py          # List workspace user IDs
    └── send_test_notification.py    # Send a test DM
```

---

## Salesforce Integration (Optional)

### Mock mode (default — no Salesforce needed)

```env
MOCK_SALESFORCE=true
```

Generates realistic test cases automatically.

### Live Salesforce mode

```env
MOCK_SALESFORCE=false
SALESFORCE_INSTANCE_URL=https://yourorg.my.salesforce.com
SALESFORCE_CLIENT_ID=...
SALESFORCE_CLIENT_SECRET=...
SALESFORCE_USERNAME=...
SALESFORCE_PASSWORD=...
SALESFORCE_SECURITY_TOKEN=...
```

### Webhook endpoint

```bash
POST http://localhost:3000/webhook/salesforce
Content-Type: application/json

{
  "case_id": "500XXXXXXXXXXXX",
  "case_number": "CS-12345",
  "subject": "Sev1 — Production outage",
  "description": "Service down in AMER",
  "priority": "Critical",
  "product": "Platform A",
  "region": "AMER",
  "is_key_customer": true
}
```

---

## Production Roadmap

- [ ] Salesforce Platform Events instead of polling
- [ ] On-call schedule integration (PagerDuty / Opsgenie)
- [ ] Manager escalation channel for unroutable cases
- [ ] Case acknowledgment sync back to Salesforce
- [ ] Audit log and metrics dashboard
- [ ] Duplicate case detection

---

## License

MIT — use freely for learning and internal prototyping.
