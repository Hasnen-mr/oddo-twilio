# AGENTS.md — Twilio Power Dialer for Odoo 18

> Permanent engineering context for the `odoo-twilio-power-dialer` repository.
> Last updated: 2026-07-15

---

## 1. Project Overview

| Field | Value |
|---|---|
| Project | Twilio Power Dialer |
| Company | ZantaTech |
| Repository | `D:\Zantatech\odoo-twilio-power-dialer` |
| Module | `twilio_power_dialer` |
| Odoo Version | 18.0 |
| Python Version | 3.12+ |
| License | LGPL-3 |
| Module Version | 18.0.1.0.0 |

**Purpose:** A production-oriented Odoo 18 module that integrates Twilio Voice to enable browser-based outbound calling directly from the Odoo backend. The module provides a configuration screen for Twilio credentials, a sticky right-side dialer panel with a full dial pad, and is designed to eventually support power dialer campaigns, call logging, and CRM integration.

**Current Stage:** Phase 5 — Twilio Voice SDK integration in progress. Backend token endpoint complete. Frontend device registration blocked by SDK asset compatibility issue (see Section 9).

---

## 2. Architecture

### High-Level

```
┌────────────────────────────────────────────────────────────────────┐
│                         Odoo 18 Backend                           │
│                                                                    │
│  res.config.settings ──→ ir.config_parameter (persistent store)   │
│         │                                                          │
│         └──→ twilio.service (AbstractModel)                       │
│                  ├── Twilio REST API (config, keys, TwiML apps)   │
│                  └── AccessToken + VoiceGrant (JWT generation)    │
│                                                                    │
│  twilio.controller ──→ GET /twilio_power_dialer/token             │
└────────────────────────────────────┬───────────────────────────────┘
                                     │ JSON { success, token }
┌────────────────────────────────────▼───────────────────────────────┐
│                        Odoo 18 Frontend                           │
│                                                                    │
│  DialerSystray (systray registry)                                 │
│      └──→ DialerPopup (OWL Component)                             │
│              ├── DeviceManager (SDK lifecycle singleton)           │
│              │       └──→ Twilio.Device (SDK 2.x)                 │
│              ├── Country Codes (static data)                      │
│              └── SCSS (all styling)                               │
└────────────────────────────────────────────────────────────────────┘
```

### Backend

| Component | Type | Responsibility |
|---|---|---|
| `res.config.settings` | `TransientModel` | Stores all Twilio credentials as `config_parameter`. Orchestrates the "Generate Configuration" button action. |
| `twilio.service` | `AbstractModel` | Owns all Twilio API logic: REST client initialization, API key generation, TwiML application CRUD, Access Token (JWT) generation. No database table. |
| `twilio.controller` | `Controller` | Thin HTTP endpoint. Validates via `auth="user"`, delegates to `twilio.service`, returns JSON. |
| `ir.config_parameter` | System | Persistent key-value store for all Twilio configuration values. |

**Config parameter keys:**

| Key | Field | Editable |
|---|---|---|
| `twilio_power_dialer.account_sid` | Account SID | Yes |
| `twilio_power_dialer.auth_token` | Auth Token | Yes |
| `twilio_power_dialer.api_key_sid` | API Key SID | No (readonly) |
| `twilio_power_dialer.api_secret` | API Secret | No (readonly) |
| `twilio_power_dialer.application_sid` | TwiML Application SID | No (readonly) |
| `twilio_power_dialer.voice_url` | Voice URL | No (readonly) |

### Frontend

| Component | Type | Responsibility |
|---|---|---|
| `DialerSystray` | OWL Component | Registered in `web.systray` registry. Renders the phone icon button and the slide-in panel. Manages open/close state. |
| `DialerPopup` | OWL Component | The dialer UI. Manages phone number entry, country selection, caller selection, keypad, status display. Initializes DeviceManager on mount. |
| `DeviceManager` | JS Singleton | Owns the entire Twilio Voice SDK lifecycle: fetch token, create Device, register, handle events, refresh token, destroy. Exposes status via callback. No UI logic. |
| `COUNTRY_CODES` | JS Module | Static array of country objects `{ name, code, flag, label }`. Used by the country selector dropdown. |
| `dialer.scss` | SCSS | All styling for the dialer panel, keypad, dropdowns, status badges, footer. Uses BEM-like naming with `o_dialer_` prefix. |
| `dialer_templates.xml` | OWL XML | Templates for `DialerSystray` and `DialerPopup`. |

