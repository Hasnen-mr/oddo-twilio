# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DuplicateContactPair(models.Model):
    _name = "duplicate.contact.pair"
    _description = "Duplicate Contact Pair"
    _order = "confidence desc, id desc"

    partner_a_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True)
    partner_b_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True)
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

    @api.constrains("partner_a_id", "partner_b_id")
    def _check_different_partners(self):
        for record in self:
            if (
                record.partner_a_id
                and record.partner_b_id
                and record.partner_a_id.id == record.partner_b_id.id
            ):
                raise ValidationError(
                    "A duplicate pair cannot reference the same contact twice."
                )

    def action_open_merge_wizard(self):
        self.ensure_one()
        if self.partner_a_id.id == self.partner_b_id.id:
            raise ValidationError(
                "This duplicate row is invalid (same contact on both sides). "
                "Mark it as Not Duplicate instead."
            )
        from ..services.action_utils import act_window
        return act_window(
            self.env,
            "duplicate.contact.merge.wizard",
            view_modes="form",
            name="Merge Contacts",
            target="new",
            context={
                "default_pair_id": self.id,
                "default_partner_a_id": self.partner_a_id.id,
                "default_partner_b_id": self.partner_b_id.id,
            },
        )

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
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()
        icp = self.env["ir.config_parameter"].sudo()
        active = ScanLog._get_active_scan()
        if not active and icp.get_param("duplicate_contact.scan_active") == "True":
            log_id = int(icp.get_param("duplicate_contact.scan_log_id") or 0)
            if log_id:
                active = ScanLog.browse(log_id)
        if not active:
            active = ScanLog._start_scan(source="cron")
        return DuplicateDetectionService(self.env).run_scan_batch(
            scan_log=active,
            source="cron",
            max_batches=20,
        )
