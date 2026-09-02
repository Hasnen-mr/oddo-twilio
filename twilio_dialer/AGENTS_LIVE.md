# AGENTS_LIVE.md — PRODUCTION & LIVE SERVER DIRECTIVES

> **ENVIRONMENT SCOPE: PRODUCTION / LIVE SERVER ONLY (`https://odoo19.zantatech.com`)**  
> This instruction document applies **strictly** to the live production server environment at `136.113.230.12`.  
> **Production is READ-ONLY by default. Strict safety and audit protocols must be enforced at all times.**

---

## 1. PRODUCTION ENVIRONMENT CONFIGURATION MATRIX

| Parameter | Production Specification |
|---|---|
| **Odoo Version** | Odoo 19.5 (Hardened & Sandboxed) |
| **Frontend Framework** | OWL 3 (Odoo Web Library) |
| **Public URL** | `https://odoo19.zantatech.com` |
| **Server Host** | `136.113.230.12` (`dev.gulani`) |
| **Database Name** | `odoo19` |
| **Database Backend** | PostgreSQL 16 on `127.0.0.1:5432` |
| **Python Environment** | Python 3.13.5 (`/opt/odoo19/venv/bin/python3`) |
| **Systemd Service** | `odoo19.service` |
| **Architecture** | Multi-worker (2 HTTP workers on port `8074`, 1 Gevent/WebSocket worker on port `8075`) |
| **Web Server** | Nginx reverse proxy with SSL termination |
| **Addons Path** | `/opt/odoo19/custom_addons/twilio_dialer`, `/opt/odoo19/odoo/addons` |
| **Primary Module** | `twilio_dialer` (installed, version `19.5.1.0.0`) |
| **Extended Module** | `twilio_dialer_pro` (uninstalled) |

---

## 2. STRICT PRODUCTION OPERATIONAL RULES

1. **READ-ONLY DEFAULT**:
   - Production is strictly read-only.
   - **NEVER** modify source code, Python files, QWeb XML templates, JavaScript modules, SCSS stylesheets, database records, Nginx configs, Odoo configs, Twilio credentials, or service definitions unless explicitly authorized by the user.

2. **No Blind Modifications or Deletions**:
   - **NEVER** blindly delete `ir_attachment` records. If asset cache clearing is needed, verify the exact attachment URLs and IDs first.
   - **NEVER** run arbitrary database updates (`UPDATE`, `DELETE`, `DROP`).
   - **NEVER** touch `mcp_claude` or modify external server packages.
   - **NEVER** execute `git commit` or `git push`.

3. **Diagnose First, Act Second**:
   - For any reported issue on production, perform a full forensic audit before proposing any action.
   - Record and log the complete environment state (module state, active PIDs, asset bundle hashes, database schema) **before** and **after** any authorized action.

4. **Smallest Safe Action**:
   - If an operational change is authorized (e.g., service restart, asset regeneration, module upgrade), execute only the minimal required command sequence.
   - Example safe upgrade sequence:
     ```bash
     sudo systemctl stop odoo19
     sudo -u odoo /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin -c /etc/odoo19.conf -d odoo19 -u twilio_dialer --stop-after-init
     sudo systemctl start odoo19
     ```

5. **Post-Action Runtime Verification**:
   - After any change, verify system health:
     - `sudo systemctl status odoo19`
     - HTTP 200 response on `/web/login` and `/odoo`
     - Gevent WebSocket listener on port `8075`
     - Nginx reverse proxy routing
     - Real browser CDP test for zero uncaught JavaScript exceptions.

---

## 3. ASSET CACHE vs. SOURCE CODE DISCIPLINE

> **CRITICAL PRINCIPLE: LIVE FAILURE ≠ SOURCE CODE FAILURE**  
> An error on production does **NOT** mean the source code is broken. Always differentiate between stale compiled asset bundles and actual codebase defects.

### Forensic Comparison Checklist (When Localhost Works but Live Fails):
1. **Compare Git Revisions**: Verify if `/opt/odoo19/custom_addons/twilio_dialer` matches the tested local branch commit.
2. **Compare Module Manifests**: Check version numbers and asset bundle definitions in `__manifest__.py`.
3. **Compare Odoo Core Versions**: Local is Odoo 19.0; Production is Odoo 19.5 (Python 3.13). Note version-specific API differences.
4. **Inspect Asset Hashes**: Check the hash in `/web/assets/<hash>/web.assets_web.min.js`.
5. **Inspect Attachment Timestamps**: Query `SELECT id, name, url, create_date FROM ir_attachment WHERE url LIKE '%assets%'` to verify if stale bundles are being served.
6. **Inspect Worker Memory Cache**: Verify if running workers were started before or after the latest code update.
7. **Inspect Browser Cache**: Ensure testing is conducted with browser cache disabled (`Network.setCacheDisabled: true`).

**Rule**: **NEVER rewrite working source code simply because the production server is serving an outdated compiled asset bundle.**

---

## 4. TWILIO CREDENTIALS & WEBRTC CLASSIFICATION

- **Credential Safety**: Never alter, overwrite, or rotate Twilio Account SIDs, Auth Tokens, or API Keys in production settings.
- **Classification Rule**:
  - If Twilio credentials are not configured in the production database, `/twilio_dialer/token` will return:
    `"Twilio Account SID and Auth Token are required. Open Configuration and save your credentials."`
  - This is an **EXPECTED INFORMATIONAL STATUS**, not a source-code error or bug.
  - In audit reports, classify WebRTC calling as **NOT TESTABLE (Credentials Absent)**, not as a code failure.

---

## 5. REAL-TIME PRESENCE & BUS RULES

- Production uses Gevent multi-worker dispatching on port `8075` (`/websocket`).
- Real-time bus channels must be verified through active WebSocket frame inspection, not assumed from static channel registration.
- Verify presence updates, agent status changes, and bus dispatching without interfering with live users.

---

## 6. EIGHT-STEP PRODUCTION INCIDENT RESOLUTION PROTOCOL

For every production defect or incident:
1. **Capture**: Log the exact HTTP status, traceback, or browser console exception.
2. **Identify Origin**: Pinpoint whether error occurs in Nginx, Odoo backend, PostgreSQL, WebSocket bus, or frontend OWL 3 bundle.
3. **Classify**: Assign exact category:
   - `Source Code Defect`
   - `Odoo 19.5 / Python 3.13 API Parity Issue`
   - `Stale Asset Bundle (ir_attachment cache)`
   - `Worker Memory / Restart Required`
   - `Nginx / WebSocket Proxy Misconfiguration`
   - `Missing Twilio Configuration (Expected)`
4. **Reproduce**: Confirm exact steps to reproduce in a clean browser session with cache disabled.
5. **Formulate Minimal Plan**: Propose the smallest safe remediation step.
6. **Obtain Explicit Authorization**: Await user confirmation before modifying any production file or service.
7. **Execute & Verify**: Apply fix, restart service cleanly, and run automated browser CDP audit.
8. **Report Evidence**: Provide exact before/after evidence, bundle hashes, and console logs.
