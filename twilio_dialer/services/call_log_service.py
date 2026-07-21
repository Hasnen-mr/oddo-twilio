import logging

from markupsafe import Markup, escape

_logger = logging.getLogger(__name__)


class CallLogService:
    """Format and post a contact chatter note for a completed or attempted call."""

    _status_labels = {
        "completed": "Completed",
        "failed": "Failed",
        "busy": "Busy",
        "no_answer": "No Answer",
        "canceled": "Canceled",
        "rejected": "Rejected",
        "missed": "Missed",
    }

    @staticmethod
    def _duration_display(duration):
        seconds = max(int(duration or 0), 0)
        if seconds < 60:
            return "%d sec" % seconds
        return "%.1f min" % (seconds / 60)

    @staticmethod
    def _get_contact(call_log):
        return call_log.partner_id or call_log.contact_id or False

    def format_call_activity(self, call_log):
        recording = "Not Available"
        if call_log.playback_url:
            url = escape(call_log.playback_url)
            recording = (
                '<div class="mt8">'
                '<audio controls preload="none" style="width:100%%;">'
                '<source src="%s" type="audio/wav"/>'
                "Your browser does not support audio playback."
                "</audio></div>"
            ) % url
        summary = call_log.summary or "AI Summary is not enabled. Click here to enable it."
        status = self._status_labels.get(
            call_log.status,
            (call_log.status or "Unknown").replace("_", " ").title(),
        )
        return Markup(
            "<b>From:</b> %s<br/>"
            "<b>To:</b> %s<br/>"
            "<b>Duration:</b> %s<br/>"
            "<b>Recording:</b> %s<br/>"
            "<b>Call Status:</b> %s<br/>"
            "<b>Summary:</b> %s"
        ) % (
            escape(call_log.from_number or "Not Available"),
            escape(call_log.to_number or "Not Available"),
            escape(self._duration_display(call_log.duration)),
            Markup(recording) if call_log.playback_url else escape(recording),
            escape(status),
            escape(summary),
        )

    def post_call_activity(self, call_log):
        contact = self._get_contact(call_log)
        if not contact or call_log.contact_activity_posted:
            return False
        try:
            contact.message_post(
                body=self.format_call_activity(call_log),
                subtype_xmlid="mail.mt_note",
            )
            call_log.with_context(mail_notrack=True).write({"contact_activity_posted": True})
            return True
        except Exception:
            _logger.exception(
                "Unable to post Contact chatter activity for Twilio Call SID %s",
                getattr(call_log, "call_sid", "unknown"),
            )
            return False
