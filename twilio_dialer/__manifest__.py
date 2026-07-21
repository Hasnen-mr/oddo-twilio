# -*- coding: utf-8 -*-
{
    'name': "Twilio Calling System for Odoo | VoIP Softphone | Auto Dialer | AI Transcription",

    'summary': "Twilio VoIP Softphone, Auto Dialer, Click-to-Call, Call Recording, AI Transcription, AI Summary, Voicemail & CRM Call Logs for Odoo.",

    'description': """
Twilio Calling System for Odoo
==============================

Complete Twilio cloud calling solution for Odoo with VoIP softphone, click-to-call,
auto dialer, call recording, voicemail, AI transcription, AI call summaries, and
automatic call logging inside your CRM.

Transform Odoo into a cloud telephony workspace powered by your own Twilio account —
no external softphone required.

Key Features
------------
* Twilio Voice Calling (inbound & outbound)
* Browser-based VoIP Softphone
* One-click Click-to-Call from Contacts
* Auto Dialer campaigns
* Voicemail configuration
* Call Recording options
* AI Call Transcription
* AI Call Summary
* Call History & local Call Logs
* Contact Call History
* Call Notes & activity trail
* DTMF keypad support
* Mute / hangup call controls
* Twilio Voice SDK integration
* CRM / Contacts integration
* Multi-user support
* Secure API configuration
* Real-time call status
* Automatic contact recognition
* AI-powered call insights

Modules Integrated
------------------
* Contacts
* Discuss / Mail
* Configuration & Billing workspace

Benefits
--------
* Increase agent productivity
* Centralize business communications in Odoo
* Track every customer conversation
* Improve sales outreach and customer support
* Automatic local call logging
* AI-powered conversation summaries
* Easy deployment with your Twilio account
* No external softphone required

Perfect For
-----------
* Sales Teams
* Customer Support
* Call Centers
* Real Estate
* Healthcare
* Recruitment
* Education
* Logistics
* Financial Services

Supported Keywords
------------------
Twilio Voice · VoIP · Browser Softphone · Click-to-Call · Auto Dialer ·
Call Recording · AI Transcription · AI Summary · Voicemail · Call Logs ·
Activity Timeline · CRM Integration · Secure Authentication

Pricing (free with fair usage)
------------------------------
* Free to install — no module purchase fee while this offer is active
* Monthly fair-usage allowance for normal business use
* Higher volume via In-App Purchase add-ons when needed
* Twilio voice minutes billed on your own Twilio account

Requirements
------------
* Odoo 18
* Paid Twilio account with phone number and balance
* Public HTTPS URL for TwiML voice callbacks (production)
* Optional: AI provider API key for transcription and summary

Support
-------
Professional implementation and customization available.
Email: developer.lifetips@gmail.com
Website: https://extension.mybroadcast.online
Bitly: https://bit.ly/odoo-twilio-dialer
    """,

    'author': "Solutions Master",
    'website': "https://extension.mybroadcast.online",
    'support': "developer.lifetips@gmail.com",

    'category': 'Productivity/Communications',
    'version': '18.0.1.2.60',
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
    'auto_install': False,

    'assets': {
        'web.assets_backend': [
            # Twilio Voice SDK is loaded at runtime via loadJS (UMD) — do not bundle it
            'twilio_dialer/static/src/js/country_codes.js',
            'twilio_dialer/static/src/js/phone_utils.js',
            'twilio_dialer/static/src/js/phone_country_field.js',
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
