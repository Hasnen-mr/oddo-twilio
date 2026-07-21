# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from odoo import api, models, fields

_logger = logging.getLogger(__name__)

MODULE_NAME = "twilio_dialer"
VERSION_INFO_PATHS = (
    # Primary: publisher cloud
    "https://extension.mybroadcast.online/odoo/twilio_dialer/version.json",
    # Fallback: GitHub branch (updated on every release push)
    "https://raw.githubusercontent.com/Hasnen-mr/oddo-twilio/18.0/twilio_dialer/static/description/version_info.json",
)
FETCH_TIMEOUT = 8


class TwilioVersionUpdate(models.AbstractModel):
    _name = "twilio.version.update"
    _description = "Twilio Dialer Version Update Check"

    @api.model
    def check_for_update(self):
        """Return update payload for the in-app dialog, or available=False."""
        installed = self._get_installed_version()
        if not installed:
            return {"available": False}

        uid = self.env.uid
        snooze_until = self._get_param("twilio_dialer.update.snooze_until.%s" % uid)
        if snooze_until:
            try:
                if fields.Datetime.to_datetime(snooze_until) > fields.Datetime.now():
                    return {"available": False}
            except Exception:
                pass

        # At most one auto-prompt per calendar day (until Remind / Okay)
        today = fields.Date.context_today(self)
        last_shown = self._get_param("twilio_dialer.update.last_shown.%s" % uid)
        if last_shown == str(today):
            return {"available": False}

        remote = self._fetch_remote_version_info()
        if not remote and self._get_param("twilio_dialer.update.demo") == "1":
            remote = self._load_local_version_info()
        if not remote:
            return {"available": False}

        latest = (remote.get("version") or "").strip()
        if not latest or not self._is_newer(latest, installed):
            return {"available": False}

        dismissed = (
            self._get_param("twilio_dialer.update.dismissed_version.%s" % uid) or ""
        ).strip()
        if dismissed and not self._is_newer(latest, dismissed):
            return {"available": False}

        features = remote.get("features") or []
        if isinstance(features, str):
            features = [line.strip() for line in features.splitlines() if line.strip()]
        features = [f for f in features if f][:12]

        if not features:
            features = self._features_from_changes(installed, latest, remote)

        self._set_param("twilio_dialer.update.last_shown.%s" % uid, str(today))

        series = self._odoo_series(installed) or self._odoo_series(latest) or "19.0"
        apps_url = "https://apps.odoo.com/apps/modules/%s/twilio_dialer" % series

        return {
            "available": True,
            "installed_version": installed,
            "latest_version": latest,
            "title": remote.get("title") or "New Version Available",
            "message": remote.get("message")
            or "A newer version of Twilio Dialer is available.",
            "features": features,
            "download_url": apps_url,
            "release_date": remote.get("release_date") or "",
        }

    @api.model
    def snooze_update(self):
        """Remind me later — hide the dialog for 24 hours."""
        until = fields.Datetime.to_string(fields.Datetime.now() + timedelta(days=1))
        self._set_param("twilio_dialer.update.snooze_until.%s" % self.env.uid, until)
        return {"ok": True, "snooze_until": until}

    @api.model
    def dismiss_update(self, version):
        """Okay — dismiss notifications for this version (until a newer one)."""
        version = (version or "").strip()
        if version:
            self._set_param(
                "twilio_dialer.update.dismissed_version.%s" % self.env.uid, version
            )
        self._set_param("twilio_dialer.update.snooze_until.%s" % self.env.uid, False)
        return {"ok": True}

    # ── helpers ──────────────────────────────────────────────

    def _get_installed_version(self):
        module = (
            self.env["ir.module.module"]
            .sudo()
            .search([("name", "=", MODULE_NAME)], limit=1)
        )
        return (module.latest_version or module.installed_version or "").strip()

    def _get_param(self, key):
        return self.env["ir.config_parameter"].sudo().get_param(key)

    def _set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(key, value or "")

    def _fetch_remote_version_info(self):
        for url in VERSION_INFO_PATHS:
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": "Odoo-Twilio-Dialer-UpdateCheck/1.0",
                        "Accept": "application/json",
                    },
                )
                with urlopen(request, timeout=FETCH_TIMEOUT) as response:
                    raw = response.read().decode("utf-8")
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("version"):
                    return data
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
                _logger.info("Version check failed for %s: %s", url, error)
            except Exception:
                _logger.exception("Unexpected version check error for %s", url)
        return None

    def _load_local_version_info(self):
        """Read bundled version_info.json (used for demo / offline preview)."""
        try:
            from odoo.modules.module import get_module_path

            module_path = get_module_path(MODULE_NAME)
            if not module_path:
                return None
            path = "%s/static/description/version_info.json" % module_path
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and data.get("version"):
                return data
        except Exception as error:
            _logger.info("Local version_info load failed: %s", error)
        return None

    @api.model
    def _odoo_series(self, version):
        """Extract series like 19.0 from 19.0.1.2.60."""
        parts = (version or "").split(".")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return "%s.%s" % (parts[0], parts[1])
        return ""

    @api.model
    def _parse_version(self, version):
        """Parse Odoo-style version (e.g. 18.0.1.2.61) into a comparable tuple."""
        parts = []
        for chunk in (version or "").split("."):
            try:
                parts.append(int(chunk))
            except ValueError:
                digits = "".join(c for c in chunk if c.isdigit())
                parts.append(int(digits) if digits else 0)
        return tuple(parts)

    @api.model
    def _is_newer(self, candidate, current):
        return self._parse_version(candidate) > self._parse_version(current)

    @api.model
    def _features_from_changes(self, installed, latest, remote):
        """Build a feature list from remote changelog / changes when features missing."""
        changelog = remote.get("changelog") or remote.get("changes") or {}
        bullets = []
        if isinstance(changelog, dict):
            for ver, entries in changelog.items():
                if not self._is_newer(ver, installed) and ver != latest:
                    continue
                if isinstance(entries, list):
                    bullets.extend(entries)
                elif isinstance(entries, str):
                    bullets.append(entries)
        elif isinstance(changelog, list):
            bullets.extend(changelog)

        cleaned = []
        for item in bullets:
            text = (item or "").strip()
            if text and text not in cleaned:
                cleaned.append(text)
        if cleaned:
            return cleaned[:12]
        return [
            "Bug fixes and performance improvements",
            "Update the module from Apps to get the latest features",
        ]
