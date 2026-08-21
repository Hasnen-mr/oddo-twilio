# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TwilioAutoDialerImportHistory(models.Model):
    _name = "twilio.auto.dialer.import.history"
    _description = "Auto Dialer Queue CSV Import History"
    _order = "create_date desc, id desc"

    dialer_id = fields.Many2one(
        "twilio.auto.dialer",
        string="Queue",
        required=True,
        ondelete="cascade",
        index=True,
    )
    file_name = fields.Char(string="File Name", required=True)
    user_id = fields.Many2one(
        "res.users",
        string="Imported By",
        default=lambda self: self.env.user,
        required=True,
    )
    import_date = fields.Datetime(string="Import Date", default=fields.Datetime.now, required=True)
    total_records = fields.Integer(string="Total Records")
    imported_records = fields.Integer(string="Imported Records")
    invalid_records = fields.Integer(string="Invalid Records")
    duplicate_records = fields.Integer(string="Duplicate Records")
    skipped_records = fields.Integer(string="Skipped Records")
    notes = fields.Text(string="Import Summary")


class TwilioAutoDialerImportWizard(models.TransientModel):
    _name = "twilio.auto.dialer.import.wizard"
    _description = "CSV Import Wizard for Auto Dialer Queue"

    dialer_id = fields.Many2one(
        "twilio.auto.dialer",
        string="Target Queue",
        required=True,
    )
    csv_file = fields.Binary(string="CSV File", required=True)
    file_name = fields.Char(string="File Name")
    duplicate_handling = fields.Selection(
        [
            ("skip", "Skip Duplicates"),
            ("replace", "Replace / Update Duplicates"),
        ],
        string="Duplicate Handling",
        default="skip",
        required=True,
    )

    state = fields.Selection(
        [("upload", "Upload"), ("preview", "Preview")],
        default="upload",
    )
    total_rows = fields.Integer(string="Total Rows")
    valid_rows = fields.Integer(string="Valid Rows")
    duplicate_rows = fields.Integer(string="Duplicate Rows")
    invalid_rows = fields.Integer(string="Invalid Rows")
    preview_data = fields.Text(string="Preview Data")

    def _parse_csv_file(self):
        if not self.csv_file:
            raise UserError("Please upload a CSV file.")

        file_content = base64.b64decode(self.csv_file)
        try:
            content_str = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                content_str = file_content.decode("latin1")
            except Exception as e:
                raise UserError("Unable to decode file. Please upload a valid UTF-8 CSV file.") from e

        reader = csv.DictReader(io.StringIO(content_str))
        if not reader.fieldnames:
            raise UserError("CSV file is empty or missing header row.")

        field_map = {name.strip().lower(): name for name in reader.fieldnames if name}

        phone_col = next((field_map[k] for k in field_map if k in ("phone", "mobile", "number", "phone_number", "contact")), None)
        name_col = next((field_map[k] for k in field_map if k in ("name", "full_name", "contact_name", "customer")), None)
        email_col = next((field_map[k] for k in field_map if k in ("email", "email_address")), None)
        company_col = next((field_map[k] for k in field_map if k in ("company", "company_name")), None)
        notes_col = next((field_map[k] for k in field_map if k in ("notes", "note", "comment")), None)

        if not phone_col:
            raise UserError("CSV file must contain a 'Phone' or 'Mobile' column.")

        rows = []
        for row in reader:
            raw_phone = (row.get(phone_col) or "").strip()
            raw_name = (row.get(name_col) or "").strip() if name_col else ""
            raw_email = (row.get(email_col) or "").strip() if email_col else ""
            raw_company = (row.get(company_col) or "").strip() if company_col else ""
            raw_notes = (row.get(notes_col) or "").strip() if notes_col else ""

            if not raw_phone:
                continue

            rows.append({
                "name": raw_name or raw_phone,
                "phone": raw_phone,
                "email": raw_email,
                "company": raw_company,
                "notes": raw_notes,
            })
        return rows

    def action_preview(self):
        self.ensure_one()
        rows = self._parse_csv_file()
        existing_phones = set()

        for line in self.dialer_id.queue_line_ids:
            if line.phone:
                digits = "".join(c for c in line.phone if c.isdigit())
                if digits:
                    existing_phones.add(digits)

        valid = 0
        invalid = 0
        duplicates = 0

        for r in rows:
            digits = "".join(c for c in r["phone"] if c.isdigit())
            if not digits:
                invalid += 1
            elif digits in existing_phones:
                duplicates += 1
            else:
                valid += 1

        self.write({
            "state": "preview",
            "total_rows": len(rows),
            "valid_rows": valid,
            "duplicate_rows": duplicates,
            "invalid_rows": invalid,
            "preview_data": f"Parsed {len(rows)} contact rows from {self.file_name or 'CSV'}.",
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "twilio.auto.dialer.import.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_import(self):
        self.ensure_one()
        rows = self._parse_csv_file()
        dialer = self.dialer_id

        existing_lines = {
            "".join(c for c in line.phone if c.isdigit()): line
            for line in dialer.queue_line_ids if line.phone
        }

        max_seq = max(dialer.queue_line_ids.mapped("sequence") or [0])
        next_seq = max_seq + 10 if max_seq else 10

        imported_count = 0
        duplicate_count = 0
        invalid_count = 0
        skipped_count = 0

        for r in rows:
            raw_phone = r["phone"]
            digits_only = "".join(c for c in raw_phone if c.isdigit())

            if not digits_only:
                invalid_count += 1
                continue

            if raw_phone.startswith("+"):
                phone_formatted = raw_phone
            elif raw_phone.startswith("91") and len(digits_only) >= 12:
                phone_formatted = "+" + raw_phone
            elif raw_phone.startswith("0"):
                phone_formatted = "+91" + raw_phone.lstrip("0")
            else:
                phone_formatted = "+91" + raw_phone

            if digits_only in existing_lines:
                duplicate_count += 1
                if self.duplicate_handling == "replace":
                    line = existing_lines[digits_only]
                    line.write({
                        "phone": phone_formatted,
                        "notes": r["notes"] or line.notes,
                        "status": "pending",
                    })
                    imported_count += 1
                else:
                    skipped_count += 1
                continue

            partner = self.env["res.partner"].search([
                ("phone", "ilike", digits_only)
            ], limit=1)

            if not partner and r["name"]:
                partner = self.env["res.partner"].create({
                    "name": r["name"],
                    "phone": phone_formatted,
                    "email": r["email"] or False,
                })

            self.env["twilio.auto.dialer.line"].create({
                "dialer_id": dialer.id,
                "partner_id": partner.id if partner else False,
                "phone": phone_formatted,
                "sequence": next_seq,
                "status": "pending",
                "attempt_count": 0,
                "notes": r["notes"] or False,
            })
            existing_lines[digits_only] = True
            next_seq += 10
            imported_count += 1

        if imported_count > 0 and dialer.state in ("completed", "cancelled"):
            dialer.write({"state": "draft"})
            if not dialer.current_line_id or dialer.current_line_id.status != "pending":
                next_p = dialer._get_next_pending_line()
                if next_p:
                    dialer.write({"current_line_id": next_p.id})

        self.env["twilio.auto.dialer.import.history"].create({
            "dialer_id": dialer.id,
            "file_name": self.file_name or "imported_contacts.csv",
            "user_id": self.env.user.id,
            "total_records": len(rows),
            "imported_records": imported_count,
            "invalid_records": invalid_count,
            "duplicate_records": duplicate_count,
            "skipped_records": skipped_count,
            "notes": f"Imported {imported_count} record(s), {duplicate_count} duplicate(s), {invalid_count} invalid.",
        })

        return {
            "name": dialer.name,
            "type": "ir.actions.act_window",
            "res_model": "twilio.auto.dialer",
            "res_id": dialer.id,
            "view_mode": "form",
            "target": "current",
        }
