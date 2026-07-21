# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SUPPORT_EMAIL = "developer.lifetips@gmail.com"


class DuplicateContactAbout(models.TransientModel):
    _name = "duplicate.contact.about"
    _description = "About Us"

    about_section = fields.Selection(
        selection=[
            ("overview", "About Module"),
            ("how_it_works", "How It Works"),
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
        default="Duplicate contact cleanup after CRM import",
    )
    help_message = fields.Text(string="Message")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        user = self.env.user
        partner = user.partner_id
        if "help_email" in fields_list:
            values["help_email"] = user.email or partner.email or ""
        if "help_phone" in fields_list:
            values["help_phone"] = partner.phone or partner.mobile or ""
        if "about_section" in fields_list:
            values["about_section"] = self.env.context.get(
                "duplicate_about_section",
                "overview",
            )
        return values

    @api.model
    def action_open_about_us(self, section=None):
        section = section or self.env.context.get("duplicate_about_section") or "overview"
        wizard = self.create({"about_section": section})
        from ..services.action_utils import act_window
        return act_window(
            self.env,
            self._name,
            view_modes="form",
            name="About Us",
            res_id=wizard.id,
            context={"duplicate_about_section": section},
        )

    def action_submit_help(self):
        self.ensure_one()
        email = (self.help_email or "").strip()
        message = (self.help_message or "").strip()
        if not email:
            raise UserError("Please enter your email address.")
        if not message:
            raise UserError("Please describe your issue or question.")

        body = (
            "<p><strong>Duplicate Contact Manager — Help request</strong></p>"
            "<ul>"
            "<li><strong>Email:</strong> %s</li>"
            "<li><strong>Phone:</strong> %s</li>"
            "<li><strong>Use case:</strong> %s</li>"
            "</ul>"
            "<p>%s</p>"
        ) % (
            email,
            (self.help_phone or "").strip() or "—",
            (self.help_use_case or "").strip() or "—",
            message.replace("\n", "<br/>"),
        )
        mail = self.env["mail.mail"].sudo().create({
            "email_to": SUPPORT_EMAIL,
            "email_from": email,
            "subject": "Duplicate Contact Manager — Help Request",
            "body_html": body,
            "auto_delete": False,
        })
        try:
            mail.send()
        except Exception as error:
            _logger.exception("Help mail failed")
            raise UserError(
                "Could not send your message automatically. "
                "Please email %s directly." % SUPPORT_EMAIL
            ) from error

        self.help_message = False
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Help",
                "message": "Your message was sent. We will get back to you soon.",
                "type": "success",
                "sticky": False,
                "next": self.action_open_about_us(section="help"),
            },
        }
