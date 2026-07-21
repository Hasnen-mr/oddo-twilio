# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DuplicateContactDashboard(models.TransientModel):
    _name = "duplicate.contact.dashboard"
    _description = "Duplicate Contact Dashboard"

    total_contacts = fields.Integer(readonly=True)
    duplicates_found = fields.Integer(readonly=True)
    need_review = fields.Integer(readonly=True)
    merged_count = fields.Integer(readonly=True)
    ignored_count = fields.Integer(readonly=True)

    @api.model
    def _dashboard_values(self):
        Partner = self.env["res.partner"].sudo()
        Pair = self.env["duplicate.contact.pair"].sudo()
        History = self.env["duplicate.contact.merge.history"].sudo()
        return {
            "total_contacts": Partner.search_count([("active", "=", True)]),
            "duplicates_found": Pair.search_count([
                ("state", "in", ("open", "review")),
            ]),
            "need_review": Pair.search_count([("state", "=", "review")]),
            "merged_count": History.search_count([]),
            "ignored_count": Pair.search_count([("state", "=", "ignored")]),
        }

    @api.model
    def action_open_dashboard(self):
        dashboard = self.create(self._dashboard_values())
        return {
            "type": "ir.actions.act_window",
            "name": "Duplicate Contact Manager",
            "res_model": self._name,
            "res_id": dashboard.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_run_scan(self):
        from ..services.detection import DuplicateDetectionService
        DuplicateDetectionService(self.env).run_scan(source="manual")
        self.write(self._dashboard_values())
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_duplicates(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Duplicate Review",
            "res_model": "duplicate.contact.pair",
            "view_mode": "list,form",
            "domain": [("state", "in", ("open", "review"))],
        }

    def action_open_review(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Need Review",
            "res_model": "duplicate.contact.pair",
            "view_mode": "list,form",
            "domain": [("state", "=", "review")],
        }

    def action_open_merged(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Merge History",
            "res_model": "duplicate.contact.merge.history",
            "view_mode": "list",
        }
