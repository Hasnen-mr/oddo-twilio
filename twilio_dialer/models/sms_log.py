# -*- coding: utf-8 -*-
import logging
import re
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
                or_conditions.append(("phone", "like", d))
            
            # Combine domain with ORs
            domain_partner = ["|"] * (len(or_conditions) - 1) + or_conditions if len(or_conditions) > 1 else or_conditions
            partners = self.env["res.partner"].search(domain_partner)
            for p in partners:
                import re
                if p.phone:
                    digits = re.sub(r"\D", "", p.phone)
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

        # Apply domain filtering
        if domain:
            filtered_records = []
            for record in result_records:
                matches_domain = True
                for leaf in domain:
                    if not isinstance(leaf, (list, tuple)) or len(leaf) != 3:
                        continue
                    fname, op, val = leaf[0], leaf[1], leaf[2]
                    if not val:
                        continue
                    if fname == "partner_id":
                        p_info = record.get("partner_id")
                        p_id = p_info[0] if isinstance(p_info, (list, tuple)) and p_info else p_info
                        if op == "=" and str(p_id) != str(val):
                            matches_domain = False
                            break
                    elif fname == "direction":
                        if op == "=":
                            if val == "inbound" and record["direction"] != "inbound":
                                matches_domain = False
                                break
                            elif val in ("outbound-api", "outbound") and record["direction"] == "inbound":
                                matches_domain = False
                                break
                    elif fname == "status":
                        if op == "=" and record["status"] != val:
                            matches_domain = False
                            break
                    elif fname in ("to_number", "from_number", "phone_number"):
                        val_digits = re.sub(r"\D", "", str(val))
                        match_part = val_digits[-10:] if len(val_digits) >= 10 else val_digits
                        to_digits = re.sub(r"\D", "", str(record.get("to_number", "")))
                        from_digits = re.sub(r"\D", "", str(record.get("from_number", "")))
                        phone_digits = re.sub(r"\D", "", str(record.get("phone_number", "")))
                        if match_part not in to_digits and match_part not in from_digits and match_part not in phone_digits:
                            matches_domain = False
                            break
                    elif fname in ("body", "sid"):
                        if str(val).lower() not in str(record.get(fname, "")).lower():
                            matches_domain = False
                            break
                if matches_domain:
                    filtered_records.append(record)
            result_records = filtered_records

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
