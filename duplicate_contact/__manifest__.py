# -*- coding: utf-8 -*-
{
    "name": "Smart Duplicate Contact Manager | AI Contact Deduplication & Merge",

    "summary": "Detect duplicate contacts with fuzzy matching, confidence scores, merge wizard, dashboard, and scheduled scans for Odoo CRM.",

    "description": """
Smart Duplicate Contact Manager
===============================

Enterprise-grade contact deduplication for Odoo. Find duplicates after imports,
API integrations, website signups, telephony, WhatsApp, and manual entry — then
review, merge, or ignore them safely.

Key Features
------------
* Exact match on Tax ID / GST / VAT / PAN, email, and normalized phone
* Fuzzy company and contact name matching (Levenshtein, Jaro-Winkler, token sort)
* Website and address normalization
* Confidence score with Duplicate / Possible Duplicate labels
* Duplicate dashboard with KPIs
* Review screen with match reasons
* Field-by-field merge wizard (name, phone, email, address, notes)
* Reassign related records (messages, followers, attachments, CRM, sales, invoices)
* Merge history audit log
* Ignore list for intentional duplicates
* Scheduled automatic detection (hourly, daily, weekly, monthly)
* API / import duplicate warnings and optional blocking
* Improved contact search by normalized phone

Perfect For
-----------
* CRM and Sales teams
* Accounting and invoicing
* Helpdesk and support
* Marketing databases
* Any Odoo customer with large contact lists

Support
-------
Email: developer.lifetips@gmail.com
Website: https://extension.mybroadcast.online
    """,

    "author": "Solutions Master",
    "website": "https://extension.mybroadcast.online",
    "support": "developer.lifetips@gmail.com",

    "category": "Sales/CRM",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",

    "depends": [
        "base",
        "contacts",
        "mail",
    ],

    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/duplicate_pair_views.xml",
        "views/merge_history_views.xml",
        "views/merge_wizard_views.xml",
        "views/dashboard_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",
    ],

    "images": [
        "static/description/icon.png",
    ],

    "installable": True,
    "application": True,
    "auto_install": False,
}