---

## 3. Completed Features

### Phase 1–3: Configuration & Settings

- Twilio configuration UI in Settings
- Account SID storage
- Auth Token storage
- API Key generation and persistence
- API Secret generation and persistence
- TwiML Application creation and persistence
- Application SID storage
- Voice URL configuration (default: `https://extension.mybroadcast.online/call-setup`)
- Configuration status display ("Connected" / "Not Configured")
- Safe cleanup using stored SIDs (delete API key, delete TwiML app)
- Root menu item
- Settings menu item

### Phase 4: Dialer UI

- Sticky right-side dialer panel (CSS transform slide-in)
- Dial pad (3x4 grid, digits 0-9)
- Country code selector with search/filter
- Caller number selector (Calling From dropdown)
- 10-digit phone number validation
- Backspace and clear buttons
- Redial support (remembers last dialed number)
- Call button (enabled only when 10 digits entered)
- Status badge in header (color-coded)
- Status footer (color-coded dot + label)
- Responsive design (360px breakpoint)
- Close button to dismiss panel

### Phase 5.1: Backend Token Endpoint

- Access Token (JWT) generation in `twilio.service`
- `generate_access_token(env)` method
- VoiceGrant with outgoing application SID
- Identity format: `odoo_user_<uid>`
- Controller: `GET /twilio_power_dialer/token`
- JSON response: `{ success, token }` or `{ success, message }`
- Validation of all 4 required config parameters
- Error handling with UserError for missing config

### Phase 5.2: Frontend SDK Integration (In Progress)

- DeviceManager singleton created (`device_manager.js`)
- OWL 2 lifecycle hooks: `onWillStart`, `onWillUnmount`
- Status flow: Initializing → Fetching Token → Registering → Ready
- `statusClass` getter for CSS mapping
- `statusLabel` getter for display text
- Token refresh on `tokenWillExpire` event
- Cleanup on component unmount
- Debug console.log statements added (temporary, to be removed)

### Review Comments Implemented

| # | Summary |
|---|---|
| 1 | Shared Twilio client pattern (service layer) |
| 2 | Application SID persistence via config_parameter |
| 3 | Settings persistence with `set_values()` |
| 4 | Menu and navigation structure |
| 5 | Configuration UX (readonly generated fields, status display) |
| 6 | Cleanup by stored SID (not re-fetching) |
| 7 | Backend token endpoint (Phase 5.1) |
| 8 | Frontend SDK integration (Phase 5.2) |
| 9 | SDK version verification (identified 1.x vs 2.x mismatch) |

---

## 4. Current Frontend Structure

```
twilio_power_dialer/static/
├── lib/
│   └── twilio/
│       └── twilio.min.js          # Twilio Voice SDK 2.18.3 (295 KB)
│                                   # Source: twilio/twilio-voice.js tag 2.18.3
│                                   # File: dist/twilio.min.js
│                                   # Exposes: window.Twilio.Device
│
└── src/
    ├── js/
    │   ├── country_codes.js        # Static array of { name, code, flag, label }
    │   ├── device_manager.js       # Singleton: SDK lifecycle, token fetch, device events
    │   ├── dialer_systray.js       # Systray button + panel toggle, registers with registry
    │   └── dialer_popup.js         # Dialer UI: keypad, dropdowns, status, device init
    │
    ├── xml/
    │   └── dialer_templates.xml    # OWL templates for DialerSystray + DialerPopup
    │
    └── scss/
        └── dialer.scss             # All dialer styling (767 lines, o_dialer_ prefix)
```

### Asset Load Order (from `__manifest__.py`)

```
1. twilio_power_dialer/static/lib/twilio/twilio.min.js   ← SDK 2.x
2. twilio_power_dialer/static/src/js/country_codes.js     ← Static data
3. twilio_power_dialer/static/src/js/device_manager.js    ← Imports window.Twilio
4. twilio_power_dialer/static/src/js/dialer_systray.js    ← Imports DialerPopup
5. twilio_power_dialer/static/src/js/dialer_popup.js      ← Imports device_manager
6. twilio_power_dialer/static/src/xml/**/*.xml            ← OWL templates
7. twilio_power_dialer/static/src/scss/**/*.scss          ← Styles
```

### File Responsibilities

