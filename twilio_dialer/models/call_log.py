# -*- coding: utf-8 -*-
import logging
import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.addons.phone_validation.tools.phone_validation import phone_format
from odoo.exceptions import UserError
from ..services import CallLogService

_logger = logging.getLogger(__name__)


class TwilioCallLog(models.Model):
    _name = "twilio.call.log"
    _description = "Twilio Call Log"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_time desc, id desc"
    _rec_name = "display_name"

    name = fields.Char(string="Reference", copy=False, index=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        index=True,
        ondelete="set null",
        tracking=True,
    )
    contact_id = fields.Many2one("res.partner", string="Linked Contact")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )
    from_number = fields.Char(string="From Number", required=True, tracking=True)
    to_number = fields.Char(string="To Number", required=True, tracking=True, index=True)
    direction = fields.Selection(
        [
            ("outgoing", "Outgoing"),
            ("incoming", "Incoming"),
        ],
        string="Direction",
        required=True,
        default="outgoing",
        index=True,
        tracking=True,
    )
    call_type = fields.Selection(
        [
            ("sales", "Sales"),
            ("support", "Support"),
            ("follow_up", "Follow-up"),
            ("demo", "Demo"),
            ("other", "Other"),
        ],
        string="Call Type",
        default="sales",
        index=True,
    )
    call_sid = fields.Char(string="Call SID", required=True, index=True, copy=False)
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("initiated", "Initiated"),
            ("ringing", "Ringing"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("busy", "Busy"),
            ("no_answer", "No Answer"),
            ("failed", "Failed"),
            ("canceled", "Canceled"),
            ("rejected", "Rejected"),
            ("missed", "Missed"),
        ],
        string="Status",
        required=True,
        default="initiated",
        index=True,
        tracking=True,
    )
    outcome = fields.Selection(
        [
            ("connected", "Connected"),
            ("voicemail", "Voicemail"),
            ("no_answer", "No Answer"),
            ("busy", "Busy"),
            ("wrong_number", "Wrong Number"),
            ("callback", "Callback Requested"),
            ("not_interested", "Not Interested"),
            ("qualified", "Qualified Lead"),
            ("other", "Other"),
        ],
        string="Outcome",
        index=True,
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Agent",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
    )
    start_time = fields.Datetime(
        string="Start Time",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    end_time = fields.Datetime(string="End Time")
    duration = fields.Integer(string="Duration (sec)", tracking=True)
    duration_display = fields.Char(
        string="Duration",
        compute="_compute_duration_display",
        store=True,
    )
    notes = fields.Text(string="Notes")
    next_action = fields.Text(string="Next Action")
    follow_up_needed = fields.Boolean(string="Follow-up Needed", index=True, tracking=True)
    follow_up_date = fields.Datetime(string="Follow-up Date", index=True)
    recording_sid = fields.Char(string="Recording SID")
    recording_url = fields.Char(string="Recording URL")
    transcript = fields.Text(string="Transcript")
    summary = fields.Text(string="Summary")
    ai_provider = fields.Char(string="AI Provider", readonly=True)

    auto_dialer_id = fields.Many2one(
        "twilio.auto.dialer",
        string="Auto Dialer Campaign",
        index=True,
        ondelete="set null",
    )
    has_recording = fields.Boolean(compute="_compute_flags", store=True)
    has_transcript = fields.Boolean(compute="_compute_flags", store=True)
    has_summary = fields.Boolean(compute="_compute_flags", store=True)
    is_missed = fields.Boolean(compute="_compute_flags", store=True)

    call_count = fields.Integer(string="Count", default=1, help="Used for reporting aggregates.")
    contact_activity_posted = fields.Boolean(copy=False, readonly=True)

    _sql_constraints = [
        ("twilio_call_log_call_sid_unique", "unique(call_sid)", "The Twilio Call SID must be unique."),
    ]

    @api.depends("partner_id", "to_number", "from_number", "direction", "start_time")
    def _compute_display_name(self):
        for log in self:
            contact = log.partner_id.display_name if log.partner_id else False
            number = log.to_number if log.direction == "outgoing" else log.from_number
            when = fields.Datetime.to_string(log.start_time) if log.start_time else ""
            if contact and number:
                log.display_name = "%s (%s)" % (contact, number)
            elif number:
                log.display_name = number
            else:
                log.display_name = log.name or when or "Call"

    @api.depends("duration")
    def _compute_duration_display(self):
        for log in self:
            seconds = log.duration or 0
            minutes, sec = divmod(max(seconds, 0), 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                log.duration_display = "%d:%02d:%02d" % (hours, minutes, sec)
            else:
                log.duration_display = "%d:%02d" % (minutes, sec)

    @api.depends("recording_url", "transcript", "summary", "status")
    def _compute_flags(self):
        missed_statuses = {"busy", "no_answer", "failed", "canceled"}
        for log in self:
            log.has_recording = bool(log.recording_url)
            log.has_transcript = bool(log.transcript)
            log.has_summary = bool(log.summary)
            log.is_missed = log.status in missed_statuses

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("twilio.call.log") or "/"
        return super().create(vals_list)

    def _normalize_phone_number(self, phone_number, partner=False):
        if not phone_number:
            return False

        country = partner.country_id if partner else self.env["res.country"]
        normalized = phone_format(
            phone_number,
            country.code if country else False,
            country.phone_code if country else False,
            force_format="E164",
            raise_exception=False,
        )
        normalized = re.sub(r"[^0-9+]", "", normalized or phone_number)
        if normalized.startswith("00"):
            normalized = f"+{normalized[2:]}"
        return normalized

    def _find_partner_by_phone_number(self, phone_number):
        normalized_number = self._normalize_phone_number(phone_number)
        if not normalized_number:
            return self.env["res.partner"]

        partners = self.env["res.partner"].search(
            [
                ("active", "=", True),
                "|",
                ("phone", "!=", False),
                ("mobile", "!=", False),
            ],
            limit=2000,
        )
        for partner in partners:
            if normalized_number in {
                self._normalize_phone_number(partner.phone, partner),
                self._normalize_phone_number(partner.mobile, partner),
            }:
                return partner
        return self.env["res.partner"]

    def _link_partner_from_to_number(self):
        for call_log in self.filtered(lambda log: not log.partner_id):
            number = call_log.to_number if call_log.direction == "outgoing" else call_log.from_number
            partner = call_log.contact_id or call_log._find_partner_by_phone_number(number)
            if partner:
                call_log.partner_id = partner
                if not call_log.contact_id:
                    call_log.contact_id = partner

    def create_outgoing_call(self, call_sid, to_number, partner_id=False):
        if not call_sid or not to_number:
            raise UserError("Twilio Call SID and destination number are required.")

        call_log = self.search([("call_sid", "=", call_sid)], limit=1)
        if call_log:
            call_log._link_partner_from_to_number()
            return call_log

        from_number = self.env["twilio.service"].get_twilio_phone_number()
        partner = self.env["res.partner"].browse(partner_id).exists() or self._find_partner_by_phone_number(to_number)
        return self.create(
            {
                "partner_id": partner.id,
                "contact_id": partner.id,
                "from_number": from_number,
                "to_number": to_number,
                "direction": "outgoing",
                "call_sid": call_sid,
            }
        )

    def update_call_status(self, call_sid, status):
        if status not in dict(self._fields["status"].selection):
            raise UserError("Invalid Twilio call status.")

        call_log = self.search([("call_sid", "=", call_sid)], limit=1)
        if not call_log:
            raise UserError("Twilio call log was not found.")

        terminal_statuses = {"completed", "busy", "no_answer", "failed", "canceled", "rejected", "missed"}
        if call_log.contact_activity_posted and status in terminal_statuses:
            return call_log

        call_log._link_partner_from_to_number()
        values = {"status": status}
        if status in terminal_statuses and not call_log.end_time:
            end_time = fields.Datetime.now()
            values["end_time"] = end_time
            values["duration"] = int((end_time - call_log.start_time).total_seconds())
        if status == "completed" and not call_log.outcome:
            values["outcome"] = "connected"
        elif status in {"busy", "no_answer", "failed", "canceled"} and not call_log.outcome:
            values["outcome"] = status if status in dict(self._fields["outcome"].selection) else "other"
        call_log.write(values)

        if status in terminal_statuses:
            call_log._post_contact_activity_if_needed()

        if status == "completed":
            call_log._maybe_auto_generate_ai()
        return call_log

    def _post_contact_activity_if_needed(self):
        try:
            return CallLogService().post_call_activity(self)
        except Exception:
            _logger.exception(
                "Unable to post Contact chatter activity for Twilio Call SID %s",
                self.call_sid,
            )
            return False

    def _maybe_auto_generate_ai(self):
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("twilio_dialer.ai_auto_on_complete") not in ("True", "true", "1"):
            return
        ai = self.env["twilio.ai.service"]
        for call_log in self:
            try:
                if ai.is_transcript_enabled() and not call_log.transcript:
                    call_log.action_create_transcript()
                if ai.is_summary_enabled() and not call_log.summary:
                    call_log.action_create_summary()
            except UserError:
                continue

    def action_create_transcript(self):
        ai = self.env["twilio.ai.service"]
        for call_log in self:
            transcript = ai.create_transcript(call_log)
            call_log.write({
                "transcript": transcript,
                "ai_provider": ai.get_provider(),
            })
            call_log.message_post(body="Transcript generated.", subtype_xmlid="mail.mt_note")
        return True

    def action_create_summary(self):
        ai = self.env["twilio.ai.service"]
        for call_log in self:
            summary = ai.create_summary(call_log)
            call_log.write({
                "summary": summary,
                "ai_provider": ai.get_provider(),
            })
            call_log.message_post(body="Summary generated.", subtype_xmlid="mail.mt_note")
        return True

    def action_open_partner(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError("No contact is linked to this call.")
        return {
            "type": "ir.actions.act_window",
            "name": "Contact",
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.partner_id.id,
            "target": "current",
        }

    def action_mark_follow_up(self):
        for call_log in self:
            call_log.follow_up_needed = True
            if not call_log.follow_up_date:
                call_log.follow_up_date = fields.Datetime.now() + timedelta(days=1)
            call_log.activity_schedule(
                "mail.mail_activity_data_call",
                date_deadline=(call_log.follow_up_date or fields.Datetime.now()).date(),
                summary="Follow up call: %s" % (call_log.display_name,),
                user_id=call_log.user_id.id,
            )
        return True

    def action_post_summary_to_contact(self):
        for call_log in self:
            if not call_log.partner_id:
                raise UserError("Link a contact before posting to the contact chatter.")
            body_parts = []
            if call_log.summary:
                body_parts.append("<b>Call summary</b><br/>%s" % call_log.summary.replace("\n", "<br/>"))
            if call_log.notes:
                body_parts.append("<b>Notes</b><br/>%s" % call_log.notes.replace("\n", "<br/>"))
            if call_log.next_action:
                body_parts.append("<b>Next action</b><br/>%s" % call_log.next_action.replace("\n", "<br/>"))
            if not body_parts:
                raise UserError("Add a summary, notes, or next action first.")
            call_log.partner_id.message_post(
                body="<br/><br/>".join(body_parts),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def action_redial(self):
        self.ensure_one()
        number = self.to_number if self.direction == "outgoing" else self.from_number
        if not number:
            raise UserError("No phone number available to redial.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Redial",
                "message": "Open the Twilio dialer and call %s" % number,
                "type": "info",
                "sticky": False,
            },
        }

    def action_open_recording(self):
        self.ensure_one()
        if not self.recording_url:
            raise UserError("No recording URL is available for this call.")
        return {
            "type": "ir.actions.act_url",
            "url": self.recording_url,
            "target": "new",
        }
