# -*- coding: utf-8 -*-
import base64
import csv
import io
from odoo import api, fields, models, _

class TwilioCallLogExportWizard(models.TransientModel):
    _name = "twilio.call.log.export.wizard"
    _description = "Export Call Logs & Contacts"

    export_type = fields.Selection(
        [
            ("csv", "CSV Spreadsheet (.csv)"),
            ("pdf", "HTML / PDF Printable Summary"),
        ],
        string="Export Format",
        default="csv",
        required=True,
    )
    scope = fields.Selection(
        [
            ("all", "All Call Logs (with Contacts)"),
            ("contacts", "Unique Contacts from Call History"),
            ("selected", "Selected Call Logs"),
        ],
        string="Data Scope",
        default="all",
        required=True,
    )
    date_from = fields.Datetime("From Date")
    date_to = fields.Datetime("To Date")

    file_data = fields.Binary("Exported File", readonly=True)
    file_name = fields.Char("File Name", readonly=True)
    state = fields.Selection([("draft", "Draft"), ("done", "Done")], default="draft")

    def action_export(self):
        self.ensure_one()
        domain = []
        if self.date_from:
            domain.append(("start_time", ">=", self.date_from))
        if self.date_to:
            domain.append(("start_time", "<=", self.date_to))

        if self.scope == "selected":
            active_ids = self.env.context.get("active_ids", [])
            if active_ids:
                domain.append(("id", "in", active_ids))

        logs = self.env["twilio.call.log"].search(domain, order="start_time desc")

        if self.export_type == "csv":
            output = io.StringIO()
            writer = csv.writer(output, delimiter=",", quoting=csv.QUOTE_MINIMAL)

            if self.scope == "contacts":
                writer.writerow(["Contact Name", "Phone / Number", "Email", "Company", "Total Calls"])
                seen_contacts = {}
                for log in logs:
                    contact_name = log.partner_id.name if log.partner_id else (log.caller_name or "Unknown")
                    phone = log.to_number if log.direction == "outgoing" else log.from_number
                    email = log.partner_id.email if log.partner_id else ""
                    company = log.partner_id.parent_id.name if (log.partner_id and log.partner_id.parent_id) else ""
                    key = (contact_name, phone)
                    if key not in seen_contacts:
                        seen_contacts[key] = {
                            "name": contact_name,
                            "phone": phone,
                            "email": email,
                            "company": company,
                            "count": 1,
                        }
                    else:
                        seen_contacts[key]["count"] += 1
                for c in seen_contacts.values():
                    writer.writerow([c["name"], c["phone"], c["email"], c["company"], c["count"]])
                filename = "twilio_contacts_export.csv"
            else:
                writer.writerow([
                    "Reference",
                    "Date & Time",
                    "Contact",
                    "Direction",
                    "From Number",
                    "To Number",
                    "Status",
                    "Duration (s)",
                    "Duration",
                    "Agent",
                    "Recording URL",
                    "Summary",
                ])
                for log in logs:
                    writer.writerow([
                        log.name or "",
                        str(log.start_time or ""),
                        log.partner_id.name if log.partner_id else (log.caller_name or ""),
                        log.direction or "",
                        log.from_number or "",
                        log.to_number or "",
                        log.status or "",
                        log.duration or 0,
                        log.duration_display or "",
                        log.user_id.name if log.user_id else "",
                        log.recording_url or "",
                        log.summary or "",
                    ])
                filename = "twilio_call_logs_export.csv"

            csv_bytes = output.getvalue().encode("utf-8-sig")
            attachment = self.env["ir.attachment"].create({
                "name": filename,
                "type": "binary",
                "datas": base64.b64encode(csv_bytes),
                "mimetype": "text/csv",
                "res_model": "twilio.call.log.export.wizard",
                "res_id": self.id,
            })
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachment.id}?download=true",
                "target": "self",
            }
        else:
            # HTML / Printable format
            rows_html = ""
            for log in logs:
                c_name = log.partner_id.name if log.partner_id else (log.caller_name or "—")
                rows_html += f"<tr><td>{log.name or ''}</td><td>{log.start_time or ''}</td><td>{c_name}</td><td>{log.direction or ''}</td><td>{log.from_number or ''}</td><td>{log.to_number or ''}</td><td>{log.status or ''}</td><td>{log.duration_display or ''}</td></tr>"

            html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Twilio Call Logs Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 24px; color: #1e293b; }}
h1 {{ color: #714b67; font-size: 20px; border-bottom: 2px solid #714b67; padding-bottom: 8px; }}
.meta {{ font-size: 12px; color: #64748b; margin-bottom: 16px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 12px; }}
th {{ background: #f8f4f7; color: #5c3c54; text-align: left; padding: 8px 10px; border-bottom: 2px solid #cbd5e1; }}
td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }}
tr:nth-child(even) {{ background: #fafbfc; }}
</style>
</head>
<body onload="window.print()">
<h1>Twilio Call Logs &amp; Contacts Summary</h1>
<div class="meta">Generated: {fields.Datetime.now()} | Total Records: {len(logs)}</div>
<table>
<thead>
<tr><th>Reference</th><th>When</th><th>Contact</th><th>Direction</th><th>From</th><th>To</th><th>Status</th><th>Duration</th></tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</body>
</html>"""
            pdf_bytes = html.encode("utf-8")
            filename = "twilio_call_logs_summary.html"
            attachment = self.env["ir.attachment"].create({
                "name": filename,
                "type": "binary",
                "datas": base64.b64encode(pdf_bytes),
                "mimetype": "text/html",
                "res_model": "twilio.call.log.export.wizard",
                "res_id": self.id,
            })
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachment.id}?download=true",
                "target": "self",
            }
