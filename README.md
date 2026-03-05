# Oddo Twilio (Odoo Apps Store)

Repository URL: `ssh://git@github.com/Hasnen-mr/oddo-twilio.git#18.0`

## If the store says "No module found"

The store expects **one folder at the root** of the repo, with the module inside it:

```
oddo-twilio/           (repo root after git clone)
  odoo_twilio/         (this folder must exist at root)
    __manifest__.py
    __init__.py
    models/
    views/
    ...
```

If your repo instead has `__manifest__.py` and `models/` at the **root** (no `odoo_twilio` folder), do this:

1. Clone the repo and go to its root:
   ```bash
   git clone ssh://git@github.com/Hasnen-mr/oddo-twilio.git
   cd oddo-twilio
   ```

2. Run the fix script (creates `odoo_twilio/` and moves all module files into it):
   ```bash
   chmod +x fix_repo_structure.sh
   ./fix_repo_structure.sh
   ```

3. Commit and push (use your branch, e.g. `18.0`):
   ```bash
   git add -A
   git commit -m "Fix: put module in odoo_twilio folder at root for Odoo Apps Store"
   git push origin 18.0
   ```

4. Re-run the store scan or re-submit the app.

## When the structure is correct

- At repo root you should see **only** the folder `odoo_twilio/` (and optionally this README and the script).
- Inside `odoo_twilio/` you must have `__manifest__.py`, `models/`, `views/`, etc.

## Module

- **Folder name:** `odoo_twilio` (must be one folder at root)
- **App name:** Twilio Connector – Calling, SMS and Call Logs

See `odoo_twilio/README.md` for installation and usage.