**`device_manager.js`**
- Exports `deviceManager` (singleton) and `STATUS` (frozen enum)
- `initialize(onStatusChange)` — main entry point, called from DialerPopup
- `_fetchToken()` — `GET /twilio_power_dialer/token`
- `_createDevice(token)` — `new Twilio.Device(token, options)`
- `_refreshToken()` — handles `tokenWillExpire`
- `destroy()` — cleans up device and callbacks
- Uses `_destroyed` flag to prevent stale callback execution

**`dialer_popup.js`**
- Imports `deviceManager` from `./device_manager`
- `onWillStart` → calls `deviceManager.initialize()`
- `onWillUnmount` → calls `deviceManager.destroy()`
- `_onDeviceStatusChange(status)` → updates `this.state.connectionStatus`
- `statusClass` getter → maps internal status to CSS class name
- `statusLabel` getter → maps internal status to display text
- Keypad, country selector, caller selector, validation logic

**`dialer_systray.js`**
- Registers `DialerSystray` in `web.systray` registry (sequence 30)
- Manages `isOpen` state for panel visibility
- `togglePanel()` bound to both the phone button and popup close button

---

## 5. Backend Structure

```
twilio_power_dialer/
├── __init__.py                     # imports controllers, models
├── __manifest__.py                 # Module definition, assets, dependencies
│
├── controllers/
│   ├── __init__.py                 # imports twilio_controller
│   └── twilio_controller.py        # GET /twilio_power_dialer/token
│
├── models/
│   ├── __init__.py                 # imports res_config_settings, twilio_service
│   ├── res_config_settings.py      # Twilio config fields, generate button action
│   ├── twilio_service.py           # AbstractModel: all Twilio API logic
│   └── call_log.py                 # EMPTY — placeholder for Phase 7
│
├── views/
│   ├── res_config_settings_views.xml  # Settings form with Twilio fields
│   ├── menu_views.xml                 # Root menu + settings menu
│   ├── call_log_views.xml             # EMPTY — placeholder for Phase 7
│   └── templates.xml                  # Commented-out boilerplate
│
├── security/
│   └── ir.model.access.csv        # Header only — no ACL rules defined yet
│
├── static/
│   ├── lib/twilio/twilio.min.js   # Twilio Voice SDK 2.18.3
│   └── src/
│       ├── js/                     # (see Section 4)
│       ├── xml/                    # (see Section 4)
│       └── scss/                   # (see Section 4)
│
└── demo/
    └── demo.xml                    # Commented-out boilerplate
```

### Key Model Details

**`twilio.service` (AbstractModel)**
- `_name = "twilio.service"`
- `get_client(account_sid, auth_token)` → `twilio.rest.Client`
- `generate_api_key(client)` → `{ api_key_sid, api_secret }`
- `create_twiml_application(client, voice_url)` → `{ application_sid }`
- `generate_configuration(account_sid, auth_token, voice_url)` → combined dict
- `generate_access_token(env)` → JWT string
- `delete_api_key(client, api_key_sid)` — safe cleanup
- `delete_twiml_application(client, application_sid)` — safe cleanup

**`res.config.settings` (TransientModel)**
- Inherits `res.config.settings`
- 6 Char fields with `config_parameter` attribute
- `_compute_twilio_status()` — computed "Connected" / "Not Configured"
- `action_generate_configuration()` — button handler

**`twilio.controller`**
- `GET /twilio_power_dialer/token` — `auth="user"`, `type="http"`
- Delegates to `twilio.service.generate_access_token(env)`
- Returns `request.make_json_response()`

---

## 6. Current Development Roadmap

### Completed

- [x] Phase 1: Twilio configuration screen
- [x] Phase 2: Account SID, Auth Token, API Key, API Secret, TwiML App, App SID storage
- [x] Phase 3: Configuration persistence, status display, safe cleanup
- [x] Phase 4: Dialer UI (sticky panel, keypad, country selector, validation, redial)
- [x] Phase 5.1: Backend Access Token endpoint

### In Progress

- [ ] Phase 5.2: Twilio Voice SDK integration & device registration
  - [x] DeviceManager abstraction created
  - [x] OWL 2 lifecycle hooks implemented
  - [x] Status flow mapped
  - [x] SDK 2.18.3 downloaded and bundled locally
  - [ ] **BLOCKED: White screen after SDK asset change** (see Section 9)

### Upcoming

- [ ] Phase 6: Outgoing calling (`device.connect()`)
- [ ] Phase 7: Call logs (model + views)
- [ ] Phase 8: Incoming calls (`device.on('incoming')`)
- [ ] Phase 9: Call controls (mute, hold, hangup)
- [ ] Phase 10: Power dialer campaigns
- [ ] Phase 11: CRM integration
- [ ] Phase 12: Call recording / notes

