import base64
import csv
import io
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TwilioAutoDialer(models.Model):
    _name = "twilio.auto.dialer"
    _description = "Auto Dialer Queue"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(string="Queue Name", required=True, tracking=True, default="New Queue")
    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "Running"),
            ("paused", "Paused"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="State",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    def _default_from_number(self):
        return self.env["twilio.service"].get_twilio_phone_number()

    from_number = fields.Char(
        string="From Number",
        default=_default_from_number,
        tracking=True,
        help="Twilio phone number used as Caller ID for this campaign queue.",
    )

    description = fields.Text(string="Description")
    active = fields.Boolean(string="Active", default=True)

    partner_ids = fields.Many2many(
        "res.partner",
        "twilio_auto_dialer_partner_rel",
        "dialer_id",
        "partner_id",
        string="Select Contacts",
        help="Select Odoo contacts to automatically generate Queue Lines.",
    )

    queue_line_ids = fields.One2many(
        "twilio.auto.dialer.line",
        "dialer_id",
        string="Queue Lines",
    )
    import_history_ids = fields.One2many(
        "twilio.auto.dialer.import.history",
        "dialer_id",
        string="Import History",
    )

    total_contacts = fields.Integer(
        string="Total Contacts",
        compute="_compute_statistics",
        store=True,
    )
    completed_contacts = fields.Integer(
        string="Completed",
        compute="_compute_statistics",
        store=True,
    )
    pending_contacts = fields.Integer(
        string="Pending",
        compute="_compute_statistics",
        store=True,
    )
    failed_contacts = fields.Integer(
        string="Failed",
        compute="_compute_statistics",
        store=True,
    )
    calling_contacts = fields.Integer(
        string="Calling",
        compute="_compute_statistics",
        store=True,
    )
    busy_contacts = fields.Integer(
        string="Busy",
        compute="_compute_statistics",
        store=True,
    )
    no_answer_contacts = fields.Integer(
        string="No Answer",
        compute="_compute_statistics",
        store=True,
    )
    skipped_contacts = fields.Integer(
        string="Skipped",
        compute="_compute_statistics",
        store=True,
    )
    progress = fields.Float(
        string="Progress (%)",
        compute="_compute_statistics",
        store=True,
    )

    # Future compatibility / Extensible Campaign Configuration
    call_delay = fields.Integer(
        string="Delay Between Calls (sec)",
        default=5,
        help="Wait time before dialing the next number in sequence.",
    )
    max_ring_time = fields.Integer(
        string="Max Ring Time (sec)",
        default=30,
        help="Maximum duration to ring before moving to next contact.",
    )
    auto_skip_no_answer = fields.Boolean(
        string="Auto Skip No Answer",
        default=True,
        help="Automatically move to next contact if no answer.",
    )
    max_retries = fields.Integer(
        string="Max Retries per Contact",
        default=1,
        help="Number of retry attempts for busy/no-answer contacts.",
    )
    current_line_id = fields.Many2one(
        "twilio.auto.dialer.line",
        string="Active Queue Line",
        ondelete="set null",
        help="Pointer to the line currently being processed by the Auto Dialer.",
    )

    @api.depends("queue_line_ids", "queue_line_ids.status")
    def _compute_statistics(self):
        for record in self:
            lines = record.queue_line_ids
            total = len(lines)
            record.total_contacts = total
            record.pending_contacts = len(lines.filtered(lambda l: l.status == "pending"))
            record.calling_contacts = len(lines.filtered(lambda l: l.status == "calling"))
            completed = len(lines.filtered(lambda l: l.status == "completed"))
            record.completed_contacts = completed
            record.busy_contacts = len(lines.filtered(lambda l: l.status == "busy"))
            record.no_answer_contacts = len(lines.filtered(lambda l: l.status == "no_answer"))
            record.skipped_contacts = len(lines.filtered(lambda l: l.status == "skipped"))
            record.failed_contacts = len(lines.filtered(lambda l: l.status in ("failed", "busy", "no_answer")))
            record.progress = (100.0 * completed / total) if total > 0 else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.partner_ids:
                record._generate_queue_lines(record.partner_ids)
                record.with_context(skip_queue_generation=True).write({"partner_ids": [(5, 0, 0)]})
        return records

    def write(self, vals):
        res = super().write(vals)
        if "partner_ids" in vals and not self.env.context.get("skip_queue_generation"):
            for record in self:
                if record.partner_ids:
                    record._generate_queue_lines(record.partner_ids)
                    record.with_context(skip_queue_generation=True).write({"partner_ids": [(5, 0, 0)]})
        return res

    def _generate_queue_lines(self, partners):
        """
        Private single source of truth for converting partners into twilio.auto.dialer.line records.
        Executes phone normalization, duplicate prevention, sequence assignment, and line creation.
        """
        self.ensure_one()
        if not partners:
            return {"created": 0, "skipped": 0}

        # Existing phone digits set to check duplicates
        existing_phones = set()
        for line in self.queue_line_ids:
            if line.phone:
                clean_existing = "".join(ch for ch in line.phone if ch.isdigit())
                if clean_existing:
                    existing_phones.add(clean_existing)

        max_seq = max(self.queue_line_ids.mapped("sequence") or [0])
        next_seq = max_seq + 10 if max_seq else 10

        created_count = 0
        skipped_count = 0

        for partner in partners:
            raw_phone = partner.mobile or partner.phone or ""
            phone_clean = "".join(ch for ch in raw_phone.strip() if ch.isdigit() or ch == "+")
            digits_only = "".join(ch for ch in raw_phone if ch.isdigit())

            if not phone_clean or not digits_only:
                _logger.info(
                    "Auto Dialer Queue '%s' (ID %s): Skipped Contact '%s' (ID %s) — Empty phone number.",
                    self.name, self.id, partner.name, partner.id
                )
                skipped_count += 1
                continue

            if digits_only in existing_phones:
                _logger.info(
                    "Auto Dialer Queue '%s' (ID %s): Skipped Contact '%s' (ID %s) — Phone '%s' is a duplicate already in queue.",
                    self.name, self.id, partner.name, partner.id, phone_clean
                )
                skipped_count += 1
                continue

            self.env["twilio.auto.dialer.line"].create({
                "dialer_id": self.id,
                "partner_id": partner.id,
                "phone": phone_clean,
                "sequence": next_seq,
                "status": "pending",
                "attempt_count": 0,
            })
            existing_phones.add(digits_only)
            next_seq += 10
            created_count += 1

        if created_count > 0 and self.state in ("completed", "cancelled"):
            self.write({"state": "draft"})
            if not self.current_line_id or self.current_line_id.status != "pending":
                next_p = self._get_next_pending_line()
                if next_p:
                    self.write({"current_line_id": next_p.id})

        _logger.info(
            "Auto Dialer Queue '%s' (ID %s): Added %s contact(s), skipped %s contact(s).",
            self.name, self.id, created_count, skipped_count
        )
        return {"created": created_count, "skipped": skipped_count}

    def action_add_contacts(self, partners):
        """Add selected contacts to the dialing queue by delegating to _generate_queue_lines()."""
        return self._generate_queue_lines(partners)

    def action_add_selected_contacts(self):
        """Button action on form view to convert selected partner_ids into Queue Lines."""
        self.ensure_one()
        if not self.partner_ids:
            raise UserError("Please select at least one Contact from the list before clicking 'Add Selected to Queue'.")

        selected_count = len(self.partner_ids)
        res = self._generate_queue_lines(self.partner_ids)
        added_count = res.get("created", 0)
        skipped_count = res.get("skipped", 0)

        # Clear selection after adding safely via context flag
        self.with_context(skip_queue_generation=True).write({"partner_ids": [(5, 0, 0)]})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Contacts Added to Queue",
                "message": f"Selected: {selected_count} | Added: {added_count} | Already in Queue: {skipped_count}",
                "sticky": False,
                "type": "success",
            },
        }

    def _get_next_pending_line(self, from_line=None):
        self.ensure_one()
        domain = [("dialer_id", "=", self.id), ("status", "=", "pending")]
        if from_line:
            domain.append(("sequence", ">", from_line.sequence))
        line = self.env["twilio.auto.dialer.line"].search(domain, order="sequence asc, id asc", limit=1)
        if not line and from_line:
            line = self.env["twilio.auto.dialer.line"].search([("dialer_id", "=", self.id), ("status", "=", "pending")], order="sequence asc, id asc", limit=1)
        return line

    def _get_prev_line(self, current_line=None):
        self.ensure_one()
        all_lines = self.queue_line_ids
        if not all_lines:
            return self.env["twilio.auto.dialer.line"]
        if not current_line:
            return all_lines[-1]
        idx = list(all_lines).index(current_line) if current_line in all_lines else 0
        return all_lines[idx - 1] if idx > 0 else all_lines[0]

    def _get_next_line(self, current_line=None):
        self.ensure_one()
        all_lines = self.queue_line_ids
        if not all_lines:
            return self.env["twilio.auto.dialer.line"]
        if not current_line:
            return all_lines[0]
        idx = list(all_lines).index(current_line) if current_line in all_lines else -1
        return all_lines[idx + 1] if idx >= 0 and idx + 1 < len(all_lines) else all_lines[-1]

    def action_start(self):
        """Start Queue: draft/paused/cancelled -> running, loads first pending contact into pointer."""
        self.ensure_one()
        if self.state == "cancelled" or self.state == "completed":
            # Restart campaign: Reset all processed queue lines back to pending
            self.queue_line_ids.write({"status": "pending", "attempt_count": 0, "last_call_date": False})
            self.write({"state": "draft", "current_line_id": False})

        # If user selected contacts in partner_ids tab but hasn't clicked 'Add Selected to Queue' yet, convert them automatically!
        if self.partner_ids:
            self._generate_queue_lines(self.partner_ids)
            self.with_context(skip_queue_generation=True).write({"partner_ids": [(5, 0, 0)]})

        if not self.queue_line_ids:
            raise UserError("No contacts in this dialing queue. Please select contacts or import a CSV file first.")

        # Determine the line to dial
        target_line = False

        # 1. Check current line if still pending or retryable (e.g. busy/no_answer/failed)
        if self.current_line_id and self.current_line_id.status in ("pending", "calling", "busy", "no_answer", "failed"):
            target_line = self.current_line_id
            if target_line.status != "pending":
                target_line.write({"status": "pending"})

        # 2. Otherwise find the next pending line
        if not target_line:
            target_line = self._get_next_pending_line(from_line=self.current_line_id)

        # 3. If no pending line found ahead, look for any pending line in the entire queue
        if not target_line:
            pending = self.queue_line_ids.filtered(lambda l: l.status == "pending")
            if pending:
                target_line = pending[0]

        # 4. If all lines were completed/processed, automatically reset all queue contacts back to pending so pressing Start seamlessly restarts the campaign!
        if not target_line:
            self.queue_line_ids.write({"status": "pending", "attempt_count": 0, "last_call_date": False})
            pending = self.queue_line_ids.filtered(lambda l: l.status == "pending")
            if pending:
                target_line = pending[0]
            else:
                self.write({"state": "completed", "current_line_id": False})
                raise UserError("No contacts available in this queue to dial.")

        vals = {
            "state": "running",
            "current_line_id": target_line.id,
        }
        if not self.from_number:
            vals["from_number"] = self.env["twilio.service"].get_twilio_phone_number()

        self.write(vals)
        return self.action_open_current_dialer()

    def action_pause(self):
        """Pause Queue: changes state to paused, keeps current pointer."""
        self.ensure_one()
        self.write({"state": "paused"})
        return True

    def action_resume(self):
        """Resume Queue: changes state to running."""
        self.ensure_one()
        return self.action_start()

    def action_stop(self):
        """Stop Queue: changes state to paused (resumable), preserving pointer and statistics."""
        self.ensure_one()
        self.write({
            "state": "paused",
        })
        return True

    def action_cancel(self):
        """Cancel Queue: permanently abandons the campaign."""
        self.ensure_one()
        self.write({
            "state": "cancelled",
        })
        return True

    def action_next_contact(self):
        """Move pointer to next queue line."""
        self.ensure_one()
        next_line = self._get_next_line(self.current_line_id) or self._get_next_pending_line(self.current_line_id)
        if next_line:
            self.current_line_id = next_line
        return self.action_open_current_dialer()

    def action_prev_contact(self):
        """Move pointer to previous queue line."""
        self.ensure_one()
        prev_line = self._get_prev_line(self.current_line_id)
        if prev_line:
            self.current_line_id = prev_line
        return self.action_open_current_dialer()

    def action_skip_contact(self):
        """Mark current line skipped and move pointer to next pending contact."""
        self.ensure_one()
        if self.current_line_id:
            self.current_line_id.write({"status": "skipped"})
        next_line = self._get_next_pending_line(self.current_line_id)
        if next_line:
            self.current_line_id = next_line
        else:
            pending = self.queue_line_ids.filtered(lambda l: l.status == "pending")
            if pending:
                self.current_line_id = pending[0]
            else:
                self.state = "completed"
                self.current_line_id = False
        return self.action_open_current_dialer()

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            "name": f"Import Contacts into {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "twilio.auto.dialer.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_dialer_id": self.id,
            },
        }

    def action_export_csv(self):
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Sequence", "Contact Name", "Phone Number", "Status", "Attempts", "Last Call Date", "Notes"])
        for line in self.queue_line_ids:
            writer.writerow([
                line.sequence,
                line.partner_id.name if line.partner_id else "",
                line.phone or "",
                line.status or "",
                line.attempt_count or 0,
                line.last_call_date or "",
                line.notes or "",
            ])
        csv_data = output.getvalue().encode("utf-8")
        attachment = self.env["ir.attachment"].create({
            "name": f"{self.name}_contacts.csv",
            "datas": base64.b64encode(csv_data),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "text/csv",
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def action_open_current_dialer(self):
        """Populate current contact into dialer UI."""
        self.ensure_one()
        line = self.current_line_id
        if not line:
            return False
        partner = line.partner_id

        all_lines = self.queue_line_ids
        line_idx = list(all_lines).index(line) + 1 if line in all_lines else 1
        pos_str = f"Line {line_idx} of {len(all_lines)}"

        return {
            "type": "ir.actions.client",
            "tag": "twilio_dialer.open_dialer",
            "params": {
                "phone": line.phone,
                "from_number": self.from_number or "",
                "partner_id": partner.id if partner else False,
                "partner_name": partner.name if partner else line.phone,
                "auto_dialer_id": self.id,
                "queue_line_id": line.id,
                "queue_name": self.name,
                "queue_position": pos_str,
                "queue_attempts": line.attempt_count,
                "queue_notes": line.notes or "",
                "queue_status": line.status,
            },
        }


class TwilioAutoDialerLine(models.Model):
    _name = "twilio.auto.dialer.line"
    _description = "Auto Dialer Queue Line"
    _order = "sequence asc, id asc"

    dialer_id = fields.Many2one(
        "twilio.auto.dialer",
        string="Dialer Queue",
        required=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        index=True,
    )
    name = fields.Char(
        string="Name",
        related="partner_id.name",
        store=True,
        readonly=False,
    )
    phone = fields.Char(
        string="Phone Number",
        required=True,
        index=True,
    )
    mobile = fields.Char(
        string="Mobile",
        related="partner_id.mobile",
        store=True,
        readonly=False,
    )
    email = fields.Char(
        string="Email",
        related="partner_id.email",
        store=True,
        readonly=False,
    )
    company_name = fields.Char(
        string="Company",
        related="partner_id.parent_id.name",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            raw_phone = self.partner_id.mobile or self.partner_id.phone or ""
            if raw_phone:
                digits_only = "".join(c for c in raw_phone if c.isdigit())
                if raw_phone.startswith("+"):
                    self.phone = raw_phone
                elif raw_phone.startswith("91") and len(digits_only) >= 12:
                    self.phone = "+" + raw_phone
                elif raw_phone.startswith("0"):
                    self.phone = "+91" + raw_phone.lstrip("0")
                else:
                    self.phone = "+91" + raw_phone
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("calling", "Calling"),
            ("completed", "Completed"),
            ("busy", "Busy"),
            ("no_answer", "No Answer"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
            ("skipped", "Skipped"),
        ],
        string="Status",
        default="pending",
        required=True,
        index=True,
    )
    attempt_count = fields.Integer(
        string="Attempts",
        default=0,
    )
    call_log_id = fields.Many2one(
        "twilio.call.log",
        string="Call Log",
        ondelete="set null",
    )
    last_call_date = fields.Datetime(
        string="Last Call Date",
    )
    notes = fields.Text(
        string="Notes",
    )
    error_message = fields.Text(
        string="Error Message",
    )

    duration_sec = fields.Integer(
        string="Call Duration (sec)",
        default=0,
    )

    def update_status_from_call(self, status, call_log_id=None, notes=None, error_message=None, duration_sec=0):
        """Update line status based on call lifecycle, update CRM partner, and advance dialer queue pointer."""
        self.ensure_one()
        vals = {}
        if notes:
            vals["notes"] = notes
        if error_message:
            vals["error_message"] = error_message
        if call_log_id:
            vals["call_log_id"] = call_log_id
        if duration_sec:
            vals["duration_sec"] = duration_sec

        norm_status = (status or "").lower().replace("-", "_")
        if norm_status in ("calling", "in_progress", "connecting"):
            vals["status"] = "calling"
            vals["attempt_count"] = self.attempt_count + 1
        elif norm_status == "completed":
            vals["status"] = "completed"
            vals["last_call_date"] = fields.Datetime.now()
        elif norm_status == "busy":
            vals["status"] = "busy"
            vals["last_call_date"] = fields.Datetime.now()
        elif norm_status in ("no_answer", "noanswer"):
            vals["status"] = "no_answer"
            vals["last_call_date"] = fields.Datetime.now()
        elif norm_status in ("failed", "canceled", "cancelled", "rejected"):
            vals["status"] = "failed"
            vals["last_call_date"] = fields.Datetime.now()

        self.write(vals)

        # CRM Synchronization: Update res.partner contact details
        if self.partner_id and vals.get("status") in ("completed", "busy", "no_answer", "failed", "skipped"):
            try:
                partner_vals = {}
                if hasattr(self.partner_id, "twilio_last_call_date"):
                    partner_vals["twilio_last_call_date"] = fields.Datetime.now()
                if hasattr(self.partner_id, "twilio_last_call_status"):
                    partner_vals["twilio_last_call_status"] = vals.get("status")
                if hasattr(self.partner_id, "comment") and not self.partner_id.comment:
                    partner_vals["comment"] = f"Auto Dialer Campaign: {self.dialer_id.name} | Result: {vals.get('status').title()}"
                if partner_vals:
                    self.partner_id.write(partner_vals)
            except Exception as e:
                _logger.warning("Failed to update partner %s from auto dialer line: %s", self.partner_id.id, e)

        # Advance queue pointer if finished calling
        if vals.get("status") in ("completed", "busy", "no_answer", "failed"):
            dialer = self.dialer_id
            if dialer and dialer.state == "running":
                next_line = dialer._get_next_pending_line(self)
                if next_line:
                    dialer.write({"current_line_id": next_line.id})
                else:
                    pending = dialer.queue_line_ids.filtered(lambda l: l.status == "pending")
                    if not pending:
                        dialer.write({"state": "completed", "current_line_id": False})
                    elif pending[0].id != self.id:
                        dialer.write({"current_line_id": pending[0].id})
        return True
