# -*- coding: utf-8 -*-
import json
import logging
import urllib.error
import urllib.request

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TwilioAIService(models.AbstractModel):
    _name = "twilio.ai.service"
    _description = "Twilio Dialer AI Service"

    def _icp(self):
        return self.env["ir.config_parameter"].sudo()

    def get_provider(self):
        return self._icp().get_param("twilio_dialer.ai_provider", "openai") or "openai"

    def is_transcript_enabled(self):
        return self._icp().get_param("twilio_dialer.ai_enable_transcript") in ("True", "true", "1")

    def is_summary_enabled(self):
        return self._icp().get_param("twilio_dialer.ai_enable_summary") in ("True", "true", "1")

    def _get_api_key(self, provider=None):
        provider = provider or self.get_provider()
        key_map = {
            "openai": "twilio_dialer.openai_api_key",
            "anthropic": "twilio_dialer.anthropic_api_key",
            "gemini": "twilio_dialer.gemini_api_key",
            "deepgram": "twilio_dialer.deepgram_api_key",
        }
        param = key_map.get(provider)
        if not param:
            raise UserError("Unsupported AI provider: %s" % provider)
        api_key = (self._icp().get_param(param) or "").strip()
        if not api_key:
            raise UserError(
                "Please configure the %s API key under Twilio Power Dialer → Configuration → AI Settings."
                % provider.replace("_", " ").title()
            )
        return api_key

    def _http_json(self, url, payload, headers, timeout=60):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="ignore")
            _logger.error("AI HTTP error %s: %s", error.code, detail)
            raise UserError("AI provider request failed (%s): %s" % (error.code, detail[:400]))
        except Exception as error:
            _logger.error("AI request failed: %s", error)
            raise UserError("Unable to reach AI provider: %s" % error)

    def generate_text(self, prompt, system_prompt=None, provider=None):
        provider = provider or self.get_provider()
        api_key = self._get_api_key(provider)
        system_prompt = system_prompt or "You are a helpful call-center assistant."

        if provider == "openai":
            result = self._http_json(
                "https://api.openai.com/v1/chat/completions",
                {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
                {
                    "Authorization": "Bearer %s" % api_key,
                    "Content-Type": "application/json",
                },
            )
            return (result.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()

        if provider == "anthropic":
            result = self._http_json(
                "https://api.anthropic.com/v1/messages",
                {
                    "model": "claude-3-5-haiku-latest",
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": prompt}],
                },
                {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
            parts = result.get("content") or []
            return "\n".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()

        if provider == "gemini":
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-1.5-flash:generateContent?key=%s" % api_key
            )
            result = self._http_json(
                url,
                {
                    "contents": [
                        {
                            "parts": [
                                {"text": "%s\n\n%s" % (system_prompt, prompt)},
                            ]
                        }
                    ]
                },
                {"Content-Type": "application/json"},
            )
            candidates = result.get("candidates") or []
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts") or []
            return "\n".join(part.get("text", "") for part in parts).strip()

        if provider == "deepgram":
            raise UserError(
                "Deepgram is intended for audio transcription. Use Create Transcript on a call with a recording URL, "
                "or choose OpenAI / Anthropic / Gemini for text summary."
            )

        raise UserError("Unsupported AI provider: %s" % provider)

    def create_transcript(self, call_log):
        if not self.is_transcript_enabled():
            raise UserError("Enable Create Call Transcripts in Configuration → AI Settings.")

        notes = (call_log.notes or "").strip()
        recording_url = (call_log.recording_url or "").strip()
        if not notes and not recording_url:
            raise UserError(
                "Add call notes or a recording URL before creating a transcript."
            )

        prompt = (
            "Create a clean call transcript from this Odoo Twilio call log.\n"
            "From: {from_number}\n"
            "To: {to_number}\n"
            "Direction: {direction}\n"
            "Status: {status}\n"
            "Duration (sec): {duration}\n"
            "Recording URL: {recording_url}\n"
            "Notes / raw content:\n{notes}\n\n"
            "Return only the transcript text."
        ).format(
            from_number=call_log.from_number or "",
            to_number=call_log.to_number or "",
            direction=call_log.direction or "",
            status=call_log.status or "",
            duration=call_log.duration or 0,
            recording_url=recording_url or "N/A",
            notes=notes or "No notes provided.",
        )
        provider = self.get_provider()
        transcript = self.generate_text(
            prompt,
            system_prompt="You produce accurate phone-call transcripts.",
            provider=provider if provider != "deepgram" else "openai",
        )
        return transcript

    def create_summary(self, call_log):
        if not self.is_summary_enabled():
            raise UserError("Enable Create Call Summaries in Configuration → AI Settings.")

        source = (call_log.transcript or call_log.notes or "").strip()
        if not source:
            raise UserError(
                "Add notes or create a transcript first, then generate a summary."
            )

        prompt = (
            "Summarize this phone call for a CRM user in 3-6 bullet points.\n"
            "Include outcome, next steps, and important details.\n\n"
            "From: {from_number}\n"
            "To: {to_number}\n"
            "Contact: {contact}\n"
            "Content:\n{source}"
        ).format(
            from_number=call_log.from_number or "",
            to_number=call_log.to_number or "",
            contact=call_log.partner_id.display_name if call_log.partner_id else "",
            source=source,
        )
        return self.generate_text(
            prompt,
            system_prompt="You write concise CRM call summaries.",
        )
