# Part of Odoo. See LICENSE file for full copyright and licensing details.
# License: LGPL-3

from urllib.parse import unquote

from odoo import http
from odoo.http import request


class TwilioDialController(http.Controller):
    """Public TwiML endpoint for click-to-call: when user answers, Twilio fetches this URL to get TwiML that dials the contact."""

    @http.route("/twilio/dial", type="http", auth="public", methods=["GET"], csrf=False)
    def twilio_dial(self, to=None, **kwargs):
        to = to or (kwargs.get("To") or "")
        to = unquote(to).strip()
        if not to:
            return request.make_response(
                '<?xml version="1.0" encoding="UTF-8"?><Response><Say>No number to dial.</Say><Hangup/></Response>',
                headers=[("Content-Type", "application/xml")],
            )
        # Twilio will dial this number when the first leg (caller) has answered
        return request.make_response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Dial>%s</Dial></Response>' % _escape_xml(to),
            headers=[("Content-Type", "application/xml")],
        )


def _escape_xml(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
