# Discord Mind Matrix Bot

A Discord bot for managing student verification with email OTP for Mind Matrix platforms. Designed to handle **5000+ students** across **multiple internship batches** with automatic role and channel creation.

## ✨ Features

- ✅ **Email OTP Verification** - Secure verification with 6-digit codes
- 🏫 **University-Based Organization** - Separate VTU and GTU students on same server
- 🤖 **Auto Role & Channel Creation** - Bot creates roles/channels dynamically with university prefixes
- 🏢 **Multi-University Support** - Each university gets its own categories, roles, and channels
- 📢 **Shared + Private Channels** - Announcements for all students, private channels per batch
- 🛡️ **Duplicate Prevention** - Email and Discord ID uniqueness enforced
- 📊 **Admin Dashboard** - Stats, force-verify, lookup, broadcast
- 💾 **Local SQLite** - No external database needed

---

## 📁 Project Structure

```
discord-edtech-bot/
├── .env                    # Secrets (NEVER commit!)
├── .gitignore
├── requirements.txt
├── config.py               # Channel IDs, Verified Role, Settings
├── main.py                 # Bot entry point
├── database.py             # SQLite operations
├── import_csv.py           # CSV → Database import tool
├── data/
│   ├── students.csv        # Your student data (name, email, course)
│   └── student_data.db     # SQLite database (auto-created)
├── src/
│   ├── __init__.py
│   └── cogs/
│       ├── __init__.py
│       ├── verification.py # /verify, /otp + Auto Role/Channel creation
│       ├── admin.py        # Admin commands
│       └── help.py         # Help menu
└── logs/                   # Bot logs
```

---

## 🚀 How It Works

### University-Based Auto-Creation System

When a **VTU** student with course `"Android App Development"` and batch `"Nomads"` verifies, the bot **automatically creates**:

| Resource | Name | Who Can See |
|----------|------|-------------|
| **Course Role** | `VTU-Android App Development Intern` | - |
| **Batch Role** | `VTU-Nomads` | - |
| **Category** | `VTU - Android App Development` | VTU Android students |
| **Channel** | `#vtu-android-app-development-announcements` | All VTU Android students (read-only) |
| **Channel** | `#vtu-android-app-development-discussion` | All VTU Android students (can chat) |
| **Channel** | `#vtu-nomads-official` | Only VTU Nomads batch |

**GTU** students get completely separate resources:
- `GTU-Android App Development Intern` role
- `GTU - Android App Development` category
- `#gtu-android-app-development-announcements` channel
- etc.

**Key Benefits:**
- VTU and GTU students are organized separately
- No naming conflicts between universities
- Easy to manage multiple colleges on one server

### Verification Flow

```
Student joins server
        ↓
Uses /verify email:student@example.com
        ↓
Bot checks SQLite database → Email found?
        ↓ (finds: University=VTU, Course=Android App Development, Batch=Nomads)
    YES → Bot sends OTP to email
        ↓
Student uses /otp code:123456
        ↓
Bot validates OTP → Creates university-specific roles/channels if needed
        ↓
Bot assigns: @Verified + @VTU-Android App Development Intern + @VTU-Nomads
        ↓
Student sees VTU Android App Development channels! 🎉
```

---

## 🛠️ Setup Guide

### Part A: Discord Setup

#### Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** → Name it (e.g., "Mind Matrix Bot")
3. Go to **"Bot"** section → Click **"Add Bot"**
4. Click **"Reset Token"** → Copy and save securely
5. **Enable Privileged Gateway Intents**:
   - ✅ `SERVER MEMBERS INTENT`
   - ✅ `MESSAGE CONTENT INTENT`

#### Step 2: Generate Bot Invite Link

1. Go to **"OAuth2"** → **"URL Generator"**
2. Select **Scopes**: `bot`, `applications.commands`
3. Select **Bot Permissions**:
   - ✅ Manage Roles
   - ✅ Manage Channels
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Read Message History
   - ✅ Use Slash Commands
4. Copy URL → Open in browser → Add to your server

#### Step 3: Create Basic Roles

In your Discord server (**Server Settings → Roles**):

1. Create a `Verified` role (general access)
2. **CRITICAL**: Drag the **Bot's Role** to the **TOP** of the role list
   - The bot can only manage roles **below** its own role

#### Step 4: Create Verification Channel

1. Create `#verify` channel (visible to @everyone)
2. Create `#admin-logs` channel (visible only to admins)

---

### Part B: Local Setup

#### Step 1: Install Python

```powershell
# Download Python 3.10+ from python.org
# Verify installation
python --version
```

#### Step 2: Set Up Project

```powershell
# Navigate to project folder
cd "d:\OneDrive - IIT Kanpur\Desktop\discord-edtech-bot"

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 3: Configure `.env`

```env
# Discord Bot Token
DISCORD_TOKEN=your_bot_token_here

# Gmail SMTP (for OTP emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

