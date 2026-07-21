# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    duplicate_match_name = fields.Boolean(
        string="Match Name",
        config_parameter="duplicate_contact.match_name",
        default=True,
    )
    duplicate_match_phone = fields.Boolean(
        string="Match Phone",
        config_parameter="duplicate_contact.match_phone",
        default=True,
    )
    duplicate_match_email = fields.Boolean(
        string="Match Email",
        config_parameter="duplicate_contact.match_email",
        default=True,
    )
    duplicate_match_vat = fields.Boolean(
        string="Match Tax ID / GST / VAT",
        config_parameter="duplicate_contact.match_vat",
        default=True,
    )
    duplicate_match_company = fields.Boolean(
        string="Match Company",
        config_parameter="duplicate_contact.match_company",
        default=True,
    )
    duplicate_match_website = fields.Boolean(
        string="Match Website",
        config_parameter="duplicate_contact.match_website",
        default=True,
    )
    duplicate_match_address = fields.Boolean(
        string="Match Address",
        config_parameter="duplicate_contact.match_address",
        default=True,
    )
    duplicate_match_ai = fields.Boolean(
        string="AI Similarity (when inconclusive)",
        config_parameter="duplicate_contact.match_ai",
        default=False,
        help="Reserved for future AI-assisted matching when traditional rules are inconclusive.",
    )
    duplicate_review_threshold = fields.Float(
        string="Review Threshold %",
        config_parameter="duplicate_contact.review_threshold",
        default=90.0,
    )
    duplicate_min_threshold = fields.Float(
        string="Minimum Match %",
        config_parameter="duplicate_contact.min_threshold",
        default=72.0,
    )
    duplicate_auto_merge = fields.Boolean(
        string="Auto-merge 100% matches",
        config_parameter="duplicate_contact.auto_merge",
        default=False,
    )
    duplicate_api_block = fields.Boolean(
        string="Block API duplicate creation",
        config_parameter="duplicate_contact.api_block",
        default=False,
    )
    duplicate_api_warn = fields.Boolean(
        string="Warn on API duplicates",
        config_parameter="duplicate_contact.api_warn",
        default=True,
    )
    duplicate_cron_interval = fields.Selection(
        [
            ("hourly", "Every Hour"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("off", "Off"),
        ],
        string="Automatic Detection",
        config_parameter="duplicate_contact.cron_interval",
        default="daily",
    )
    duplicate_scan_limit = fields.Integer(
        string="Scan Batch Size",
        config_parameter="duplicate_contact.scan_limit",
        default=2000,
    )

    def action_run_duplicate_scan(self):
        from ..services.detection import DuplicateDetectionService
        stats = DuplicateDetectionService(self.env).run_scan(source="manual")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Duplicate Scan",
                "message": "Created %(created)s, updated %(updated)s pairs." % stats,
                "type": "success",
                "sticky": False,
            },
        }
