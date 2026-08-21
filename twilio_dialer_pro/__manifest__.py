# -*- coding: utf-8 -*-
{
    'name': "Odoo Twilio Dialer Pro | Twilio VoIP Calling | Softphone | Auto Dialer | Click-to-Call | Call Recording | Call Center",

    'summary': "Twilio VoIP softphone, auto dialer, power dialer, click-to-call, call recording, AI transcription, voicemail & CRM call logs for Odoo sales and call center teams.",

    'description': """
Odoo Twilio Dialer — VoIP Softphone, Auto Dialer & Call Center Software
=======================================================================

SEO title: Odoo Twilio Dialer | VoIP Softphone | Auto Dialer | Click to Call | Call Center Software

Short description:
Best Twilio cloud calling system for Odoo with browser VoIP softphone, power auto dialer,
click-to-call, call recording, voicemail, AI transcription, AI call summary, inbound and
outbound dialer, and automatic CRM call logs for sales dialer and contact center teams.

Full description:
Transform Odoo into a cloud telephony workspace powered by your own Twilio account —
no external softphone required. Ideal if you are evaluating business phone and dialer
platforms and want calling native inside Odoo.

Top calling software names (category keywords)
----------------------------------------------
Aircall, RingCentral, Dialpad, Five9, JustCall, Talkdesk, Genesys Cloud, Vonage, 8x8, PhoneBurner

Dialer & calling SEO keywords
-----------------------------
Odoo Twilio dialer, VoIP softphone, auto dialer, power dialer, predictive dialer, sales dialer,
outbound dialer, inbound call center, click to call, browser dialer, cloud phone system,
business phone system, telephony CRM, call recording software, call tracking, call logs,
AI call transcription, AI call summary, contact center software, SIP softphone, Odoo VoIP,
Twilio Voice SDK, CRM dialer integration, telemarketing dialer, customer support calling

Key Features
------------
* Twilio Voice Calling (inbound & outbound)
* Browser-based VoIP Softphone
* One-click Click-to-Call from Contacts
* Auto Dialer / Power Dialer campaigns
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

Pricing
-------
* Free on the Odoo Apps Store
* Optional In-App Purchase add-ons for higher volume
* Twilio voice minutes billed on your own Twilio account

Requirements
------------
* Odoo 14 / 15 / 16 / 17 / 18 / 19 (matching branch)
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
    'live_test_url': "https://www.youtube.com/watch?v=bwgUI6tYrT8",
    'price': 99.0,
    'currency': 'USD',

    'category': 'Productivity/Communications',
    'version': '17.0.1.2.98',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'contacts',
        'mail',
        'phone_validation',
        'crm',
    ],

    'external_dependencies': {
        'python': [
            'twilio',
            'jwt',
        ],
    },

    'data': [
        'security/ir.model.access.csv',
        'views/dialer_actions.xml',
                'views/res_config_settings_views.xml',
        'views/call_log_views.xml',
        'views/sms_log_views.xml',
        'views/sms_template_views.xml',
        'views/auto_dialer_views.xml',
        'views/res_partner_views.xml',
        'views/crm_lead_views.xml',
        'views/terms_privacy_views.xml',
        'views/contact_us_views.xml',
        'views/help_views.xml',
        'views/dashboard_views.xml',
        'views/billing_views.xml',
        'views/menu_views.xml',
        'views/number_allocation_views.xml',
    ],

    'images': [
        'static/description/screenshot_dashboard.png',
        'static/description/screenshot_settings.png',
        'static/description/screenshot_call_logs.png',
        'static/description/product_overview.png',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,

    'assets': {
        'web.assets_backend': [
            # Twilio Voice SDK is loaded at runtime via loadJS (UMD) — do not bundle it
            'twilio_dialer_pro/static/src/js/country_codes.js',
            'twilio_dialer_pro/static/src/js/phone_utils.js',
            'twilio_dialer_pro/static/src/js/phone_country_field.js',
            'twilio_dialer_pro/static/src/js/device_manager.js',
            'twilio_dialer_pro/static/src/js/dialer_service.js',
            'twilio_dialer_pro/static/src/js/auto_dialer_runner.js',
            'twilio_dialer_pro/static/src/js/contact_phone_field.js',
            'twilio_dialer_pro/static/src/js/contact_sms_button.js',
            'twilio_dialer_pro/static/src/js/sms_popup.js',
            'twilio_dialer_pro/static/src/js/sms_messaging_dialog.js',
            'twilio_dialer_pro/static/src/js/sms_workspace.js',
            'twilio_dialer_pro/static/src/js/billing.js',
            'twilio_dialer_pro/static/src/js/onboarding_wizard.js',
            'twilio_dialer_pro/static/src/js/credentials_help_dialog.js',
            'twilio_dialer_pro/static/src/js/help_dialog.js',
            'twilio_dialer_pro/static/src/js/help_bubble.js',
            'twilio_dialer_pro/static/src/js/dashboard_form.js',
            'twilio_dialer_pro/static/src/js/settings_ui_field.js',
            'twilio_dialer_pro/static/src/js/config_nav.js',
            'twilio_dialer_pro/static/src/js/about_nav.js',
            'twilio_dialer_pro/static/src/js/call_settings_cache.js',
            'twilio_dialer_pro/static/src/js/call_settings_autosave.js',
            'twilio_dialer_pro/static/src/js/ai_settings_link.js',
            'twilio_dialer_pro/static/src/js/password_toggle_field.js',
            'twilio_dialer_pro/static/src/js/dialer_popup.js',
            'twilio_dialer_pro/static/src/js/dialer_systray.js',
            'twilio_dialer_pro/static/src/js/version_update_dialog.js',
            'twilio_dialer_pro/static/src/js/version_update_service.js',
            'twilio_dialer_pro/static/src/js/transcript_tab_nav.js',
            'twilio_dialer_pro/static/src/xml/**/*.xml',
            'twilio_dialer_pro/static/src/scss/**/*.scss',
        ],
    },
}
