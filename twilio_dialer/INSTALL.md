# How to install Twilio Dialer (Odoo 18)

## Do not install from ZIP

This module contains **Python code** (models, wizards, controllers). Odoo’s **Apps → Import (zip)** only loads XML/data and **does not run Python**, so you will get:

```text
Invalid model name "twilio_config" in action definition.
```

You must install from the **addons path**.

---

## Install from addons path

1. **Copy the module folder**  
   Copy the whole `twilio_dialer` folder (this folder) into your Odoo addons directory, for example:
   - `/opt/odoo/addons/twilio_dialer`, or  
   - `~/odoo/addons/twilio_dialer`

2. **Add the path to Odoo** (if needed)  
   If the folder is not inside a directory that is already in the addons path, add it in `odoo.conf`:
   ```ini
   addons_path = /opt/odoo/addons,/opt/odoo/enterprise,/path/to/twilio_dialer_parent
   ```
   The path must be the **parent** of `twilio_dialer` (so Odoo finds `twilio_dialer` as a module).

3. **Restart Odoo**
   ```bash
   sudo systemctl restart odoo
   ```
   (or your usual restart command)

4. **Install or upgrade the app**
   - **Apps** → **Update Apps List** (if in developer mode)
   - Search for **Twilio Dialer**
   - Click **Install** or **Upgrade**

   Or from the command line:
   ```bash
   odoo -u twilio_dialer -d your_database
   ```

5. **Configure**  
   Go to **Twilio → Configuration** and set your Twilio Account SID and Auth Token.

---

## If you only have a ZIP

1. Unzip the file on your server.
2. Copy the **`twilio_dialer`** folder (the inner folder that contains `__manifest__.py`) into your Odoo addons directory.
3. Then follow steps 2–5 above.

Do **not** use **Apps → Import Module** with the ZIP; that path does not run Python and will keep failing with “Invalid model name”.
