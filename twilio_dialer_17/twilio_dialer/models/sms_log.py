# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from twilio.rest import Client

_logger = logging.getLogger(__name__)


class TwilioSmsLog(models.TransientModel):
    """Virtual/Transient model for SMS Logs.

    SMS records are fetched live from Twilio API and never stored in the database.
    This model provides the standard Odoo list view interface backed by Twilio REST API.
    """
    _name = "twilio.sms.log"
    _description = "Twilio SMS Log"
    _order = "date_sent desc"

    sid = fields.Char(string="Message SID")
    date_sent = fields.Datetime(string="Date")
    partner_id = fields.Many2one("res.partner", string="Contact")
    phone_number = fields.Char(string="Phone Number")
    direction = fields.Selection(
        [
            ("inbound", "Incoming"),
            ("outbound-api", "Outgoing"),
            ("outbound-call", "Outgoing"),
            ("outbound-reply", "Outgoing"),
        ],
        string="Direction",
    )
    status = fields.Selection(
        [
            ("accepted", "Accepted"),
            ("scheduled", "Scheduled"),
            ("queued", "Queued"),
            ("sending", "Sending"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("undelivered", "Undelivered"),
            ("failed", "Failed"),
            ("received", "Received"),
            ("read", "Read"),
        ],
        string="Status",
    )
    body = fields.Text(string="Message Preview")
    to_number = fields.Char(string="To Number")
    from_number = fields.Char(string="From Number")

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Fetch live SMS logs directly from Twilio without storing in DB."""
        domain = domain or []
        try:
            client = self.env["twilio.service"].get_twilio_client()
            messages = client.messages.list(limit=limit or 100)
        except Exception as e:
            _logger.error("Failed to fetch SMS logs from Twilio: %s", str(e))
            return []

        # Find partners matching phone numbers with digit normalization
        all_phone_digits = set()
        for msg in messages:
            for raw_num in (msg.from_, msg.to):
                if raw_num:
                    import re
                    digits = re.sub(r"\D", "", raw_num)
                    if len(digits) >= 10:
                        all_phone_digits.add(digits[-10:])

        partner_map = {}
        if all_phone_digits:
            or_conditions = []
            for d in all_phone_digits:
                or_conditions.extend([("phone", "like", d), ("mobile", "like", d)])
            
            # Combine domain with ORs
            domain_partner = ["|"] * (len(or_conditions) - 1) + or_conditions
            partners = self.env["res.partner"].search(domain_partner)
            for p in partners:
                import re
                if p.phone:
                    digits = re.sub(r"\D", "", p.phone)
                    if len(digits) >= 10:
                        partner_map[digits[-10:]] = (p.id, p.name)
                if p.mobile:
                    digits = re.sub(r"\D", "", p.mobile)
                    if len(digits) >= 10:
                        partner_map[digits[-10:]] = (p.id, p.name)

        result_records = []
        for msg in messages:
            is_inbound = "inbound" in (msg.direction or "")
            contact_phone = msg.from_ if is_inbound else msg.to
            import re
            c_digits = re.sub(r"\D", "", contact_phone or "")[-10:]
            partner_info = partner_map.get(c_digits)

            date_val = msg.date_sent or msg.date_created
            date_str = date_val.strftime("%Y-%m-%d %H:%M:%S") if date_val else False

            record_dict = {
                "id": msg.sid,
                "sid": msg.sid,
                "date_sent": date_str,
                "partner_id": partner_info if partner_info else False,
                "phone_number": contact_phone or "",
                "direction": "inbound" if is_inbound else "outbound-api",
                "status": msg.status or "sent",
                "body": msg.body or "",
                "to_number": msg.to or "",
                "from_number": msg.from_ or "",
            }
            result_records.append(record_dict)

        # Apply basic domain filtering if specified by search/filter bar
        if domain:
            for leaf in domain:
                if isinstance(leaf, (list, tuple)) and len(leaf) == 3:
                    fname, op, val = leaf[0], leaf[1], leaf[2]
                    if fname == "direction" and op == "=":
                        result_records = [r for r in result_records if (
                            r["direction"] == val or
                            (val == "inbound" and r["direction"] == "inbound") or
                            (val == "outbound-api" and r["direction"] != "inbound")
                        )]
                    elif fname == "status" and op == "=":
                        result_records = [r for r in result_records if r["status"] == val]
                    elif fname in ("phone_number", "body", "sid") and op in ("ilike", "="):
                        val_str = str(val).lower()
                        result_records = [r for r in result_records if val_str in str(r.get(fname, "")).lower()]

        if offset:
            result_records = result_records[offset:]
        if limit:
            result_records = result_records[:limit]

        return result_records

    @api.model
    def web_search_read(self, domain=None, specification=None, offset=0, limit=None, order=None, count_limit=None):
        """Odoo 17/18 web client search_read handler."""
        fields_to_read = list(specification.keys()) if specification else None
        records = self.search_read(domain=domain, fields=fields_to_read, offset=offset, limit=limit, order=order)
        length = self.search_count(domain=domain)
        return {
            "records": records,
            "length": length,
        }

    @api.model
    def search_fetch(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Odoo 17/18 search_fetch handler."""
        records = self.search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)
        return self.browse([r["id"] for r in records if "id" in r])

    @api.model
    def search_count(self, domain=None, limit=None):
        """Return count for SMS logs search."""
        records = self.search_read(domain=domain, limit=limit)
        return len(records)
