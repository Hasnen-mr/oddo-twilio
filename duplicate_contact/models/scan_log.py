# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DuplicateContactScanLog(models.Model):
    _name = "duplicate.contact.scan.log"
    _description = "Duplicate Contact Scan Log"
    _order = "date_start desc, id desc"

    name = fields.Char(required=True, index=True)
    source = fields.Selection(
        [
            ("manual", "Manual"),
            ("cron", "Automatic"),
        ],
        default="manual",
        index=True,
    )
    state = fields.Selection(
        [
            ("running", "Running"),
            ("done", "Completed"),
            ("failed", "Failed"),
        ],
        default="running",
        index=True,
    )
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    total_contacts = fields.Integer(string="Total Contacts", readonly=True)
    processed_contacts = fields.Integer(string="Contacts Scanned", readonly=True)
    progress = fields.Float(string="Progress %", digits=(5, 2), readonly=True)
    scan_offset = fields.Integer(string="Batch Offset", readonly=True)
    batch_size = fields.Integer(string="Batch Size", readonly=True)
    pairs_created = fields.Integer(readonly=True)
    pairs_updated = fields.Integer(readonly=True)
    pairs_skipped = fields.Integer(readonly=True)
    date_start = fields.Datetime(default=fields.Datetime.now, readonly=True)
    date_end = fields.Datetime(readonly=True)
    message = fields.Text(readonly=True)

    def action_open_duplicates(self):
        self.ensure_one()
        from ..services.action_utils import xml_id_action
        return xml_id_action(
            self.env,
            "duplicate_contact.action_duplicate_contact_pairs",
            name="Duplicates from %s" % self.name,
        )

    @api.model
    def _get_active_scan(self):
        return self.search([("state", "=", "running")], limit=1, order="id desc")

    @api.model
    def _start_scan(self, source="manual"):
        active = self._get_active_scan()
        if active:
            return active
        total = self.env["res.partner"].sudo().search_count([("active", "=", True)])
        batch_size = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "duplicate_contact.scan_limit", "5000"
            )
            or 5000
        )
        log = self.create({
            "name": "Scan %s" % fields.Datetime.now(),
            "source": source,
            "state": "running",
            "total_contacts": total,
            "processed_contacts": 0,
            "progress": 0.0,
            "scan_offset": 0,
            "batch_size": batch_size,
            "pairs_created": 0,
            "pairs_updated": 0,
            "pairs_skipped": 0,
        })
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("duplicate_contact.scan_active", "True")
        icp.set_param("duplicate_contact.scan_log_id", str(log.id))
        icp.set_param("duplicate_contact.scan_offset", "0")
        return log

    def _mark_done(self, message=None):
        self.write({
            "state": "done",
            "date_end": fields.Datetime.now(),
            "progress": 100.0,
            "message": message or "Scan completed successfully.",
        })
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("duplicate_contact.scan_active", "False")
        icp.set_param("duplicate_contact.scan_offset", "0")

    def _mark_failed(self, message):
        self.write({
            "state": "failed",
            "date_end": fields.Datetime.now(),
            "message": message,
        })
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("duplicate_contact.scan_active", "False")
