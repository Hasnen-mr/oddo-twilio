# -*- coding: utf-8 -*-
import csv
import base64
from io import StringIO

from odoo import api, fields, models

from ..services.action_utils import act_window, xml_id_action


CRON_INTERVAL_MAP = {
    "hourly": (1, "hours"),
    "daily": (1, "days"),
    "weekly": (1, "weeks"),
    "monthly": (1, "months"),
}


class DuplicateContactDashboard(models.TransientModel):
    _name = "duplicate.contact.dashboard"
    _description = "Duplicate Contact Dashboard"

    name = fields.Char(default="Dashboard", readonly=True)
    total_contacts = fields.Integer(readonly=True)
    duplicate_pairs = fields.Integer(string="Duplicate Pairs", readonly=True)
    contacts_with_duplicates = fields.Integer(string="Contacts With Duplicates", readonly=True)
    duplicates_found = fields.Integer(string="Duplicate Contacts", readonly=True)
    need_review = fields.Integer(readonly=True)
    merged_count = fields.Integer(readonly=True)
    ignored_count = fields.Integer(readonly=True)
    duplicate_rate = fields.Float(string="Duplicate Rate %", digits=(5, 2), readonly=True)

    scan_status = fields.Selection(
        [
            ("idle", "Ready"),
            ("running", "Syncing"),
            ("done", "Up to date"),
        ],
        string="Sync Status",
        readonly=True,
    )
    scan_progress = fields.Float(string="Scan Progress %", digits=(5, 2), readonly=True)
    contacts_scanned = fields.Integer(readonly=True)
    contacts_total = fields.Integer(readonly=True)
    last_manual_scan = fields.Datetime(readonly=True)
    last_auto_scan = fields.Datetime(readonly=True)
    last_scan_created = fields.Integer(readonly=True)
    last_scan_updated = fields.Integer(readonly=True)
    manual_pair_count = fields.Integer(string="Manual Detections", readonly=True)
    auto_pair_count = fields.Integer(string="Automatic Detections", readonly=True)
    active_scan_name = fields.Char(readonly=True)
    sync_message = fields.Char(readonly=True)
    next_auto_sync_label = fields.Char(string="Next Automatic Sync", readonly=True)

    scan_line_ids = fields.One2many(
        "duplicate.contact.dashboard.scan.line",
        "dashboard_id",
        string="Recent Scans",
        readonly=True,
    )

    @api.model
    def _format_local_datetime(self, dt):
        if not dt:
            return ""
        local_dt = fields.Datetime.context_timestamp(self, dt)
        return local_dt.strftime("%Y-%m-%d %H:%M")

    @api.model
    def _sync_duplicate_cron(self):
        icp = self.env["ir.config_parameter"].sudo()
        cron = self.env.ref(
            "duplicate_contact.ir_cron_duplicate_contact_scan",
            raise_if_not_found=False,
        )
        if not cron:
            return
        interval_key = icp.get_param("duplicate_contact.cron_interval", "daily")
        if interval_key == "off":
            if cron.active:
                cron.write({"active": False})
            return
        mapping = CRON_INTERVAL_MAP.get(interval_key, CRON_INTERVAL_MAP["daily"])
        expected = {
            "active": True,
            "interval_number": mapping[0],
            "interval_type": mapping[1],
        }
        if (
            cron.active != expected["active"]
            or cron.interval_number != expected["interval_number"]
            or cron.interval_type != expected["interval_type"]
        ):
            cron.write(expected)

    @api.model
    def _get_next_auto_sync_label(self, icp=None):
        icp = icp or self.env["ir.config_parameter"].sudo()
        interval = icp.get_param("duplicate_contact.cron_interval", "daily")
        if interval == "off":
            return "Next sync: disabled in settings"
        cron = self.env.ref(
            "duplicate_contact.ir_cron_duplicate_contact_scan",
            raise_if_not_found=False,
        )
        if not cron or not cron.active:
            return "Next sync: not scheduled"
        if icp.get_param("duplicate_contact.scan_active") == "True":
            return "Next sync: after current run completes"
        if not cron.nextcall:
            return "Next sync: pending schedule"
        return "Next sync: %s" % self._format_local_datetime(cron.nextcall)

    @api.model
    def _dashboard_values(self):
        Partner = self.env["res.partner"].sudo()
        Pair = self.env["duplicate.contact.pair"].sudo()
        History = self.env["duplicate.contact.merge.history"].sudo()
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()
        icp = self.env["ir.config_parameter"].sudo()
        self._sync_duplicate_cron()

        total_contacts = Partner.search_count([("active", "=", True)])
        duplicate_pairs = Pair.search_count([("state", "in", ("open", "review"))])

        # Old scans could create more pair rows than contacts (city-only bug).
        if duplicate_pairs > total_contacts and total_contacts > 0:
            from ..services.detection import DuplicateDetectionService
            DuplicateDetectionService(self.env).revalidate_open_pairs()
            duplicate_pairs = Pair.search_count([("state", "in", ("open", "review"))])

        open_pairs = Pair.search([("state", "in", ("open", "review"))])
        contacts_with_duplicates = len(set(
            open_pairs.mapped("partner_a_id").ids + open_pairs.mapped("partner_b_id").ids
        ))
        need_review = Pair.search_count([("state", "=", "review")])

        active_scan = ScanLog._get_active_scan()
        last_manual = ScanLog.search(
            [("source", "=", "manual")],
            limit=1,
            order="date_start desc",
        )
        last_auto = ScanLog.search(
            [("source", "=", "cron")],
            limit=1,
            order="date_start desc",
        )
        latest_done = ScanLog.search(
            [("state", "=", "done")],
            limit=1,
            order="date_end desc",
        )

        if active_scan:
            scan_status = "running"
            scan_progress = active_scan.progress
            contacts_scanned = active_scan.processed_contacts
            contacts_total = active_scan.total_contacts
            active_scan_name = active_scan.name
            sync_message = "Sync in progress: %s of %s contacts scanned." % (
                f"{contacts_scanned:,}",
                f"{contacts_total:,}",
            )
        elif icp.get_param("duplicate_contact.scan_active") == "True":
            scan_status = "running"
            scan_progress = float(icp.get_param("duplicate_contact.scan_progress", "0") or 0)
            contacts_scanned = int(icp.get_param("duplicate_contact.scan_processed", "0") or 0)
            contacts_total = total_contacts
            active_scan_name = "Background sync"
            sync_message = "Background sync is running."
        else:
            scan_status = "done" if latest_done else "idle"
            scan_progress = 100.0 if latest_done else 0.0
            contacts_scanned = latest_done.processed_contacts if latest_done else 0
            contacts_total = total_contacts
            active_scan_name = False
            sync_message = (
                "Last sync completed on %s."
                % self._format_local_datetime(latest_done.date_end)
                if latest_done and latest_done.date_end
                else "No full scan completed yet. Start a manual sync."
            )

        duplicate_rate = (
            (contacts_with_duplicates / total_contacts) * 100.0
            if total_contacts
            else 0.0
        )

        return {
            "total_contacts": total_contacts,
            "duplicate_pairs": duplicate_pairs,
            "contacts_with_duplicates": contacts_with_duplicates,
            "duplicates_found": contacts_with_duplicates,
            "need_review": need_review,
            "merged_count": History.search_count([]),
            "ignored_count": Pair.search_count([("state", "=", "ignored")]),
            "duplicate_rate": round(duplicate_rate, 2),
            "scan_status": scan_status,
            "scan_progress": scan_progress,
            "contacts_scanned": contacts_scanned,
            "contacts_total": contacts_total,
            "last_manual_scan": last_manual.date_start if last_manual else False,
            "last_auto_scan": last_auto.date_start if last_auto else False,
            "last_scan_created": latest_done.pairs_created if latest_done else 0,
            "last_scan_updated": latest_done.pairs_updated if latest_done else 0,
            "manual_pair_count": Pair.search_count([("detection_source", "=", "manual")]),
            "auto_pair_count": Pair.search_count([("detection_source", "=", "cron")]),
            "active_scan_name": active_scan_name,
            "sync_message": sync_message,
            "next_auto_sync_label": self._get_next_auto_sync_label(icp),
        }

    @api.model
    def _attach_scan_lines(self, dashboard):
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()
        lines = []
        for log in ScanLog.search([], limit=8):
            lines.append((0, 0, {"scan_log_id": log.id, "name": log.name}))
        dashboard.scan_line_ids = [(5, 0, 0)] + lines
        return dashboard

    @api.model
    def action_open_dashboard(self):
        dashboard = self.create(self._dashboard_values())
        self._attach_scan_lines(dashboard)
        return act_window(
            self.env,
            self._name,
            view_modes="form",
            name="Duplicate Contact Manager",
            res_id=dashboard.id,
        )

    def _refresh_dashboard(self):
        self.write(self._dashboard_values())
        self._attach_scan_lines(self)
        return act_window(
            self.env,
            self._name,
            view_modes="form",
            name="Duplicate Contact Manager",
            res_id=self.id,
        )

    def _refresh_dashboard_with_notice(self, result):
        action = self._refresh_dashboard()
        progress = result.get("progress", 0)
        processed = result.get("processed", 0)
        total = result.get("total", 0)
        if result.get("has_more"):
            message = "Sync running: %s / %s contacts scanned (%.1f%%)." % (
                f"{processed:,}",
                f"{total:,}",
                progress,
            )
            notif_type = "warning"
        else:
            message = "Sync completed: %s contacts scanned. %s new pairs found." % (
                f"{processed:,}",
                result.get("created", 0),
            )
            if result.get("message_extra"):
                message = result["message_extra"]
            notif_type = "success"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Duplicate Contact Sync",
                "message": message,
                "type": notif_type,
                "sticky": False,
                "next": action,
            },
        }

    def action_run_scan(self):
        """Start or continue a batched manual sync."""
        from ..services.detection import DuplicateDetectionService
        self.ensure_one()
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()
        active = ScanLog._get_active_scan()
        if not active:
            active = ScanLog._start_scan(source="manual")
        result = DuplicateDetectionService(self.env).run_scan_batch(
            scan_log=active,
            source="manual",
            max_batches=20,
        )
        return self._refresh_dashboard_with_notice(result)

    def action_run_full_sync(self):
        """Reset and start a full database sync from the beginning."""
        from ..services.detection import DuplicateDetectionService
        self.ensure_one()
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()
        running = ScanLog.search([("state", "=", "running")])
        if running:
            running.write({
                "state": "failed",
                "date_end": fields.Datetime.now(),
                "message": "Stopped for new full sync.",
            })
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("duplicate_contact.scan_offset", "0")
        icp.set_param("duplicate_contact.scan_active", "False")
        log = ScanLog._start_scan(source="manual")
        detection = DuplicateDetectionService(self.env)
        detection.revalidate_open_pairs()
        result = detection.run_scan_batch(
            scan_log=log,
            source="manual",
            max_batches=20,
        )
        return self._refresh_dashboard_with_notice(result)

    def action_continue_sync(self):
        return self.action_run_scan()

    def action_revalidate_duplicates(self):
        """Clear false positives and refresh scores for open duplicate rows."""
        from ..services.detection import DuplicateDetectionService
        self.ensure_one()
        stats = DuplicateDetectionService(self.env).revalidate_open_pairs()
        action = self._refresh_dashboard()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Duplicates Revalidated",
                "message": "%s false positives cleared. %s duplicate rows updated."
                % (stats["cleared"], stats["updated"]),
                "type": "success",
                "sticky": False,
                "next": action,
            },
        }

    def action_open_scan_logs(self):
        return self.env["duplicate.contact.hub"].action_open_hub(section="scan_reports")

    def action_download_report(self):
        """Export open duplicate pairs as CSV."""
        self.ensure_one()
        pairs = self.env["duplicate.contact.pair"].sudo().search(
            [("state", "in", ("open", "review"))],
            order="confidence desc",
        )

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "Contact A",
            "Contact B",
            "Confidence %",
            "Label",
            "State",
            "Source",
            "Match Reasons",
        ])
        for pair in pairs:
            writer.writerow([
                pair.partner_a_id.display_name,
                pair.partner_b_id.display_name,
                pair.confidence,
                pair.confidence_label,
                pair.state,
                pair.detection_source,
                (pair.match_reasons or "").replace("\n", "; "),
            ])

        attachment = self.env["ir.attachment"].sudo().create({
            "name": "duplicate_contacts_report.csv",
            "type": "binary",
            "datas": base64.b64encode(buffer.getvalue().encode("utf-8")),
            "mimetype": "text/csv",
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }

    def action_open_duplicates(self):
        return xml_id_action(self.env, "duplicate_contact.action_duplicate_contact_pairs")

    def action_open_review(self):
        return xml_id_action(
            self.env,
            "duplicate_contact.action_duplicate_contact_pairs",
            domain=[("state", "=", "review")],
            name="Need Review",
        )

    def action_open_merged(self):
        return self.env["duplicate.contact.hub"].action_open_hub(section="merge_history")

    def action_open_contacts(self):
        return xml_id_action(self.env, "contacts.action_contacts")
