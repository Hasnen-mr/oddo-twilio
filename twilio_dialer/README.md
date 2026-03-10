# Twilio Connector for Odoo

Odoo module that provides Twilio integration: configuration (Account SID, Auth Token), send SMS, view SMS history and call logs from Twilio, and click-to-call from Odoo. Uses the same concepts as the Twilio browser extension (calling, SMS, call logs) in an Odoo addon suitable for the Odoo Apps Store.

## Installation

1. Copy the `odoo_twilio` folder into your Odoo addons path.
2. Update the app list (Apps → Update Apps List if needed).
3. Install the "Twilio Connector – Calling, SMS and Call Logs" app.
4. Open **Twilio → Configuration** and set your Twilio Account SID and Auth Token (from your Twilio console).
5. Use **Twilio → Send SMS**, **SMS History**, **Call Logs**, and **Click to Call** as needed.

## How to use (after install)

All features are under the **Twilio** menu in the Odoo app switcher (top-left) or main menu.

### 1. Configuration (required first time)

- Go to **Twilio → Configuration**.
- Click **Create** and fill in:
  - **Company** (default: current company).
  - **Account SID** – from [Twilio Console](https://console.twilio.com) (starts with `AC`).
  - **Auth Token** – from the same console (keep it secret).
  - **Default From Number** – your Twilio phone number (e.g. `+1234567890`) for SMS and calls.
- Click **Test connection** to verify credentials.
- Save.

### 2. Send SMS

- **Twilio → Send SMS**.
- Choose **To** number, enter **Message**, optionally pick a **From** number (or use the default).
- Click **Send SMS**. The message is sent via Twilio.

### 3. SMS History

- **Twilio → SMS History**.
- Optionally set date range and click **Fetch SMS** to load messages from Twilio into Odoo.
- View the list of sent/received SMS.

### 4. Call Logs

- **Twilio → Call Logs**.
- Optionally set date range and click **Fetch Calls** to load call records from Twilio.
- View direction, status, duration and recording links (if any).

### 5. Click to Call

- **Twilio → Click to Call**.
- Enter **Your phone number** (the number Twilio will call first).
- Enter or select **Contact / number to call** (the number to dial after you answer).
- Click **Start call**. Twilio calls your phone; when you answer, it dials the contact.

**Note:** Click to Call requires your Odoo server to be reachable from the internet (public URL) so Twilio can request the dial TwiML. Set **System Parameters → `web.base.url`** correctly.

## Requirements

- Odoo 18.0 (or 17.0; adjust `__manifest__.py` if needed).
- A Twilio account (twilio.com). No activation key; you use your own credentials.

## Click-to-call

Your Odoo instance must be reachable by Twilio on the internet (public URL). The module provides a public TwiML endpoint at `/twilio/dial?to=<number>`. When you use Click to Call, Twilio first calls your phone; when you answer, Twilio fetches that URL and dials the contact. Ensure `web.base.url` is set correctly in Odoo.

## Odoo Apps Store – repository structure and URL

**Required structure:** Each module must be in its **own folder at the root** of the repository. The store expects:

```
your-repo-root/
  odoo_twilio/          <-- one folder per module, name = module technical name
    __manifest__.py
    __init__.py
    models/
    views/
    ...
```

If you pushed the **contents** of `odoo_twilio` as the repo root (so `__manifest__.py` is at the top level), the store will report "No module found". Fix it by creating a folder named `odoo_twilio` and moving all module files into it. You can run from the repo root:

```bash
bash fix_repo_structure.sh
```

(Or create `odoo_twilio/` manually and move `__manifest__.py`, `__init__.py`, `models/`, `views/`, `data/`, `security/`, `controllers/`, `wizard/`, `static/`, `README.md` into it.)

**Repository URL** must follow the standard format:

```
ssh://git@github.com/<owner>/<repo>.git#<branch>
```

Examples: `ssh://git@github.com/Hasnen-mr/oddo-twilio.git#18.0`. Use the branch that matches your Odoo version (e.g. `#18.0`, `#17.0`).

## License

LGPL-3.
# oddo-twilio
