# AGENTS_LOCAL.md — LOCALHOST & DEVELOPMENT ENVIRONMENT DIRECTIVES

> **ENVIRONMENT SCOPE: LOCALHOST ONLY (`http://localhost:8072`)**  
> This instruction document applies **strictly** to the local development, debugging, and testing environment on the host machine.  
> **NEVER apply these local development permissions or assumptions to the production/live server.**

---

## 1. ENVIRONMENT CONFIGURATION MATRIX

| Parameter | Localhost Specification |
|---|---|
| **Odoo Version** | Odoo 19.0 (Community / Core) |
| **Frontend Framework** | OWL 3 (Odoo Web Library) |
| **Base URL** | `http://localhost:8072` |
| **Database Name** | `odoo19` |
| **Database Backend** | PostgreSQL 16/17 on `localhost:5432` |
| **Python Environment** | Python 3.12 (`D:\Odoo\venv\Scripts\python.exe`) |
| **Odoo Source Path** | `D:\Odoo\odoo19` |
| **Odoo Configuration** | `D:\Odoo\odoo19\odoo19.conf` |
| **Active Module Path** | `D:\Odoo\repos\oddo-twilio-18.0` / `D:\Odoo\custom_addons` |
| **Primary Module** | `twilio_dialer` (installed, version `19.0.1.0.0`) |
| **Extended Module** | `twilio_dialer_pro` (normally uninstalled unless testing Pro features) |

---

## 2. STRICT LOCAL OPERATIONAL RULES

1. **Development & Testing Scope**:
   - Localhost is the authorized sandbox for code experimentation, refactoring, unit testing, and UI debugging.
   - Code modifications are permitted **only when explicitly requested or required** to solve local development tasks.

2. **Audit Before Modification**:
   - Always perform static code inspection, log examination, and architecture review before editing source code.
   - Prefer the smallest, cleanest, non-destructive fix over broad refactoring.

3. **Asset Bundle Regeneration**:
   - After modifying any JavaScript (`static/src/js/`), QWeb XML (`static/src/xml/`), or SCSS (`static/src/scss/`) files, always restart Odoo with `-u twilio_dialer` or purge local `ir_attachment` records to force asset bundle compilation.

4. **Real Browser Runtime Verification Required**:
   - Static inspection alone is **never** sufficient for a frontend verification.
   - Always verify changes in a real browser session (via CDP or automated browser runner) checking:
     - Zero uncaught JavaScript exceptions in the browser console.
     - Systray icon rendering and DOM mounting.
     - Popup open/close toggling.
     - Component lifecycle hooks (`setup`, `onWillStart`, `onWillUnmount`).

5. **Local Boundaries & Protections**:
   - **LOCAL PASS ≠ LIVE PASS**: Never assume a passing test on localhost guarantees a pass on production (Odoo 19.5, Python 3.13, gevent multi-worker proxy environment).
   - **Do NOT touch production**: Never execute remote SSH commands or alter production state while operating under local development directives.
   - **Do NOT modify Twilio credentials**: Preserve configured Account SIDs, Auth Tokens, and API Keys unless explicitly instructed.
   - **Do NOT touch MCP Claude**: Do not install, reconfigure, or alter MCP Claude configurations.
   - **Do NOT commit or push**: Never run `git commit` or `git push` unless explicit permission is granted by the user.

---

## 3. COMPATIBILITY & FEATURE INTEGRITY RULES

- **OWL 3 Parity**: Ensure all components adhere to OWL 3 rules:
  - Use `useState(this.dialer.state)` or safe reactive adapters.
  - Event handlers must never use bare string expressions with `this.` (e.g., use `t-on-click="togglePanel"`, NOT `t-on-click="this.togglePanel"`).
  - Component templates must be registered cleanly in the OWL template registry.
- **Twilio Feature Suite**: Preserve end-to-end functionality:
  - WebRTC Device instantiation and lifecycle.
  - Token generation (`/twilio_dialer/token`).
  - Outgoing and incoming call handling.
  - Phone number allocation, assigned-number routing, and caller ID switching.
  - Call logging, recording synchronization, and SMS workspace.
  - Presence updates, DND toggle, and real-time Bus notifications.
- **Edition Parity**: Preserve Community vs. Pro feature gates and separation.

---

## 4. STANDARD DEBUGGING WORKFLOW

When diagnosing any defect on Localhost:
1. **Capture**: Record the exact traceback, console error, or unexpected behavior.
2. **Identify Origin**: Trace to the exact file, line number, and component.
3. **Classify**: Categorize as Source Code, OWL/Odoo Compatibility, Asset Cache, Database Schema, or Twilio Configuration.
4. **Reproduce**: Confirm the issue is reliably reproducible under a clean session.
5. **Fix**: Implement the minimal, targeted code or template change.
6. **Verify**: Test in a real browser context and verify all related features.
7. **Document**: Report exact before/after evidence with file paths.
