# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DuplicateContactPair(models.Model):
    _name = "duplicate.contact.pair"
    _description = "Duplicate Contact Pair"
    _order = "confidence desc, id desc"

    partner_a_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    partner_b_id = fields.Many2one("res.partner", required=True, ondelete="cascade", index=True)
    confidence = fields.Float(string="Confidence %", digits=(5, 2), index=True)
    confidence_label = fields.Selection(
        [
            ("duplicate", "Duplicate"),
            ("possible", "Possible Duplicate"),
            ("low", "Low Match"),
        ],
        string="Label",
        index=True,
    )
    match_reasons = fields.Text(string="Match Reasons")
    state = fields.Selection(
        [
            ("open", "Open"),
            ("review", "Need Review"),
            ("merged", "Merged"),
            ("ignored", "Ignored"),
            ("not_duplicate", "Not Duplicate"),
        ],
        default="open",
        index=True,
    )
    detection_source = fields.Selection(
        [
            ("manual", "Manual Scan"),
            ("cron", "Scheduled"),
            ("import", "Import"),
            ("api", "API"),
        ],
        default="manual",
    )
    company_id = fields.Many2one(
        "res.company",
        compute="_compute_company_id",
        store=True,
    )

    @api.depends("partner_a_id", "partner_b_id")
    def _compute_company_id(self):
        for record in self:
            record.company_id = (
                record.partner_a_id.company_id
                or record.partner_b_id.company_id
                or self.env.company
            )

    def action_open_merge_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Merge Contacts",
            "res_model": "duplicate.contact.merge.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_pair_id": self.id,
                "default_partner_a_id": self.partner_a_id.id,
                "default_partner_b_id": self.partner_b_id.id,
            },
        }

    def action_ignore(self):
        for record in self:
            low, high = sorted((record.partner_a_id.id, record.partner_b_id.id))
            self.env["duplicate.contact.ignore"].sudo().create({
                "partner_low_id": low,
                "partner_high_id": high,
                "reason": "Ignored from duplicate review",
            })
            record.state = "ignored"

    def action_mark_not_duplicate(self):
        self.write({"state": "not_duplicate"})

    @api.model
    def cron_detect_duplicates(self):
        from ..services.detection import DuplicateDetectionService
        return DuplicateDetectionService(self.env).run_scan(
            limit=int(
                self.env["ir.config_parameter"].sudo().get_param(
                    "duplicate_contact.scan_limit", "2000"
                )
                or 2000
            ),
            source="cron",
        )
