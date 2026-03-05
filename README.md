# Twilio Connector for Odoo

Odoo module that provides Twilio integration: configuration (Account SID, Auth Token), send SMS, view SMS history and call logs from Twilio, and click-to-call from Odoo. Uses the same concepts as the Twilio browser extension (calling, SMS, call logs) in an Odoo addon suitable for the Odoo Apps Store.

## Installation

1. Copy the `odoo_twilio` folder into your Odoo addons path.
2. Update the app list (Apps → Update Apps List if needed).
3. Install the "Twilio Connector – Calling, SMS and Call Logs" app.
4. Open **Twilio → Configuration** and set your Twilio Account SID and Auth Token (from your Twilio console).
5. Use **Twilio → Send SMS**, **SMS History**, **Call Logs**, and **Click to Call** as needed.

## Requirements

- Odoo 18.0 (or 17.0; adjust `__manifest__.py` if needed).
- A Twilio account (twilio.com). No activation key; you use your own credentials.

## Click-to-call

Your Odoo instance must be reachable by Twilio on the internet (public URL). The module provides a public TwiML endpoint at `/twilio/dial?to=<number>`. When you use Click to Call, Twilio first calls your phone; when you answer, Twilio fetches that URL and dials the contact. Ensure `web.base.url` is set correctly in Odoo.

## Odoo Apps Store – repository URL

When you register your repository on [apps.odoo.com](https://apps.odoo.com), the URL must follow the standard format. Odoo may modify or normalize it to match:

```
ssh://git@github.com/<owner>/<repo>.git#<branch>
```

Examples:

- `ssh://git@github.com/yourusername/twilio-extension.git#18.0` (Odoo 18)
- `ssh://git@github.com/yourusername/twilio-extension.git#17.0` (Odoo 17)

Use the branch that matches your Odoo version (e.g. `#18.0`, `#17.0`). HTTPS-style URLs may be converted to this standard by the store.

## License

LGPL-3.
# oddo-twilio
