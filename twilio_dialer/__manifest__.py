# -*- coding: utf-8 -*-
{
    'name': "Twilio Power Dialer",

    'summary': "Trusted Odoo softphone — Contacts, Auto Dialer, AI summary. $10 setup, clear billing.",

    'description': """
Twilio Power Dialer for Odoo
============================

Call from Odoo Contacts with a built-in softphone, Auto Dialer, call logs, and optional AI summaries.

Pricing (clear & transparent)
-----------------------------
* **$10 one-time setup** — no per-seat softphone fee
* **Twilio usage** — pay-as-you-go on your own Twilio account (external service required)

Features
--------
* In-Odoo dialpad with country codes
* Direct call from Odoo Contacts
* Auto Dialer campaigns
* Call logs linked to partners
* AI recording transcript & call summary (optional)
* Data stays in your Odoo + Twilio accounts — easy to use

Requirements
------------
* Odoo 13
* Twilio account with a phone number and balance
* Public HTTPS URL for TwiML voice callbacks (production)
* Optional: AI provider API key for transcript/summary
    """,

    'author': "Solutions Master",
    'website': "https://github.com/Hasnen-mr/odoo-twilio-power-dialer",
    'support': "developer.lifetips@gmail.com",

    'category': 'Productivity/Communications',
    'version': '13.0.1.1.3',
    'license': 'LGPL-3',
    'price': 10.0,
    'currency': 'USD',

    'depends': [
        'base',
        'contacts',
        'mail',
        'phone_validation',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/call_log_views.xml',
        'views/auto_dialer_views.xml',
        'views/contact_views.xml',
        'views/menu_views.xml',
    ],

    'images': [
        'static/description/banner.png',
    ],

    'installable': True,
    'application': True,

    'assets': {
        'web.assets_backend': [
            # Twilio Voice SDK is loaded at runtime via loadJS (UMD) — do not bundle it
            'twilio_dialer/static/src/js/country_codes.js',
            'twilio_dialer/static/src/js/device_manager.js',
            'twilio_dialer/static/src/js/dialer_service.js',
            'twilio_dialer/static/src/js/password_toggle_field.js',
            'twilio_dialer/static/src/js/dialer_popup.js',
            'twilio_dialer/static/src/js/dialer_systray.js',
            'twilio_dialer/static/src/xml/**/*.xml',
            'twilio_dialer/static/src/scss/**/*.scss',
        ],
    },
}
