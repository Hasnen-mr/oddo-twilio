from odoo import models, fields

class TwilioCallLog(models.Model):
    _name = "twilio.call.log"
    _description = "Twilio Call Log"
    _order = "call_date desc"

    from_number = fields.Char("From")
    to_number = fields.Char("To")
    duration = fields.Integer("Duration")
    status = fields.Char("Status")
    call_date = fields.Datetime("Date")
    recording_url = fields.Char("Recording")