# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class TwilioAutoDialerCampaign(models.Model):
    _name = "twilio.auto.dialer"
    _description = "Auto Calling Setup"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "write_date desc, id desc"

    name = fields.Char(string="Campaign Name", required=True, tracking=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("ready", "Ready"),
            ("running", "Running"),
            ("paused", "Paused"),
            ("done", "Done"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Agent",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    phone_list = fields.Text(
        string="Phone List",
        help="One phone number per line (E.164 preferred, e.g. +15551234567).",
    )
    total_numbers = fields.Integer(
        string="Total Numbers",
        compute="_compute_numbers",
        store=True,
    )
    dialed_count = fields.Integer(string="Dialed", default=0)
    connected_count = fields.Integer(string="Connected", default=0)
    skipped_count = fields.Integer(string="Skipped", default=0)
    current_index = fields.Integer(string="Current Index", default=0)
    current_number = fields.Char(
        string="Current Number",
        compute="_compute_numbers",
        store=True,
    )
    remaining_count = fields.Integer(
        string="Remaining",
        compute="_compute_numbers",
        store=True,
    )
    call_delay = fields.Integer(
        string="Delay Between Calls (sec)",
        default=5,
        help="Wait time before dialing the next number.",
    )
    max_ring_time = fields.Integer(
        string="Max Ring Time (sec)",
        default=30,
    )
    auto_skip_no_answer = fields.Boolean(
        string="Auto Skip No Answer",
        default=True,
    )
    notes = fields.Text(string="Notes")
    call_log_ids = fields.One2many(
        "twilio.call.log",
        "auto_dialer_id",
        string="Call Logs",
    )
    progress = fields.Float(
        string="Progress",
        compute="_compute_numbers",
        store=True,
    )

    @api.depends("phone_list", "current_index", "dialed_count", "total_numbers")
    def _compute_numbers(self):
        for campaign in self:
            numbers = campaign._get_number_list()
            campaign.total_numbers = len(numbers)
            idx = max(campaign.current_index or 0, 0)
            campaign.current_number = numbers[idx] if idx < len(numbers) else False
            campaign.remaining_count = max(len(numbers) - (campaign.dialed_count or 0), 0)
            campaign.progress = (
                (100.0 * campaign.dialed_count / len(numbers)) if numbers else 0.0
            )

    def _get_number_list(self):
        self.ensure_one()
        raw = self.phone_list or ""
        numbers = []
        for line in raw.splitlines():
            number = "".join(ch for ch in line.strip() if ch.isdigit() or ch == "+")
            if number:
                numbers.append(number)
        return numbers

    def action_mark_ready(self):
        for campaign in self:
            if not campaign._get_number_list():
                raise UserError("Add at least one phone number before marking Ready.")
            campaign.state = "ready"
        return True

    def action_start(self):
        for campaign in self:
            numbers = campaign._get_number_list()
            if not numbers:
                raise UserError("Add phone numbers before starting Auto Dialer.")
            if campaign.state == "done":
                campaign.current_index = 0
                campaign.dialed_count = 0
                campaign.connected_count = 0
                campaign.skipped_count = 0
            campaign.state = "running"
            campaign._compute_numbers()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Auto Dialer",
                "message": "Campaign is running. Use the dialer to call the current number, then Next/Skip.",
                "type": "success",
                "sticky": False,
            },
        }

    def action_pause(self):
        self.write({"state": "paused"})
        return True

    def action_reset(self):
        self.write({
            "state": "draft",
            "current_index": 0,
            "dialed_count": 0,
            "connected_count": 0,
            "skipped_count": 0,
        })
        self._compute_numbers()
        return True

    def action_next_number(self):
        for campaign in self:
            numbers = campaign._get_number_list()
            if not numbers:
                raise UserError("No numbers in this campaign.")
            campaign.dialed_count = (campaign.dialed_count or 0) + 1
            next_index = (campaign.current_index or 0) + 1
            if next_index >= len(numbers):
                campaign.current_index = len(numbers)
                campaign.state = "done"
            else:
                campaign.current_index = next_index
                if campaign.state != "running":
                    campaign.state = "running"
            campaign._compute_numbers()
        return True

    def action_skip_number(self):
        for campaign in self:
            campaign.skipped_count = (campaign.skipped_count or 0) + 1
            campaign.action_next_number()
        return True

    def action_open_dialer_hint(self):
        self.ensure_one()
        number = self.current_number or "the next number"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Call next number",
                "message": "Open Twilio Power Dialer and call %s" % number,
                "type": "info",
                "sticky": False,
            },
        }