---

## 7. Development Principles

1. **Service layer owns Twilio API logic.** All Twilio REST API calls and JWT generation live in `twilio.service`. Never put Twilio API calls in controllers or models that inherit other models.

2. **Settings model orchestrates only.** `res.config.settings` coordinates the configuration flow but delegates actual API work to `twilio.service`.

3. **Thin controllers.** Controllers handle HTTP concerns only: authentication, request parsing, response formatting. Business logic is delegated to services.

4. **OWL components manage UI only.** `DialerPopup` and `DialerSystray` handle rendering and user interaction. They delegate device lifecycle to `DeviceManager`.

5. **DeviceManager owns SDK lifecycle.** `device_manager.js` is the single source of truth for Twilio Device state. UI components never touch `Twilio.Device` directly.

6. **No duplicated business logic.** Each piece of logic lives in exactly one place.

7. **Minimal diffs.** When modifying existing files, change only what is necessary. Preserve existing code style.

8. **Odoo 18 best practices.** Use OWL 2 composition API hooks (`onWillStart`, `onWillUnmount`). Use `config_parameter` for persistent settings. Use `AbstractModel` for service classes.

9. **SOLID principles.** Single responsibility, open/closed, dependency inversion (service injection via `env`).

10. **Production-ready.** Error handling, logging, validation at every boundary. No hardcoded credentials. No shortcuts.

---

## 8. Review Comments History

| # | Phase | Topic | Outcome |
|---|---|---|---|
| 1 | 1–2 | Shared Twilio client | Created `twilio.service` AbstractModel instead of inline client creation |
| 2 | 2 | Application SID persistence | Stored as `config_parameter` with `readonly=True` |
| 3 | 3 | Settings persistence | Used `set_values()` and `config_parameter` attributes |
| 4 | 3 | Navigation | Added root menu + Settings submenu under Technical |
| 5 | 3 | Configuration UX | Readonly generated fields, status badge, notification on success |
| 6 | 3 | Cleanup by SID | Delete API key and TwiML app using stored SIDs before regenerating |
| 7 | 5.1 | Backend token endpoint | New controller + `generate_access_token()` method, JWT with VoiceGrant |
| 8 | 5.2 | Frontend SDK integration | DeviceManager singleton, OWL 2 lifecycle hooks, status mapping |
| 9 | 5.2 | SDK version verification | Identified SDK 1.x (CDN) vs SDK 2.x (code) mismatch — root cause of runtime errors |

---

## 9. Current Known Issue

### BLOCKER: White Screen After SDK Asset Change

**Date:** 2026-07-15

**Trigger:** Changed `__manifest__.py` asset reference from CDN URL to local file.

**What changed in `__manifest__.py`:**

```python
# Before (worked but wrong SDK):
'https://sdk.twilio.com/js/client/releases/1.14.0/twilio.min.js'

# After (white screen):
'twilio_power_dialer/static/lib/twilio/twilio.min.js'
```

**SDK file details:**

- Source: `twilio/twilio-voice.js` GitHub repository
- Tag: `2.18.3` (latest release)
- File: `dist/twilio.min.js` from the source tarball
- Size: 301,902 bytes (295 KB)
- Format: UMD bundle (starts with `(function(root){var bundle=function(){...`)
- Location: `twilio_power_dialer/static/lib/twilio/twilio.min.js`

**Current symptoms:**

- Odoo web client fails to render
- Browser displays a white screen
- No UI loads at all
- No Odoo backend is accessible

**Possible causes (unconfirmed):**

- [ ] Asset pipeline fails to compile/bundle the local SDK file
- [ ] The SDK's UMD format is incompatible with Odoo's asset loader
- [ ] The SDK file contains code that throws during parsing/execution
- [ ] JavaScript runtime exception during OWL boot sequence
- [ ] Asset ordering issue (SDK loaded at wrong time)
- [ ] `window.Twilio` export conflicts with Odoo's module system
- [ ] The `/** @odoo-module **/` directive in other files causes issues with SDK loading
- [ ] Bundle size causes timeout or memory issue
- [ ] Content Security Policy blocks the local file
- [ ] Path resolution issue (relative vs absolute in Odoo asset pipeline)

**Root cause:** NOT YET CONFIRMED. No debugging has been performed.

---

## 10. Investigation Checklist

For the next debugging session, check the following in order:

