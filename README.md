# Twilio Dialer for Odoo — Install & Setup Guide

Step-by-step guide to install and configure **Twilio Dialer** on your existing Odoo (Community or Enterprise).

Website: https://extension.mybroadcast.online  
Support: developer.lifetips@gmail.com

---

## Before you start

Make sure you have:

- Odoo already running (use your **existing database** and **existing login**)
- Matching module branch for your Odoo version (`14.0` … `19.0`)
- A Twilio account (Account SID + Auth Token)
- Optional: AI API key (for transcription / summary)

**Do not create a new database or new admin user** unless you intentionally want a fresh instance.

---

## Quick install (Windows / macOS)

Use the OS installer to auto-find Odoo, copy the module into custom addons, and install Python deps:

### macOS / Linux

```bash
cd installers
chmod +x install_mac.sh
./install_mac.sh
```

### Windows

Double-click `installers/install_windows.bat`  
or:

```powershell
cd installers
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
```

Details: [installers/README.md](installers/README.md)

Then continue from **Step 4** below (install the app in Odoo).

---

## Step 1 — Get the module

Clone or download the repository and checkout the branch for your Odoo version.

```bash
cd /path/to/your/addons
git clone https://github.com/Hasnen-mr/oddo-twilio.git twilio_dialer
cd twilio_dialer
git checkout 18.0
```

Replace `18.0` with `14.0`, `15.0`, `16.0`, `17.0`, or `19.0` if needed.

Folder layout should look like:

```text
twilio_dialer/                 ← repo root (add this folder to addons_path)
  twilio_dialer/               ← Odoo module
    __manifest__.py
  requirements.txt
  odoo.conf.example
  README.md
```

---

## Step 2 — Install Python dependency

Install the Twilio Python package in the **same Python environment** that runs Odoo:

```bash
cd twilio_dialer
pip install -r requirements.txt
```

This installs only:

- `twilio`

---

## Step 3 — Add the module to Odoo `addons_path`

### Option A — Local Odoo / Enterprise (recommended)

Use your **existing** Odoo config file (the one you already use to start Odoo).

Reference template in this repo: `odoo.conf.example`

Add the **repo root** to `addons_path` (keep your existing community + enterprise paths):

```ini
[options]
addons_path = /path/to/odoo/addons,/path/to/enterprise,/path/to/twilio_dialer
```

Example on macOS:

```ini
addons_path = /Users/you/odoo/addons,/Users/you/enterprise,/Users/hasnen/Documents/odoo_modules/twilio_dialer
```

Notes:

- Use your existing DB settings (`db_host`, `db_user`, `db_password`)
- Use your existing login — no new credentials are required
- **Do not** use `.local-dev/odoo.conf` for Enterprise — that file is only for Docker

Restart Odoo after saving the config.

### Option B — Docker / Colima (this machine only)

If you use the local Docker stack under `odoo_modules/.local-dev/`:

```bash
bash /Users/hasnen/Documents/odoo_modules/.local-dev/restart.sh
```

This upgrades the module on an **existing** database (default: `twilio_test`) and does **not** create a new DB or login.

To use another existing DB:

```bash
DB_NAME=your_existing_db bash /Users/hasnen/Documents/odoo_modules/.local-dev/restart.sh
```

Open: http://localhost:8069 — select your existing database and log in with your existing user.

---

## Step 4 — Install the app in Odoo

1. Log in to Odoo with your **existing** user
2. Go to **Apps**
3. Click **Update Apps List**
4. Remove the “Apps” filter if needed and search for **Twilio Dialer**
5. Click **Install**

Required Odoo apps (installed automatically via dependencies):

- Contacts  
- Discuss / Mail  
- Phone Validation  
- CRM  

---

## Step 5 — Configure Twilio

1. Open **Twilio Dialer → Configuration**
2. Enter:
   - **Account SID**
   - **Auth Token**
3. Save / generate configuration (API key + TwiML application), or paste your existing Twilio values
4. (Optional) Open **AI Settings** and add your AI API key if you want transcription / summary

---

## Step 6 — Verify it works

1. Hard-refresh the browser: **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows/Linux)
2. Open the dialer from the systray phone icon (or Dashboard)
3. Confirm status becomes connected
4. Try a test call from Contacts or CRM

---

## After code updates

When you pull new code:

```bash
cd /path/to/twilio_dialer
git pull
```

Then upgrade the module on your **existing** database:

- **Apps → Twilio Dialer → Upgrade**, or  
- Local Docker: `bash /Users/hasnen/Documents/odoo_modules/.local-dev/restart.sh`

Hard-refresh the browser again.

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| Module not visible in Apps | Check `addons_path` points to the **repo root**, then Update Apps List |
| `No module named 'twilio'` | Run `pip install -r requirements.txt` in Odoo’s Python env |
| Dialer UI looks old | Hard refresh; upgrade the module |
| Call connect fails | Recheck Account SID, Auth Token, API Key, TwiML App SID in Configuration |
| CRM call buttons missing | Make sure CRM is installed |
| Wrong database | Select your existing DB on the login screen — do not create a new one |

---

## Quick checklist

- [ ] Step 1 — Module downloaded / correct branch  
- [ ] Step 2 — `pip install -r requirements.txt`  
- [ ] Step 3 — `addons_path` updated + Odoo restarted  
- [ ] Step 4 — App installed on existing DB  
- [ ] Step 5 — Twilio credentials configured  
- [ ] Step 6 — Dialer connected and test call OK  
