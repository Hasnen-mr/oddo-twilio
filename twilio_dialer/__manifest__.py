# -*- coding: utf-8 -*-
{
    'name': "Twilio Calling System for Odoo | Auto Dialer | Call Logs | AI Transcription",

    'summary': "Free Twilio calling for Odoo — Auto Dialer, contact activity, local call logs & AI transcription.",

    'description': """
Twilio Call Auto Dialer for Odoo
================================

Complete Twilio calling system inside Odoo: browser softphone, Auto Dialer campaigns,
contact activity, local call log records, and optional AI call transcription & summaries.

Twilio calling system
---------------------
* Make and receive calls from Odoo with Twilio Voice
* Connects to your own Twilio account
* In-app dialpad with country codes and caller ID
* Secure credentials stored in your Odoo configuration

Auto Dialer
-----------
* Create outbound campaigns with phone lists
* Start, pause, next, and skip through numbers
* Track dialed, remaining, and connected counts
* Built for sales outreach and follow-up calling

Contact activity
----------------
* Call directly from Odoo Contacts
* Link calls to partners and keep CRM history together
* Schedule follow-ups and activities on call records
* Easy click-to-call workflow for your team

Call log local records
----------------------
* Store call logs locally in Odoo (status, duration, numbers)
* Search, filter, and report on inbound and outbound calls
* Keep records in your database — not only in Twilio
* Connect logs to contacts for a full communication trail

Transcription & AI summary
--------------------------
* Optional AI transcription of call recordings
* Generate short CRM-friendly call summaries
* Configure your preferred AI provider in settings
* Post insights back to the contact when needed

Pricing (free with fair usage)
------------------------------
* **Free to install** — no module purchase fee while this offer is active
* **Monthly fair-usage allowance** — initial free limit for normal business use
* **Higher volume** — purchase add-ons via In-App Purchases when you need more
* **Twilio usage** — voice minutes billed on your own Twilio account (external service)

Requirements
------------
* Odoo 18
* Twilio account with a phone number and balance
* Public HTTPS URL for TwiML voice callbacks (production)
* Optional: AI provider API key for transcription and summary
    """,

    'author': "Solutions Master",
    'website': "https://extension.mybroadcast.online",
    'support': "developer.lifetips@gmail.com",

    'category': 'Productivity/Communications',
    'version': '18.0.1.2.38',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'contacts',
        'mail',
        'phone_validation',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/dialer_actions.xml',
        'views/res_config_settings_views.xml',
        'views/call_log_views.xml',
        'views/auto_dialer_views.xml',
        'views/res_partner_views.xml',
        'views/terms_privacy_views.xml',
        'views/contact_us_views.xml',
        'views/help_views.xml',
        'views/dashboard_views.xml',
        'views/billing_views.xml',
        'views/menu_views.xml',
    ],

    'images': [
        'static/description/cover.png',
        'static/description/main_screenshot.png',
    ],

    'installable': True,
    'application': True,

    'assets': {
        'web.assets_backend': [
            # Twilio Voice SDK is loaded at runtime via loadJS (UMD) — do not bundle it
            'twilio_dialer/static/src/js/country_codes.js',
            'twilio_dialer/static/src/js/phone_utils.js',
            'twilio_dialer/static/src/js/device_manager.js',
            'twilio_dialer/static/src/js/dialer_service.js',
            'twilio_dialer/static/src/js/contact_phone_field.js',
            'twilio_dialer/static/src/js/billing.js',
            'twilio_dialer/static/src/js/config_nav.js',
            'twilio_dialer/static/src/js/about_nav.js',
            'twilio_dialer/static/src/js/call_settings_autosave.js',
            'twilio_dialer/static/src/js/password_toggle_field.js',
            'twilio_dialer/static/src/js/dialer_popup.js',
            'twilio_dialer/static/src/js/dialer_systray.js',
            'twilio_dialer/static/src/xml/**/*.xml',
            'twilio_dialer/static/src/scss/**/*.scss',
        ],
    },
}
