# -*- coding: utf-8 -*-
import json
import logging
import urllib.error
import urllib.request

from odoo import models
from odoo.exceptions import UserError

import requests

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

        raise UserError("Unsupported AI provider: %s" % provider)

    def get_speech_model(self):
        return self._icp().get_param("twilio_dialer.openai_speech_model", "whisper-1") or "whisper-1"

    def transcribe_recording(self, call_log):
        """Transcribe call log recording audio using OpenAI Speech-to-Text API.

        Uses the OpenAI API Key and Speech Model configured in AI Settings.
        Fetches recording audio via TwilioService and sends to OpenAI transcription endpoint.
        Includes retry with exponential backoff for transient errors, idempotency check,
        and detailed error messages.
        """
        import time

        if not self.is_transcript_enabled():
            raise UserError("Enable Create Call Transcripts in Configuration → AI Settings.")

        # 1. Idempotency check: avoid duplicate requests and unnecessary charges
        if call_log.transcript and call_log.transcript_status == "completed":
            _logger.info("Idempotency check: call_log=%s already has completed transcript, skipping OpenAI request.", call_log.id)
            return call_log.transcript

        if not call_log.recording_sid:
            raise UserError("No call recording SID available to transcribe for this call.")

        api_key = self._get_api_key("openai")
        speech_model = self.get_speech_model()

        # 2. Download recording with logging
        _logger.info("Downloading recording audio for call_log=%s (recording_sid=%s)...", call_log.id, call_log.recording_sid)
        dl_start = time.time()
        try:
            resp, content_type = self.env["twilio.service"].fetch_recording_audio(call_log.recording_sid)
        except Exception as err:
            _logger.exception("Failed to download recording audio from Twilio for call_log=%s: %s", call_log.id, err)
            raise UserError("Recording download failure: %s" % str(err))

        if not resp:
            _logger.error("Recording audio response is empty for call_log=%s recording_sid=%s", call_log.id, call_log.recording_sid)
            raise UserError("Recording download failure: Twilio returned no audio response.")

        audio_bytes = resp.content
        dl_duration = time.time() - dl_start
        if not audio_bytes:
            _logger.error("Recording audio content length is 0 bytes for call_log=%s", call_log.id)
            raise UserError("Recording audio file is empty (0 bytes).")

        _logger.info("Downloaded recording audio for call_log=%s: %d bytes in %.2fs (content_type=%s)",
                     call_log.id, len(audio_bytes), dl_duration, content_type)

        # 3. Request OpenAI Speech-to-Text API with retry & exponential backoff
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": "Bearer %s" % api_key}
        files = {"file": ("recording_%s.wav" % call_log.recording_sid, audio_bytes, content_type or "audio/wav")}
        data = {"model": speech_model}

        MAX_ATTEMPTS = 3
        last_error_msg = None

        _logger.info("OpenAI transcription request started: call_log=%s model=%s audio_bytes=%d",
                     call_log.id, speech_model, len(audio_bytes))
        api_start = time.time()

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                if attempt > 1:
                    backoff = 2 ** (attempt - 1)
                    _logger.info("Retrying OpenAI transcription attempt %d/%d after %ds backoff for call_log=%s",
                                 attempt, MAX_ATTEMPTS, backoff, call_log.id)
                    time.sleep(backoff)

                response = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120,
                )

                status_code = response.status_code
                if status_code == 200:
                    api_duration = time.time() - api_start
                    result = response.json()
                    transcript_text = (result.get("text") or "").strip()
                    _logger.info("OpenAI transcription completed successfully for call_log=%s in %.2fs (length=%d chars)",
                                 call_log.id, api_duration, len(transcript_text))
                    return transcript_text

                # Specific error handling for status codes
                detail = response.text[:400]
                if status_code == 401:
                    _logger.error("OpenAI API Key invalid (401) for call_log=%s: %s", call_log.id, detail)
                    raise UserError("Invalid OpenAI API Key (401 Unauthorized). Please verify key in AI Settings.")

                if status_code == 429:
                    _logger.error("OpenAI Rate Limit Exceeded (429) for call_log=%s: %s", call_log.id, detail)
                    raise UserError("OpenAI Rate Limit Exceeded (429). Please check your OpenAI account quota/plan.")

                if 400 <= status_code < 500:
                    _logger.error("OpenAI API Bad Request (%d) for call_log=%s: %s", status_code, call_log.id, detail)
                    raise UserError("OpenAI Speech-to-Text API rejected request (%d): %s" % (status_code, detail))

                # HTTP 5xx: Transient server error -> candidate for retry
                _logger.warning("OpenAI API server error (%d) on attempt %d/%d for call_log=%s: %s",
                               status_code, attempt, MAX_ATTEMPTS, call_log.id, detail)
                last_error_msg = "OpenAI server error (%d): %s" % (status_code, detail)

            except (UserError, Exception) as err:
                if isinstance(err, UserError):
                    raise
                _logger.warning("Network/Connection exception on attempt %d/%d for call_log=%s: %s",
                               attempt, MAX_ATTEMPTS, call_log.id, err)
                last_error_msg = "Network failure: %s" % str(err)

        _logger.error("OpenAI transcription exhausted %d retries for call_log=%s. Last error: %s",
                     MAX_ATTEMPTS, call_log.id, last_error_msg)
        raise UserError("OpenAI transcription failed after %d attempts: %s" % (MAX_ATTEMPTS, last_error_msg))

    def create_transcript(self, call_log):
        if not self.is_transcript_enabled():
            raise UserError("Enable Create Call Transcripts in Configuration → AI Settings.")
        if not call_log.transcript:
            return self.transcribe_recording(call_log)
        return call_log.transcript

    def create_summary(self, call_log):
        """Create a summary from the call transcript.
        
        The transcript must already be available (from Twilio).
        Uses the configured AI provider (OpenAI, Anthropic, or Gemini).
        """
        if not self.is_summary_enabled():
            raise UserError("Enable Create Call Summaries in Configuration → AI Settings.")

        # Require transcript to be available from Twilio
        transcript = (call_log.transcript or "").strip()
        if not transcript:
            raise UserError(
                "Cannot generate summary without a transcript.\n"
                "Transcript status: %s" % call_log.transcript_status
            )

        prompt = (
            "Summarize this phone call for a CRM user in 3-6 bullet points.\n"
            "Include outcome, next steps, and important details.\n\n"
            "From: {from_number}\n"
            "To: {to_number}\n"
            "Contact: {contact}\n"
            "Transcript:\n{transcript}"
        ).format(
            from_number=call_log.from_number or "",
            to_number=call_log.to_number or "",
            contact=call_log.partner_id.display_name if call_log.partner_id else "",
            transcript=transcript,
        )
        return self.generate_text(
            prompt,
            system_prompt="You write concise CRM call summaries.",
        )
