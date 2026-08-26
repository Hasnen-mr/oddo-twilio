import html
import logging
import re

from markupsafe import Markup, escape

_logger = logging.getLogger(__name__)


class CallLogService:
    """Format and manage a single, consolidated chatter activity entry for a call log."""

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

    @staticmethod
    def _clean_summary_text(text):
        """Strip HTML tags and unescape HTML entities to produce clean plain text summary."""
        if not text:
            return ""
        unescaped = html.unescape(str(text))
        cleaned = re.sub(r"<[^>]+>", "", unescaped)
        cleaned = cleaned.replace("&nbsp;", " ")
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        return "\n".join(lines)

    def format_call_activity(self, call_log):
        """Format a single consolidated activity card for Call Log and Contact chatter."""
        icp = call_log.env["ir.config_parameter"].sudo()
        is_transcript_enabled = icp.get_param("twilio_dialer.ai_enable_transcript") in ("True", "true", "1")
        is_summary_enabled = icp.get_param("twilio_dialer.ai_enable_summary") in ("True", "true", "1")

        config_url = "/web#action=twilio_dialer_pro.action_twilio_configuration"

        # 1. Recording display
        if call_log.playback_url:
            url = escape(call_log.playback_url)
            recording_html = Markup('<a href="%s" target="_blank">▶ Play Recording</a>') % url
        else:
            recording_html = Markup("Not Available")

        # 2. Transcript display (Shows clickable 'View' link opening Call Log AI Transcript tab)
        if call_log.transcript:
            form_url = escape("/web#id=%d&model=twilio.call.log&view_type=form#ai_tab" % call_log.id)
            transcript_html = Markup('<a href="%s" class="o_open_ai_tab">View</a>') % form_url
        elif is_transcript_enabled:
            if call_log.transcript_status == "processing":
                transcript_html = Markup("Transcript is currently being generated...")
            elif call_log.transcript_status == "failed":
                transcript_html = Markup("Transcript generation failed.")
            else:
                transcript_html = Markup("Not Available")
        else:
            config_link = Markup('<a href="%s">Click here to enable it.</a>') % config_url
            transcript_html = Markup("Transcript is not enabled.<br/>%s") % config_link

        # 3. Summary display (Clean HTML tags & entities, or fallback enable link)
        if call_log.summary:
            clean_summary = self._clean_summary_text(call_log.summary)
            summary_formatted = escape(clean_summary).replace("\n", "<br/>")
            summary_html = Markup(summary_formatted)
        elif is_summary_enabled:
            summary_html = Markup("Summary is being generated...")
        else:
            config_link = Markup('<a href="%s">Click here to enable it.</a>') % config_url
            summary_html = Markup("AI Summary is not enabled.<br/>%s") % config_link

        status = self._status_labels.get(
            call_log.status,
            (call_log.status or "Unknown").replace("_", " ").title(),
        )

        return Markup(
            "<b>From:</b> %s<br/>"
            "<b>To:</b> %s<br/>"
            "<b>Duration:</b> %s<br/>"
            "<b>Recording:</b><br/>%s<br/>"
            "<b>Call Status:</b> %s<br/>"
            "<b>Transcript:</b><br/>%s<br/>"
            "<b>Summary:</b><br/>%s"
        ) % (
            escape(call_log.from_number or "Not Available"),
            escape(call_log.to_number or "Not Available"),
            escape(self._duration_display(call_log.duration)),
            recording_html,
            escape(status),
            transcript_html,
            summary_html,
        )

    def post_call_activity(self, call_log):
        """Delegate single consolidated chatter activity sync to call_log."""
        try:
            return call_log._sync_chatter_activity()
        except Exception:
            _logger.exception(
                "Unable to post Contact chatter activity for Twilio Call SID %s",
                getattr(call_log, "call_sid", "unknown"),
            )
            return False