**Gmail App Password**:
1. Enable 2FA on Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Generate password for "Mail"

#### Step 4: Configure `config.py`

Only **3 IDs** needed (batch roles are auto-created):

```python
# Get by right-clicking in Discord (Developer Mode ON)
VERIFIED_ROLE_ID = 1452628492263882825   # @Verified role
VERIFY_CHANNEL_ID = 1452628764000260116  # #verify channel
LOG_CHANNEL_ID = 1452629016568791050     # #admin-logs channel
```

#### Step 5: Prepare Student CSV

Create `data/students.csv` with **5 columns**:

```csv
Name,Email id,University,Course,Batch name
Rahul Sharma,rahul@example.com,VTU,Android App Development,Nomads
Priya Singh,priya@example.com,GTU,Data Analytics,Pioneers
Amit Kumar,amit@example.com,VTU,Android App Development,Navigants
Neha Gupta,neha@example.com,GTU,Web Development,Explorers
```

**CSV Format Explained:**
| Column | Description | Example |
|--------|-------------|----------|
| Name | Student's full name | "Rahul Sharma" |
| Email id | Student's email | "rahul@example.com" |
| University | University code (VTU/GTU) | "VTU" |
| Course | Course/Category name | "Android App Development" |
| Batch name | Batch/Group name | "Nomads" |

**Supported Universities:**
- `VTU` - Visvesvaraya Technological University
- `GTU` - Gujarat Technological University
- Add more in `config.py` → `SUPPORTED_UNIVERSITIES`

#### Step 6: Import Students to Database

```powershell
python import_csv.py
# Choose option 1 to import
```

#### Step 7: Run the Bot

```powershell
.\venv\Scripts\activate
python main.py
```

Expected output:
```
==================================================
✅ Bot is ready!
📌 Logged in as: MindMatrixBot
🆔 Bot ID: 123456789
🌐 Servers: 1
==================================================
```

---

## 📋 Commands Reference

### User Commands

| Command | Description |
|---------|-------------|
| `/verify email:your@email.com` | Start verification (sends OTP) |
| `/otp code:123456` | Complete verification with OTP |
| `/reverify` | Request new OTP |
| `/help` | Show help menu |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/stats` | View verification statistics |
| `/force-verify user:@User email:...` | Manually verify user (auto-fetches university/course/batch from DB) |
| `/unverify user:@User` | Remove verification and all university-specific roles |
| `/lookup user:@User` | Look up by Discord user |
| `/lookup email:email@example.com` | Look up by email |
| `/add-student email:... name:... university:... course:... batch:...` | Add single student with university |
| `/broadcast message:... course:...` | Send announcement |

---

## 📊 What Gets Created Per University & Course

### Example: VTU - Android App Development

For **VTU** students in **Android App Development** with batches (Nomads, Pioneers, etc.):

```
📁 VTU - Android App Development (Category)
├── 📢 #vtu-android-app-development-announcements  ← All VTU Android students (read-only)
├── 💬 #vtu-android-app-development-discussion     ← All VTU Android students (can chat)
├── 🔒 #vtu-nomads-official                        ← Only VTU Nomads batch
├── 🔒 #vtu-pioneers-official                      ← Only VTU Pioneers batch
└── 🔒 #vtu-navigants-official                     ← Only VTU Navigants batch
```

**Roles Created:**
- `VTU-Android App Development Intern` (all VTU Android students)
- `VTU-Nomads` (batch-specific)
- `VTU-Pioneers` (batch-specific)
- `VTU-Navigants` (batch-specific)

### Example: GTU - Android App Development

**GTU** students get completely separate resources:

```
📁 GTU - Android App Development (Category)
├── 📢 #gtu-android-app-development-announcements
├── 💬 #gtu-android-app-development-discussion
├── 🔒 #gtu-nomads-official
└── 🔒 #gtu-pioneers-official
```

**Roles Created:**
- `GTU-Android App Development Intern`
- `GTU-Nomads`
- `GTU-Pioneers`

**Key Point:** VTU and GTU resources are completely independent - no conflicts!

---

## 🔄 Adding New Students

```powershell
# 1. Edit data/students.csv with new students
# Format: Name,Email id,University,Course,Batch name
# Example: Raj Kumar,raj@example.com,VTU,Data Analytics,Batch-A

# 2. Run import (duplicates are skipped)
python import_csv.py
# Choose option 1 to import

