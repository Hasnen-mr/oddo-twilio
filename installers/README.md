# OS Installers — Twilio Dialer

Interactive installers that help customers with an **existing Odoo** setup:

1. Find (or enter) the Odoo directory  
2. Copy `twilio_dialer` into a custom addons folder  
3. Optionally update `odoo.conf` `addons_path`  
4. Install Python dependency (`twilio`)  

Does **not** create a new database or new login. Use your existing Odoo user.

---

## macOS / Linux

```bash
cd twilio_dialer/installers
chmod +x install_mac.sh
./install_mac.sh
```

---

## Windows

Double-click:

```text
install_windows.bat
```

Or in PowerShell:

```powershell
cd twilio_dialer\installers
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
```

---

## After the installer finishes

1. Restart Odoo  
2. **Apps → Update Apps List**  
3. Install **Twilio Dialer**  
4. Open **Twilio Dialer → Configuration** and enter Account SID / Auth Token  

---

## Notes

- If Odoo is not auto-detected, enter the Odoo root or your custom addons folder manually.  
- Python must be the same environment Odoo uses (venv / system).  
- Works alongside other installed modules in most cases.  
