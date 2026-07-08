# License: LGPL-3
{
    "name": "Twilio Softphone for Odoo | Auto Dialer, API & Call Logs",
    "version": "1.0.1",
    "category": "Productivity/Communication",
    "summary": "Odoo Twilio API: Auto Dialer, click-to-call, SMS, contact sync & call logs. Pairs with Chrome softphone. Odoo 14–19.",
    "description": """
Twilio Softphone for Odoo — Auto Dialer & Odoo API Integration
================================================================

Turn Odoo into a Twilio-powered calling hub. This module exposes the Odoo API endpoints
your Chrome softphone needs to sync CRM contacts, log calls, and run outbound Auto Dialer
campaigns — all through your own Twilio account.

Stop copying numbers between Odoo and your phone. Call and text contacts from Chrome,
click any number on Odoo pages, and push every call back to CRM automatically.

Key Features
------------
* **Auto Dialer** — Upload or paste call lists and auto-dial with Start, Stop, Skip, and End
  controls. Built for outbound sales and follow-up workflows (Premium in Chrome extension).
* **Odoo API / Twilio API Hub** — REST endpoints for Get Contacts, Post Call Log, Get All Call
  Logs, and Contact Call Logs. Test each API before save with guided setup help.
* **Click to Call** — Detect phone numbers on Odoo pages; one click dials via Twilio softphone.
* **Odoo Contacts Sync** — Pull contacts from your Odoo API endpoint; search by name or phone.
* **SMS** — Send SMS from the same panel without switching apps.
* **Call History** — Twilio call logs and Odoo call logs in one place; redial, filter by date or number.
* **Twilio Configuration** — Store Account SID, Auth Token, and default From number per company.

Works With
----------
* Odoo 14, 15, 16, 17, 18, and 19 — Online, Odoo.sh, Enterprise, and Community
* Chrome extension (Twilio Softphone for Odoo) for browser-based calling
* Your own Twilio account — pay-as-you-go voice and SMS; no per-seat extension fee

Setup in Four Steps
-------------------
1. Install this Odoo module and configure Twilio credentials.
2. Install the Chrome extension and connect your Twilio account.
3. Configure Odoo API Hub endpoints (contacts and call logs).
4. Start calling — click any number in Odoo or use the Auto Dialer.

Security & Privacy
------------------
Credentials are stored in Odoo (module) and locally in the browser (extension). Data is sent
only to Twilio and your own Odoo endpoints — no intermediary servers.

Install from addons path (copy twilio_dialer folder to addons); do not use Apps → Import (zip).
    """,
    "author": "Twilio Dialer",
    "license": "LGPL-3",
    "website": "https://www.twilio.com",
    "depends": ["base","web"],
    "external_dependencies": {},
    # Cover/thumbnail for Odoo Apps Store (first image = list thumbnail)
    "images": ["static/description/images/cover.png"],
    "post_init_hook": "post_init_hook",
    "data": [
        "security/ir.model.access.csv",
        "views/twilio_config_views.xml",
        "views/twilio_sms_views.xml",
        "views/twilio_call_log_views.xml",
        "views/twilio_dialer_views.xml",
        "data/menu.xml",
    ],
"assets": {
    "web.assets_backend": [

        # CSS
        "twilio_dialer/static/src/css/dialer_floating_button.css",

        # JS
        "twilio_dialer/static/src/js/dialer.js",
        "twilio_dialer/static/src/js/dialer_floating_button.js",
    ],

    "web.assets_qweb": [
        "twilio_dialer/static/src/xml/dialer_floating_button.xml",
    ],
},
    "installable": True,
    "application": True,
}
