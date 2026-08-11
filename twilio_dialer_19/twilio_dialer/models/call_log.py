# -*- coding: utf-8 -*-
import logging
import re
import threading
import time
from datetime import timedelta

import odoo
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
    recording_duration = fields.Integer(string="Recording Duration (sec)")
    playback_url = fields.Char(
        string="Play Recording",
        compute="_compute_playback_url",
    )
    recording_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("recording", "Recording"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("absent", "Not Available"),
        ],
        string="Recording Status",
    )
    transcript = fields.Text(string="Transcript")
    transcript_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("absent", "Not Available"),
        ],
        string="Transcript Status",
        default="pending",
    )
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
    recording_chatter_posted = fields.Boolean(copy=False, readonly=True)
    chatter_message_id = fields.Many2one(
        "mail.message", string="Chatter Message", copy=False, ondelete="set null"
    )
    contact_message_id = fields.Many2one(
        "mail.message", string="Contact Chatter Message", copy=False, ondelete="set null"
    )

    _twilio_call_log_call_sid_unique = models.Constraint(
        "unique(call_sid)",
        "The Twilio Call SID must be unique.",
    )

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

    @api.depends("recording_url", "recording_status", "transcript", "summary", "status")
    def _compute_flags(self):
        missed_statuses = {"busy", "no_answer", "failed", "canceled"}
        for log in self:
            log.has_recording = bool(log.recording_url)
            log.has_transcript = bool(log.transcript)
            log.has_summary = bool(log.summary)
            log.is_missed = log.status in missed_statuses

    @api.depends("recording_sid")
    def _compute_playback_url(self):
        for log in self:
            if log.recording_sid:
                log.playback_url = "/twilio_dialer/recording/%d" % log.id
            else:
                log.playback_url = ""

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
                ("phone", "!=", False),
            ],
            limit=2000,
        )
        for partner in partners:
            if normalized_number == self._normalize_phone_number(partner.phone, partner):
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

    def create_incoming_call(self, call_sid, from_number, to_number):
        """Create or return an existing incoming call log for an inbound Twilio call.

        Creates the record before answering so the call is tracked and workers can
        operate using the Call SID.
        """
        if not call_sid or not from_number or not to_number:
            raise UserError("Twilio Call SID, from number and to number are required.")

        call_log = self.search([("call_sid", "=", call_sid)], limit=1)
        if call_log:
            call_log._link_partner_from_to_number()
            return call_log

        partner = self._find_partner_by_phone_number(from_number)
        return self.create(
            {
                "partner_id": partner.id,
                "contact_id": partner.id,
                "from_number": from_number,
                "to_number": to_number,
                "direction": "incoming",
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
            call_log._sync_recording_from_twilio()

        if status == "completed":
            call_log._maybe_auto_generate_ai()
        return call_log

    def _sync_chatter_activity(self):
        """Post or update the single consolidated chatter activity card on both Call Log and Contact chatter."""
        service = CallLogService()
        for log in self:
            body = service.format_call_activity(log)

            # 1. Single Chatter Message on Call Log
            try:
                if log.chatter_message_id and log.chatter_message_id.exists():
                    log.chatter_message_id.sudo().write({"body": body})
                else:
                    msg = log.message_post(
                        body=body,
                        subtype_xmlid="mail.mt_note",
                    )
                    log.sudo().write({"chatter_message_id": msg.id})
            except Exception:
                _logger.exception("Failed to sync chatter activity on call_log=%s", log.id)

            # 2. Single Chatter Message on Contact (if linked)
            contact = log.partner_id or log.contact_id
            if contact:
                try:
                    if log.contact_message_id and log.contact_message_id.exists():
                        log.contact_message_id.sudo().write({"body": body})
                    else:
                        msg = contact.message_post(
                            body=body,
                            subtype_xmlid="mail.mt_note",
                        )
                        log.sudo().write({
                            "contact_message_id": msg.id,
                            "contact_activity_posted": True,
                        })
                except Exception:
                    _logger.exception("Failed to sync chatter activity on contact for call_log=%s", log.id)

    def _post_contact_activity_if_needed(self):
        return self._sync_chatter_activity()

    def _post_recording_to_chatter(self):
        return self._sync_chatter_activity()

    @staticmethod
    def _build_recording_url(account_sid, recording_sid):
        if not account_sid or not recording_sid:
            return ""
        return (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{account_sid}/Recordings/{recording_sid}.wav"
        )

    def _sync_recording_from_twilio(self):
        for call_log in self:
            if call_log.recording_sid:
                _logger.info(
                    "Recording sync skipped for %s — already has recording_sid=%s",
                    call_log.call_sid, call_log.recording_sid,
                )
                continue
            _logger.info(
                "Recording sync starting background thread for call_log=%s call_sid=%s",
                call_log.id, call_log.call_sid,
            )
            db_name = self.env.cr.dbname
            uid = self.env.uid
            thread = threading.Thread(
                target=TwilioCallLog._sync_recording_worker,
                args=(call_log.id, db_name, uid),
                daemon=True,
            )
            thread.start()

    @staticmethod
    def _sync_recording_worker(call_log_id, db_name, uid):
        MAX_RETRIES = 5
        RETRY_INTERVAL = 5

        _logger.info(
            "Recording worker started for call_log=%s (db=%s, uid=%s)",
            call_log_id, db_name, uid,
        )

        for attempt in range(MAX_RETRIES):
            time.sleep(RETRY_INTERVAL if attempt > 0 else 5)

            try:
                with odoo.registry(db_name).cursor() as cr:
                    env = odoo.api.Environment(cr, uid, {})
                    # Row-level PostgreSQL lock to prevent concurrent worker execution
                    cr.execute("SELECT id FROM twilio_call_log WHERE id = %s FOR UPDATE", (call_log_id,))
                    log = env["twilio.call.log"].browse(call_log_id)

                    if log.recording_sid and log.recording_url:
                        _logger.info(
                            "Recording sync attempt %d/%d: call_log=%s already has recording_sid=%s and recording_url, stopping",
                            attempt + 1, MAX_RETRIES, call_log_id, log.recording_sid,
                        )
                        return

                    _logger.info(
                        "Recording sync attempt %d/%d: fetching recordings for call_sid=%s",
                        attempt + 1, MAX_RETRIES, log.call_sid,
                    )
                    recordings = env["twilio.service"].fetch_recordings_by_call_sid(
                        log.call_sid
                    )
                    _logger.info(
                        "Recording sync attempt %d/%d: got %d recording(s) for call_sid=%s",
                        attempt + 1, MAX_RETRIES, len(recordings), log.call_sid,
                    )
                    if recordings:
                        log._save_recording_from_twilio(recordings[0])
                        cr.commit()
                        _logger.info(
                            "Recording sync attempt %d/%d: saved recording for call_log=%s call_sid=%s",
                            attempt + 1, MAX_RETRIES, call_log_id, log.call_sid,
                        )
                        return
            except Exception:
                _logger.exception(
                    "Recording sync attempt %d/%d failed for call log %s",
                    attempt + 1,
                    MAX_RETRIES,
                    call_log_id,
                )

        _logger.info(
            "Recording sync exhausted %d retries for call_log=%s, marking absent",
            MAX_RETRIES, call_log_id,
        )
        try:
            with odoo.registry(db_name).cursor() as cr:
                env = odoo.api.Environment(cr, uid, {})
                cr.execute("SELECT id FROM twilio_call_log WHERE id = %s FOR UPDATE", (call_log_id,))
                log = env["twilio.call.log"].browse(call_log_id)
                if log.exists() and not log.recording_sid:
                    log.sudo().write({"recording_status": "absent"})
                    cr.commit()
                    _logger.info(
                        "Recording marked absent for call_log=%s call_sid=%s",
                        call_log_id, log.call_sid,
                    )
        except Exception:
            _logger.exception(
                "Failed to mark recording as absent for call log %s", call_log_id
            )

    def _save_recording_from_twilio(self, recording):
        for log in self:
            try:
                self.env.cr.execute("SELECT id FROM twilio_call_log WHERE id = %s FOR UPDATE", (log.id,))
                log.invalidate_recordset(["recording_status", "recording_url"])
            except Exception:
                pass

            if log.recording_status == "completed" and log.recording_url:
                _logger.info("Recording already saved and completed for call_log=%s, skipping duplicate save", log.id)
                continue

            icp = self.env["ir.config_parameter"].sudo()
            account_sid = icp.get_param("twilio_dialer.account_sid")

            sid = getattr(recording, "sid", "") or ""
            status_raw = (getattr(recording, "status", "") or "").lower()
            duration_raw = getattr(recording, "duration", None)

            status_map = {
                "completed": "completed",
                "failed": "failed",
                "in-progress": "recording",
                "processing": "pending",
            }
            mapped_status = status_map.get(status_raw, "completed")

            duration = 0
            if duration_raw is not None:
                try:
                    duration = int(duration_raw)
                except (TypeError, ValueError):
                    pass

            url = self._build_recording_url(account_sid, sid)

            values = {
                "recording_sid": sid,
                "recording_url": url,
                "recording_duration": duration,
                "recording_status": mapped_status,
            }
            _logger.info(
                "Saving recording for call_log=%s: sid=%s status=%s duration=%s",
                log.id, sid, mapped_status, duration,
            )
            log.sudo().write(values)

            _logger.info(
                "Recording saved for call_log=%s: playback_url=%s",
                log.id, log.playback_url,
            )

            try:
                log._post_recording_to_chatter()
            except Exception:
                _logger.exception(
                    "Chatter posting failed for call_log=%s but recording is saved", log.id,
                )

            # Start transcript worker after recording is saved
            icp = self.env["ir.config_parameter"].sudo()
            ai_flag_raw = icp.get_param("twilio_dialer.ai_enable_transcript")
            condition_eval = ai_flag_raw in ("True", "true", "1")
            if condition_eval:
                _logger.info(
                    "Starting transcript worker for call_log=%s call_sid=%s",
                    log.id, log.call_sid,
                )
                log._sync_transcript_from_twilio()

    def _post_recording_to_chatter(self):
        return self._sync_chatter_activity()

    def _sync_transcript_from_twilio(self):
        for call_log in self:
            if call_log.transcript:
                _logger.info(
                    "Transcript sync skipped for %s — already has transcript",
                    call_log.call_sid,
                )
                continue
            if call_log.transcript_status in ("completed", "failed"):
                _logger.info(
                    "Transcript sync skipped for %s — status is %s",
                    call_log.call_sid, call_log.transcript_status,
                )
                continue
            _logger.info(
                "Transcript sync starting background thread for call_log=%s call_sid=%s",
                call_log.id, call_log.call_sid,
            )
            db_name = self.env.cr.dbname
            uid = self.env.uid
            thread = threading.Thread(
                target=TwilioCallLog._sync_transcript_worker,
                args=(call_log.id, db_name, uid),
                daemon=True,
            )
            thread.start()

    @staticmethod
    def _sync_transcript_worker(call_log_id, db_name, uid):
        MAX_RETRIES = 5
        RETRY_INTERVAL = 3

        _logger.info(
            "Transcript worker started for call_log=%s (db=%s, uid=%s)",
            call_log_id, db_name, uid,
        )

        for attempt in range(MAX_RETRIES):
            time.sleep(RETRY_INTERVAL if attempt > 0 else 2)

            try:
                with odoo.registry(db_name).cursor() as cr:
                    env = odoo.api.Environment(cr, uid, {})
                    cr.execute("SELECT id FROM twilio_call_log WHERE id = %s FOR UPDATE", (call_log_id,))
                    log = env["twilio.call.log"].browse(call_log_id)

                    if log.transcript or log.transcript_status == "completed":
                        _logger.info(
                            "Transcript sync attempt %d/%d: call_log=%s already has transcript, stopping",
                            attempt + 1, MAX_RETRIES, call_log_id,
                        )
                        return

                    if not log.recording_sid:
                        _logger.info(
                            "Transcript sync attempt %d/%d: call_log=%s recording_sid missing, fetching recordings for call_sid=%s",
                            attempt + 1, MAX_RETRIES, call_log_id, log.call_sid,
                        )
                        try:
                            recordings = env["twilio.service"].fetch_recordings_by_call_sid(log.call_sid)
                            if recordings:
                                log._save_recording_from_twilio(recordings[0])
                                cr.commit()
                        except Exception:
                            _logger.exception("Failed to fetch recordings by call_sid=%s during transcript sync", log.call_sid)

                    if not log.recording_sid:
                        _logger.info(
                            "Transcript sync attempt %d/%d: call_log=%s recording_sid not ready yet",
                            attempt + 1, MAX_RETRIES, call_log_id,
                        )
                        continue

                    # Update status to processing
                    log.sudo().write({"transcript_status": "processing"})
                    cr.commit()

                    _logger.info(
                        "Transcript sync attempt %d/%d: generating OpenAI transcript for call_log=%s recording_sid=%s",
                        attempt + 1, MAX_RETRIES, call_log_id, log.recording_sid,
                    )
                    transcript_text = env["twilio.ai.service"].transcribe_recording(log)
                    log._save_transcript_from_openai(transcript_text)
                    cr.commit()
                    _logger.info(
                        "Transcript sync attempt %d/%d: saved OpenAI transcript for call_log=%s",
                        attempt + 1, MAX_RETRIES, call_log_id,
                    )
                    return
            except Exception:
                _logger.exception(
                    "Transcript sync attempt %d/%d failed for call log %s",
                    attempt + 1,
                    MAX_RETRIES,
                    call_log_id,
                )

        _logger.info(
            "Transcript sync exhausted %d retries for call_log=%s, marking failed",
            MAX_RETRIES, call_log_id,
        )
        try:
            with odoo.registry(db_name).cursor() as cr:
                env = odoo.api.Environment(cr, uid, {})
                log = env["twilio.call.log"].browse(call_log_id)
                if log.exists() and not log.transcript and log.transcript_status != "completed":
                    log.sudo().write({"transcript_status": "failed"})
                    cr.commit()
                    _logger.info(
                        "Transcript marked failed for call_log=%s call_sid=%s",
                        call_log_id, log.call_sid,
                    )
        except Exception:
            _logger.exception(
                "Failed to mark transcript as failed for call log %s", call_log_id
            )

    def _save_transcript_from_openai(self, transcript_text):
        for log in self:
            values = {
                "transcript": transcript_text,
                "transcript_status": "completed",
                "ai_provider": "openai",
            }
            _logger.info(
                "Saving OpenAI transcript for call_log=%s: text_length=%d",
                log.id, len(transcript_text or ""),
            )
            log.sudo().write(values)

            # Update single consolidated chatter activity card
            try:
                log._sync_chatter_activity()
            except Exception:
                _logger.exception("Failed to sync chatter activity after saving transcript for call_log=%s", log.id)

            # Auto-generate summary if enabled and doesn't exist
            icp = self.env["ir.config_parameter"].sudo()
            auto_complete = icp.get_param("twilio_dialer.ai_auto_on_complete") in ("True", "true", "1")
            ai = self.env["twilio.ai.service"]
            if auto_complete and ai.is_summary_enabled() and not log.summary:
                try:
                    _logger.info(
                        "Auto-generating summary for call_log=%s after transcript saved",
                        log.id,
                    )
                    log.action_create_summary()
                except UserError:
                    _logger.exception("Summary generation failed for call_log=%s", log.id)

    def _post_transcript_to_chatter(self):
        return self._sync_chatter_activity()

    def _maybe_auto_generate_ai(self):
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("twilio_dialer.ai_auto_on_complete") not in ("True", "true", "1"):
            return
        for call_log in self:
            try:
                # Start transcript worker if enabled and transcript not yet available
                if icp.get_param("twilio_dialer.ai_enable_transcript") in ("True", "true", "1"):
                    if not call_log.transcript and call_log.transcript_status not in ("completed", "failed"):
                        _logger.info(
                            "Auto-triggering transcript worker for call_log=%s",
                            call_log.id,
                        )
                        call_log._sync_transcript_from_twilio()
            except UserError:
                _logger.exception("Auto-generate AI failed for call_log=%s", call_log.id)

    def action_create_transcript(self):
        """Manually trigger OpenAI Whisper transcription for this call log."""
        ai = self.env["twilio.ai.service"]
        if not ai.is_transcript_enabled():
            raise UserError("Enable Create Call Transcripts under Twilio Power Dialer → Configuration → AI Settings.")

        for call_log in self:
            if call_log.transcript and call_log.transcript_status == "completed":
                raise UserError(
                    f"Transcript already exists for this call. "
                    f"Length: {len(call_log.transcript)} characters."
                )

            # Auto-fetch recording SID if not already saved
            if not call_log.recording_sid:
                _logger.info("action_create_transcript: fetching recordings for call_sid=%s", call_log.call_sid)
                try:
                    recordings = self.env["twilio.service"].fetch_recordings_by_call_sid(call_log.call_sid)
                    if recordings:
                        call_log._save_recording_from_twilio(recordings[0])
                except Exception as e:
                    _logger.exception("Failed to auto-fetch recording for call_sid=%s: %s", call_log.call_sid, e)

            if not call_log.recording_sid:
                raise UserError(
                    "No recording is available for this call in Twilio yet. "
                    "Please verify that call recording was enabled or try again in a few seconds."
                )

            call_log.write({"transcript_status": "processing"})
            call_log._sync_chatter_activity()
            try:
                transcript_text = ai.transcribe_recording(call_log)
                call_log._save_transcript_from_openai(transcript_text)
            except Exception as e:
                call_log.write({"transcript_status": "failed"})
                call_log._sync_chatter_activity()
                raise UserError(f"OpenAI Whisper transcription failed:\n{str(e)}")

        return True

    def action_create_summary(self):
        ai = self.env["twilio.ai.service"]
        if not ai.is_summary_enabled():
            raise UserError("Enable Create Call Summaries under Twilio Power Dialer → Configuration → AI Settings.")

        for call_log in self:
            summary = ai.create_summary(call_log)
            call_log.write({
                "summary": summary,
                "ai_provider": ai.get_provider(),
            })
            call_log._sync_chatter_activity()
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
        if not self.playback_url:
            raise UserError("No recording is available for this call.")
        return {
            "type": "ir.actions.act_url",
            "url": self.playback_url,
            "target": "new",
        }
