# -*- coding: utf-8 -*-
import logging
import re
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class TwilioSmsTemplateCategory(models.Model):
    _name = "twilio.sms.template.category"
    _description = "Twilio SMS Template Category"
    _order = "name asc"

    name = fields.Char(string="Category Name", required=True)
    description = fields.Text(string="Description")


class TwilioSmsTemplate(models.Model):
    _name = "twilio.sms.template"
    _description = "Twilio SMS Template"
    _order = "sequence asc, name asc"

    name = fields.Char(string="Template Name", required=True)
    category_id = fields.Many2one("twilio.sms.template.category", string="Category")
    body = fields.Text(string="Message Body", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    description = fields.Text(string="Description")

    def render_template(self, partner=None, user=None):
        """Replace placeholders with actual Contact / User data."""
        self.ensure_one()
        text = self.body or ""
        if not text:
            return ""

        partner_name = partner.name if partner else ""
        name_parts = partner_name.strip().split(" ") if partner_name else []
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        phone = partner.phone if partner else ""
        mobile = partner.mobile if partner else ""
        email = partner.email if partner else ""
        company = partner.company_id.name if (partner and partner.company_id) else (partner.parent_id.name if (partner and partner.parent_id) else "")
        job_title = partner.function if partner else ""
        user_name = user.name if user else self.env.user.name
        today_str = fields.Date.today().strftime("%Y-%m-%d")

        placeholders = {
            r"\{\{\s*contact_name\s*\}\}": partner_name,
            r"\{\{\s*first_name\s*\}\}": first_name,
            r"\{\{\s*last_name\s*\}\}": last_name,
            r"\{\{\s*phone\s*\}\}": phone or mobile,
            r"\{\{\s*mobile\s*\}\}": mobile or phone,
            r"\{\{\s*email\s*\}\}": email,
            r"\{\{\s*company\s*\}\}": company,
            r"\{\{\s*job_title\s*\}\}": job_title,
            r"\{\{\s*user\s*\}\}": user_name,
            r"\{\{\s*today\s*\}\}": today_str,
        }

        for pattern, val in placeholders.items():
            text = re.sub(pattern, val or "", text, flags=re.IGNORECASE)

        return text


class TwilioSmsQuickReply(models.Model):
    _name = "twilio.sms.quick.reply"
    _description = "Twilio SMS Quick Reply"
    _order = "sequence asc, name asc"

    name = fields.Char(string="Name / Label", required=True)
    body = fields.Text(string="Message", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