```
□ 1. Check browser console for JavaScript errors
     - Look for syntax errors, module import failures, runtime exceptions
     - Note exact error messages and line numbers

□ 2. Check Odoo server log for asset compilation errors
     - Look for bundle-related errors
     - Check if the module loads successfully

□ 3. Check browser Network tab
     - Is twilio.min.js being served? (status code, content-type)
     - Is it being loaded before other JS files?
     - Are other JS files loading at all?

□ 4. Verify web.assets_backend manifest
     - Is the path correct? (no leading slash, forward slashes)
     - Is the file actually at that path on disk?
     - Is the glob pattern valid?

□ 5. Verify bundle compilation
     - Does `odoo-bin assets GENERATE` succeed?
     - Does the generated bundle contain the SDK?

□ 6. Verify twilio.min.js compatibility
     - Does it use `window.Twilio` global export?
     - Does it conflict with Odoo's AMD/ES module system?
     - Does it execute without errors in browser console?

□ 7. Verify window.Twilio export
     - After SDK loads, is `window.Twilio` defined?
     - Is `window.Twilio.Device` a constructor?

□ 8. Verify ES Module vs UMD bundle
     - The SDK is a UMD bundle (IIFE wrapping)
     - Odoo uses `/** @odoo-module **/` for ES module compatibility
     - These should be compatible but test

□ 9. Verify OWL boot sequence
     - Does OWL initialize before the SDK?
     - Does the SDK interfere with OWL's component registry?

□ 10. Verify asset ordering
     - SDK must load BEFORE device_manager.js
     - device_manager.js accesses window.Twilio
     - If SDK loads after, window.Twilio is undefined

□ 11. Try reverting to CDN URL temporarily
     - If CDN works but local file doesn't → file format issue
     - If both fail → different issue entirely

□ 12. Check if the issue is the SDK file or the path
     - Create an empty static/lib/twilio/twilio.min.js
     - If white screen persists → path issue
     - If white screen goes away → SDK file issue
```

---

## Appendix A: File Quick Reference

### Backend Files

| File | Lines | Status |
|---|---|---|
| `__init__.py` | 4 | Complete |
| `__manifest__.py` | 54 | Needs review (SDK path) |
| `controllers/__init__.py` | 3 | Complete |
| `controllers/twilio_controller.py` | 20 | Complete |
| `models/__init__.py` | 4 | Complete |
| `models/res_config_settings.py` | 88 | Complete |
| `models/twilio_service.py` | 135 | Complete (has dead code on line 90) |
| `models/call_log.py` | 0 | Empty placeholder |

### Frontend Files

| File | Lines | Status |
|---|---|---|
| `static/lib/twilio/twilio.min.js` | 1 (minified) | SDK 2.18.3, causes white screen |
| `static/src/js/country_codes.js` | ~250 | Complete |
| `static/src/js/device_manager.js` | 134 | Complete (has debug logs) |
| `static/src/js/dialer_systray.js` | 27 | Complete (has debug log) |
| `static/src/js/dialer_popup.js` | 205 | Complete (has debug logs) |
| `static/src/xml/dialer_templates.xml` | 179 | Complete |
| `static/src/scss/dialer.scss` | 767 | Complete |

### Views

| File | Status |
|---|---|
| `views/res_config_settings_views.xml` | Complete |
| `views/menu_views.xml` | Complete |
| `views/call_log_views.xml` | Empty placeholder |
| `views/templates.xml` | Commented-out boilerplate |

### Security

| File | Status |
|---|---|
| `security/ir.model.access.csv` | Header only, no ACL rules |

---

## Appendix B: Twilio SDK Version History

| Version | Package | CDN | Status |
|---|---|---|---|
| 1.x | `twilio-client` | `sdk.twilio.com/js/client/` | **EOL April 1, 2025** — shut down |
| 2.x | `@twilio/voice-sdk` | **Not available via CDN** | Current, v2.18.3 |

**Key API differences:**

| Feature | SDK 1.x | SDK 2.x |
|---|---|---|
| Constructor | `new Device()` then `device.setup(token)` | `new Device(token)` |
| Registration | No `register()` method | `device.register()` |
| Events | `ready`, `offline` | `registered`, `registering`, `unregistered` |
| Token refresh | Not available | `tokenWillExpire` event |
| Options | Different set | `codecPreferences`, `fakeLocalDTMF`, `enableRingingState` |

Our `device_manager.js` uses SDK 2.x API exclusively.
