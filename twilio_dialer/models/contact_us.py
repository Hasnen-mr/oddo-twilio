# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from ..services import ZantaTechAPI, ZantaTechAPIError

_logger = logging.getLogger(__name__)


class TwilioContactUs(models.TransientModel):
    _name = "twilio.contact.us"
    _description = "About Us"

    about_section = fields.Selection(
        selection=[
            ("overview", "About Module"),
            ("help", "Help"),
            ("terms", "Terms & Privacy"),
        ],
        string="Section",
        default="overview",
        required=True,
    )
    about_nav = fields.Char(default="1")

    help_email = fields.Char(string="Email")
    help_phone = fields.Char(string="Phone")
    help_use_case = fields.Char(
        string="Use Case",
        default="Sales outbound calling from Odoo",
    )
    help_message = fields.Text(string="Message")
    help_account_sid = fields.Char(string="Account SID", readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        user = self.env.user
        partner = user.partner_id
        icp = self.env["ir.config_parameter"].sudo()
        contact_email = icp.get_param("twilio_dialer.contact_email") or ""
        contact_phone = icp.get_param("twilio_dialer.contact_phone") or ""
        if "help_email" in fields_list:
            values["help_email"] = contact_email or user.email or partner.email or ""
        if "help_phone" in fields_list:
            values["help_phone"] = contact_phone or partner.phone or partner.mobile or ""
        if "help_account_sid" in fields_list:
            values["help_account_sid"] = icp.get_param("twilio_dialer.account_sid") or ""
        if "about_section" in fields_list:
            values["about_section"] = self.env.context.get(
                "twilio_about_section",
                "overview",
            )
        return values

    @api.model
    def action_open_contact_us(self, section=None):
        """Open the About Us page with optional sidebar section."""
        section = section or self.env.context.get("twilio_about_section") or "overview"
        wizard = self.create({"about_section": section})
        return {
            "type": "ir.actions.act_window",
            "name": "About Us",
            "res_model": "twilio.contact.us",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "current",
            "context": {"twilio_about_section": section},
        }

    def action_submit_help(self):
        self.ensure_one()
        email = (self.help_email or "").strip()
        message = (self.help_message or "").strip()
        if not email:
            raise UserError("Please enter your email address.")
        if not message:
            raise UserError("Please describe your issue or question.")

        account_sid = (
            self.help_account_sid
            or self.env["ir.config_parameter"].sudo().get_param("twilio_dialer.account_sid")
            or ""
        )
        payload = {
            "accountSid": account_sid,
            "email": email,
            "phone": (self.help_phone or "").strip(),
            "useCase": (self.help_use_case or "").strip()
            or "Sales outbound calling from Odoo",
            "message": message,
            "title": "Odoo Help",
        }
        try:
            ZantaTechAPI().submit_feedback(payload)
        except ZantaTechAPIError as error:
            raise UserError(str(error)) from error

        self.help_message = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Help",
                "message": "Your issue was submitted successfully. We will get back to you soon.",
                "type": "success",
                "sticky": False,
                "next": self.action_open_contact_us(section="help"),
            },
        }
