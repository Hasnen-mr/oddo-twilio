# License: LGPL-3
{
    "name": "Twilio Connector – Calling, SMS and Call Logs",
    "version": "1.0.0",
    "category": "Productivity/Communication",
    "summary": "Make calls, send SMS, and view Twilio call logs from Odoo using your own Twilio account.",
    "description": """
Twilio Connector for Odoo
=========================

Integrate Twilio with Odoo: store your Twilio credentials (Account SID and Auth Token),
send SMS, view SMS history and call logs from Twilio, and initiate click-to-call from Odoo.

* **Configuration**: One configuration per company (Account SID, Auth Token, default From number).
* **SMS**: Send SMS and fetch SMS history from Twilio on demand.
* **Call logs**: Fetch and display call logs from Twilio with optional recording links.
* **Click-to-call**: Initiate outbound calls via Twilio REST API (your phone rings, then the contact).

Uses only your Twilio credentials; no intermediary servers. Data is sent to Twilio as per their
privacy policy. Requires a Twilio account (twilio.com).
    """,
    "author": "Twilio Connector",
    "license": "LGPL-3",
    "website": "https://www.twilio.com",
    "depends": ["base"],
    "external_dependencies": {},
    "data": [
        "security/ir.model.access.csv",
        "data/menu.xml",
        "views/twilio_config_views.xml",
        "views/twilio_sms_views.xml",
        "views/twilio_call_log_views.xml",
        "views/twilio_dialer_views.xml",
    ],
    "installable": True,
    "application": False,
}