# 3. Restart bot (optional, for new slash commands)
python main.py
```

**Adding a New University:**
1. Open `config.py`
2. Add to `SUPPORTED_UNIVERSITIES` list:
   ```python
   SUPPORTED_UNIVERSITIES = ["VTU", "GTU", "JNTU"]  # Add JNTU
   ```
3. Update CSV with new university code
4. Import and verify - bot auto-creates resources!

---

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot can't create roles | Move Bot's role to TOP in Server Settings → Roles |
| "Email not found" | Run `python import_csv.py` to import CSV |
| OTP not received | Check spam folder, verify SMTP credentials |
| Roles exist but not assigned | Bot role must be ABOVE the target roles |
| Slash commands not showing | Wait 1 hour or kick & re-invite bot |

---

## 🔒 Security Notes

- **Never commit `.env`** - Contains bot token & email password
- **Bot token leaked?** → Regenerate in Discord Developer Portal
- **OTPs expire** in 5 minutes
- **All responses are ephemeral** (private to user)

---

## 📄 License

MIT License - Free to use and modify!



# MindMatrix Discord Bot – VM Deployment & Operations Guide

This README documents the **exact VM structure, commands, and operational workflow** used to deploy and run the MindMatrix Discord Bot on a **Google Cloud VM using systemd**.

---

## 1. VM Details

* **Project ID:** `mindmatrix-455721`
* **VM Name:** `mindmatrix-discord-bot`
* **Zone:** `asia-south1-c`
* **OS Login User:** `platform_clinf_com`
* **Home Directory:**

```bash
/home/platform_clinf_com
```

---

## 2. Directory Structure on VM

```text
/home/platform_clinf_com/
├── discord-edtech-bot-Updated/
│   ├── discord-edtech-bot-Updated/
│   │   ├── main.py
│   │   ├── config.py              # gitignored (manual on VM)
│   │   ├── database.py
│   │   ├── import_csv.py
│   │   ├── requirements.txt
│   │   ├── .env                    # gitignored (manual on VM)
│   │   ├── venv/
│   │   ├── data/
│   │   │   └── *.db
│   │   ├── logs/
│   │   └── src/
│   │       └── cogs/
│   └── .git/
```

---

## 3. Python Environment Setup

```bash
cd ~/discord-edtech-bot-Updated/discord-edtech-bot-Updated
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Configuration Files (Important)

### 4.1 `config.py`

* **NOT committed to Git**
* Exists manually on VM
* Used like:

```python
import config
config.BOT_PREFIX
```

### 4.2 `.env`

* Loaded using `python-dotenv`
* Example variables:

```env
BOT_TOKEN=xxxxx
SMTP_EMAIL=xxxxx
SMTP_PASSWORD=xxxxx
```

---

## 5. systemd Service Configuration

### Service File Location

```bash
/etc/systemd/system/mindmatrix-discord-bot.service
```

### Service File Contents

```ini
[Unit]
Description=MindMatrix Discord Bot
After=network.target

[Service]
User=platform_clinf_com
WorkingDirectory=/home/platform_clinf_com/discord-edtech-bot-Updated/discord-edtech-bot-Updated
EnvironmentFile=/home/platform_clinf_com/discord-edtech-bot-Updated/discord-edtech-bot-Updated/.env
ExecStart=/home/platform_clinf_com/discord-edtech-bot-Updated/discord-edtech-bot-Updated/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 6. systemd Commands (Daily Use)

### Start Bot

```bash
sudo systemctl start mindmatrix-discord-bot
```

### Stop Bot

```bash
sudo systemctl stop mindmatrix-discord-bot
```

### Restart Bot (Most Used)

```bash
sudo systemctl restart mindmatrix-discord-bot
```

### Check Status

```bash
sudo systemctl status mindmatrix-discord-bot
```

### View Logs (Live)

```bash
journalctl -u mindmatrix-discord-bot -f
```

---

## 7. Git Deployment Workflow (IMPORTANT)

### On Local Machine

```bash
git add .
git commit -m "message"
git push origin main
```

### On VM (Deployment)

```bash
cd ~/discord-edtech-bot-Updated/discord-edtech-bot-Updated
git fetch origin
git reset --hard origin/main
sudo systemctl restart mindmatrix-discord-bot
```

⚠️ **Never use `git pull` with merge or rebase on the VM**

---

## 8. Database Operations

### Stop Bot Before DB Changes

```bash
sudo systemctl stop mindmatrix-discord-bot
```

### Backup Database

```bash
cp data/database.db data/database_backup_$(date +%F_%H-%M-%S).db
```

### Run DB Init / Migration

```bash
source venv/bin/activate
python database.py
```

### Restart Bot

```bash
sudo systemctl start mindmatrix-discord-bot
```

---

## 9. Process Verification

### Ensure Single Bot Instance

```bash
ps aux | grep main.py
```

Expected: **Only one python process** (ignore grep line).

---

## 10. What NOT To Do (Critical Rules)

* ❌ Do NOT run `python main.py` manually on VM
* ❌ Do NOT commit `config.py` or `.env`
* ❌ Do NOT run multiple bots simultaneously
* ❌ Do NOT edit prod code without restarting systemd service

---

## 11. Health Check (Expected Logs)

On successful start, logs should show:

* Database initialized
* Cogs loaded
* Discord login successful
* Connected to guild(s)
* Slash commands synced

---

## 12. Status

✅ Production-ready
✅ Auto-restart enabled
✅ Survives VM reboot

---

*Last updated: Feb 2026*
