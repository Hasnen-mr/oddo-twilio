# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.action_utils import act_window


class DuplicateContactHub(models.TransientModel):
    _name = "duplicate.contact.hub"
    _description = "Duplicate Contact Reports & Settings"

    hub_section = fields.Selection(
        [
            ("merge_history", "Merge History"),
            ("scan_reports", "Scan Reports"),
            ("settings", "Settings"),
        ],
        string="Section",
        default="merge_history",
        required=True,
    )
    hub_nav = fields.Char(default="1")
    is_settings_user = fields.Boolean(compute="_compute_is_settings_user")

    merge_line_ids = fields.One2many(
        "duplicate.contact.hub.merge.line",
        "hub_id",
        string="Merge History",
        readonly=True,
    )
    scan_line_ids = fields.One2many(
        "duplicate.contact.hub.scan.line",
        "hub_id",
        string="Scan Reports",
        readonly=True,
    )

    duplicate_match_name = fields.Boolean(string="Match Name", default=True)
    duplicate_match_phone = fields.Boolean(string="Match Phone", default=True)
    duplicate_match_email = fields.Boolean(string="Match Email", default=True)
    duplicate_match_vat = fields.Boolean(string="Match Tax ID / GST / VAT", default=True)
    duplicate_match_company = fields.Boolean(string="Match Company", default=True)
    duplicate_match_website = fields.Boolean(string="Match Website", default=True)
    duplicate_match_address = fields.Boolean(string="Match Address", default=True)
    duplicate_match_ai = fields.Boolean(string="AI Similarity", default=False)
    duplicate_review_threshold = fields.Float(string="Review Threshold %", default=90.0)
    duplicate_min_threshold = fields.Float(string="Minimum Match %", default=72.0)
    duplicate_auto_merge = fields.Boolean(string="Auto-merge exact matches", default=False)
    duplicate_api_block = fields.Boolean(string="Block API duplicate creation", default=False)
    duplicate_api_warn = fields.Boolean(string="Warn on API duplicates", default=True)
    duplicate_cron_interval = fields.Selection(
        [
            ("hourly", "Every Hour"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("off", "Off"),
        ],
        string="Automatic Detection",
        default="daily",
    )
    duplicate_scan_limit = fields.Integer(string="Scan Batch Size", default=5000)

    @api.depends_context("uid")
    def _compute_is_settings_user(self):
        is_admin = self.env.user.has_group("base.group_system")
        for record in self:
            record.is_settings_user = is_admin

    @api.model
    def _settings_from_icp(self):
        icp = self.env["ir.config_parameter"].sudo()

        def _bool(key, default="True"):
            return icp.get_param(key, default) == "True"

        return {
            "duplicate_match_name": _bool("duplicate_contact.match_name"),
            "duplicate_match_phone": _bool("duplicate_contact.match_phone"),
            "duplicate_match_email": _bool("duplicate_contact.match_email"),
            "duplicate_match_vat": _bool("duplicate_contact.match_vat"),
            "duplicate_match_company": _bool("duplicate_contact.match_company"),
            "duplicate_match_website": _bool("duplicate_contact.match_website"),
            "duplicate_match_address": _bool("duplicate_contact.match_address"),
            "duplicate_match_ai": _bool("duplicate_contact.match_ai", "False"),
            "duplicate_review_threshold": float(
                icp.get_param("duplicate_contact.review_threshold", "90") or 90
            ),
            "duplicate_min_threshold": float(
                icp.get_param("duplicate_contact.min_threshold", "72") or 72
            ),
            "duplicate_auto_merge": _bool("duplicate_contact.auto_merge", "False"),
            "duplicate_api_block": _bool("duplicate_contact.api_block", "False"),
            "duplicate_api_warn": _bool("duplicate_contact.api_warn"),
            "duplicate_cron_interval": icp.get_param(
                "duplicate_contact.cron_interval", "daily"
            ),
            "duplicate_scan_limit": int(
                icp.get_param("duplicate_contact.scan_limit", "5000") or 5000
            ),
        }

    def _write_settings_to_icp(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        mapping = {
            "duplicate_contact.match_name": self.duplicate_match_name,
            "duplicate_contact.match_phone": self.duplicate_match_phone,
            "duplicate_contact.match_email": self.duplicate_match_email,
            "duplicate_contact.match_vat": self.duplicate_match_vat,
            "duplicate_contact.match_company": self.duplicate_match_company,
            "duplicate_contact.match_website": self.duplicate_match_website,
            "duplicate_contact.match_address": self.duplicate_match_address,
            "duplicate_contact.match_ai": self.duplicate_match_ai,
            "duplicate_contact.review_threshold": self.duplicate_review_threshold,
            "duplicate_contact.min_threshold": self.duplicate_min_threshold,
            "duplicate_contact.auto_merge": self.duplicate_auto_merge,
            "duplicate_contact.api_block": self.duplicate_api_block,
            "duplicate_contact.api_warn": self.duplicate_api_warn,
            "duplicate_contact.cron_interval": self.duplicate_cron_interval,
            "duplicate_contact.scan_limit": self.duplicate_scan_limit,
        }
        for key, value in mapping.items():
            icp.set_param(key, str(value))
        self.env["duplicate.contact.dashboard"]._sync_duplicate_cron()

    def _refresh_lines(self):
        self.ensure_one()
        History = self.env["duplicate.contact.merge.history"].sudo()
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()

        merge_lines = [
            (0, 0, {"history_id": history.id})
            for history in History.search([], limit=200)
        ]
        scan_lines = [
            (0, 0, {"scan_log_id": log.id})
            for log in ScanLog.search([], limit=200)
        ]
        self.write({
            "merge_line_ids": [(5, 0, 0)] + merge_lines,
            "scan_line_ids": [(5, 0, 0)] + scan_lines,
        })

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        values.update(self._settings_from_icp())
        section = self.env.context.get("duplicate_hub_section", "merge_history")
        if section == "settings" and not self.env.user.has_group("base.group_system"):
            section = "merge_history"
        values["hub_section"] = section
        return values

    @api.model
    def action_back_to_dashboard(self):
        return self.env["duplicate.contact.dashboard"].action_open_dashboard()

    @api.model
    def action_open_hub(self, section=None):
        section = section or self.env.context.get("duplicate_hub_section") or "merge_history"
        if section == "settings" and not self.env.user.has_group("base.group_system"):
            section = "merge_history"
        hub = self.create({"hub_section": section})
        hub._refresh_lines()
        return act_window(
            self.env,
            self._name,
            view_modes="form",
            name="Reports & Settings",
            res_id=hub.id,
            context={"duplicate_hub_section": section},
        )

    def _reload_hub(self):
        self.ensure_one()
        self._refresh_lines()
        return act_window(
            self.env,
            self._name,
            view_modes="form",
            name="Reports & Settings",
            res_id=self.id,
            context={"duplicate_hub_section": self.hub_section},
        )

    def action_save_settings(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise UserError("Only administrators can change duplicate contact settings.")
        self._write_settings_to_icp()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Settings saved",
                "message": "Duplicate contact settings were updated.",
                "type": "success",
                "sticky": False,
                "next": self._reload_hub(),
            },
        }

    def action_run_duplicate_scan(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise UserError("Only administrators can run scans from settings.")
        from ..services.detection import DuplicateDetectionService
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()
        active = ScanLog._get_active_scan() or ScanLog._start_scan(source="manual")
        stats = DuplicateDetectionService(self.env).run_scan_batch(
            scan_log=active,
            source="manual",
            max_batches=20,
        )
        self._refresh_lines()
        if stats.get("has_more"):
            message = "Sync running: %s / %s contacts (%.1f%%)." % (
                f"{stats.get('processed', 0):,}",
                f"{stats.get('total', 0):,}",
                stats.get("progress", 0),
            )
            notif_type = "warning"
        else:
            message = "Scan completed: %s contacts. Created %s pairs." % (
                f"{stats.get('processed', 0):,}",
                stats.get("created", 0),
            )
            notif_type = "success"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Duplicate Scan",
                "message": message,
                "type": notif_type,
                "sticky": False,
                "next": self._reload_hub(),
            },
        }
