import re
# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, time, timedelta

from odoo import api, fields, models, release


class TwilioDialerDashboard(models.TransientModel):
    _name = "twilio.dialer.dashboard"
    _description = "Twilio Dialer Dashboard"

    name = fields.Char(default="Dashboard", readonly=True)
    connection_configured = fields.Boolean(readonly=True)
    connection_status = fields.Char(readonly=True)
    total_calls = fields.Integer(readonly=True)
    completed_calls = fields.Integer(readonly=True)
    total_campaigns = fields.Integer(readonly=True)
    active_campaigns = fields.Integer(readonly=True)
    callable_contacts = fields.Integer(readonly=True)
    today_calls = fields.Integer(readonly=True)
    seven_day_calls = fields.Integer(readonly=True)
    thirty_day_calls = fields.Integer(readonly=True)
    incoming_calls = fields.Integer(readonly=True)
    outgoing_calls = fields.Integer(readonly=True)
    missed_calls = fields.Integer(readonly=True)
    completion_rate = fields.Float(readonly=True)
    total_duration_display = fields.Char(readonly=True)
    average_duration_display = fields.Char(readonly=True)
    date_line_ids = fields.One2many(
        "twilio.dialer.dashboard.date.line",
        "dashboard_id",
        readonly=True,
    )
    agent_line_ids = fields.One2many(
        "twilio.dialer.dashboard.agent.line",
        "dashboard_id",
        readonly=True,
    )

    @staticmethod
    def _format_duration(seconds):
        seconds = int(seconds or 0)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return "%dh %02dm" % (hours, minutes)
        return "%dm %02ds" % (minutes, secs)

    def _dashboard_values(self):
        icp = self.env["ir.config_parameter"].sudo()
        configured = all(
            icp.get_param(key)
            for key in (
                "twilio_dialer.account_sid",
                "twilio_dialer.auth_token",
                "twilio_dialer.phone_number",
                "twilio_dialer.api_key_sid",
                "twilio_dialer.application_sid",
            )
        )
        is_admin = self.env["twilio.number.allocation"]._is_current_twilio_admin()
        call_logs = self.env["twilio.call.log"].sudo()
        campaigns = self.env["twilio.auto.dialer"].sudo()
        contacts = self.env["res.partner"].sudo()
        today = fields.Date.context_today(self)
        start_30_days = datetime.combine(today - timedelta(days=29), time.min)
        
        # Twilio Admin sees team-wide calls; standard users see only their own calls
        if is_admin:
            logs = call_logs.search([("start_time", ">=", start_30_days)])
        else:
            logs = call_logs.search([("start_time", ">=", start_30_days), ("user_id", "=", self.env.user.id)])
        missed_statuses = {"busy", "no_answer", "failed", "canceled"}

        date_stats = defaultdict(
            lambda: {"calls": 0, "completed": 0, "missed": 0, "duration": 0}
        )
        agent_stats = defaultdict(
            lambda: {
                "calls": 0,
                "completed": 0,
                "missed": 0,
                "outgoing": 0,
                "duration": 0,
            }
        )
        for log in logs:
            local_date = fields.Datetime.context_timestamp(self, log.start_time).date()
            date_item = date_stats[local_date]
            agent_item = agent_stats[log.user_id]
            for item in (date_item, agent_item):
                item["calls"] += 1
                item["duration"] += log.duration or 0
                if log.status == "completed":
                    item["completed"] += 1
                if log.status in missed_statuses:
                    item["missed"] += 1
            if log.direction == "outgoing":
                agent_item["outgoing"] += 1

        last_seven_days = today - timedelta(days=6)
        total_30 = len(logs)
        completed_30 = sum(1 for log in logs if log.status == "completed")
        duration_30 = sum(log.duration or 0 for log in logs)
        date_lines = []
        for offset in range(7):
            day = today - timedelta(days=offset)
            item = date_stats[day]
            date_lines.append((0, 0, {
                "date": day,
                "total_calls": item["calls"],
                "completed_calls": item["completed"],
                "missed_calls": item["missed"],
                "duration_display": self._format_duration(item["duration"]),
            }))

        agent_lines = []
        for user, item in sorted(
            agent_stats.items(),
            key=lambda pair: pair[1]["calls"],
            reverse=True,
        ):
            agent_lines.append((0, 0, {
                "user_id": user.id,
                "total_calls": item["calls"],
                "completed_calls": item["completed"],
                "missed_calls": item["missed"],
                "outgoing_calls": item["outgoing"],
                "completion_rate": (
                    item["completed"] / item["calls"]
                    if item["calls"] else 0.0
                ),
                "duration_display": self._format_duration(item["duration"]),
            }))

        return {
            "name": "Dashboard",
            "connection_configured": configured,
            "connection_status": "Connected" if configured else "Configuration required",
            "total_calls": call_logs.search_count([]),
            "completed_calls": call_logs.search_count([("status", "=", "completed")]),
            "total_campaigns": campaigns.search_count([]),
            "active_campaigns": campaigns.search_count(
                [("state", "in", ("ready", "running", "paused"))]
            ),
            "callable_contacts": contacts.search_count(
                [("phone", "!=", False)]
            ),
            "today_calls": date_stats[today]["calls"],
            "seven_day_calls": sum(
                item["calls"]
                for day, item in date_stats.items()
                if day >= last_seven_days
            ),
            "thirty_day_calls": total_30,
            "incoming_calls": sum(1 for log in logs if log.direction == "incoming"),
            "outgoing_calls": sum(1 for log in logs if log.direction == "outgoing"),
            "missed_calls": sum(1 for log in logs if log.status in missed_statuses),
            "completion_rate": (
                completed_30 / total_30 if total_30 else 0.0
            ),
            "total_duration_display": self._format_duration(duration_30),
            "average_duration_display": self._format_duration(
                duration_30 / total_30 if total_30 else 0
            ),
            "date_line_ids": date_lines,
            "agent_line_ids": agent_lines,
        }

    @api.model
    def _get_or_create_dashboard(self):
        dashboard = self.search([], order="id desc", limit=1)
        if not dashboard:
            dashboard = self.sudo().create(self._dashboard_values())
        return dashboard

    def web_read(self, specification):
        records = self.exists()
        if not records:
            dashboard = self._get_or_create_dashboard()
            res = dashboard.web_read(specification)
            if res and self.ids:
                res[0]["id"] = self.ids[0]
            return res
        return super().web_read(specification)

    def read(self, fields=None, load='_classic_read'):
        records = self.exists()
        if not records:
            dashboard = self._get_or_create_dashboard()
            res = dashboard.read(fields=fields, load=load)
            if res and self.ids:
                res[0]["id"] = self.ids[0]
            return res
        return super().read(fields=fields, load=load)

    @api.model
    def action_open_dashboard(self):
        dashboard = self.sudo().create(self._dashboard_values())
        view_id = (
            self.env.ref("twilio_dialer_pro.view_twilio_dialer_dashboard_form", raise_if_not_found=False) or
            self.env.ref("twilio_dialer.view_twilio_dialer_dashboard_form", raise_if_not_found=False)
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Dashboard",
            "res_model": self._name,
            "res_id": dashboard.id,
            "view_mode": "form",
            "views": [(view_id.id if view_id else False, "form")],
            "view_id": view_id.id if view_id else False,
            "target": "current",
        }

    def action_open_configuration(self):
        return self.env["res.config.settings"].action_open_twilio_configuration()

    def action_open_dialer(self):
        """Open softphone when connected; otherwise send user to Configuration."""
        self.ensure_one()
        if self.connection_configured:
            action = (
                self.env.ref("twilio_dialer_pro.action_twilio_open_phone", raise_if_not_found=False) or
                self.env.ref("twilio_dialer.action_twilio_open_phone", raise_if_not_found=False)
            )
            if action:
                return action.read()[0]
            return {
                "type": "ir.actions.client",
                "name": "Open Phone",
                "tag": "twilio_dialer.open_dialer",
            }
        return self.action_open_configuration()

    def action_open_call_logs(self):
        return self.env.ref("twilio_dialer_pro.action_twilio_call_log").read()[0]

    def action_open_call_graph(self):
        action = self.action_open_call_logs()
        graph = self.env.ref("twilio_dialer.view_twilio_call_log_graph")
        pivot = self.env.ref("twilio_dialer.view_twilio_call_log_pivot")
        action.update({
            "name": "Call Analytics by Date",
            "views": [(graph.id, "graph"), (pivot.id, "pivot"), (False, "list")],
            "view_mode": "graph,pivot,list",
        })
        return action

    def action_open_agent_screen(self):
        """Open the Agents & Number Allocation management hub in Configurations."""
        return {
            "type": "ir.actions.act_window",
            "name": "Settings",
            "res_model": "res.config.settings",
            "view_mode": "form",
            "target": "inline",
            "context": {
                "module": "twilio_dialer",
                "bin_size": False,
                "active_section": "allocation",
                "default_active_section": "allocation",
                "default_twilio_config_section": "allocation",
            },
        }

    def action_open_agent_analytics(self):
        action = self.action_open_call_logs()
        pivot = self.env.ref("twilio_dialer.view_twilio_call_log_pivot")
        graph = self.env.ref("twilio_dialer.view_twilio_call_log_graph")
        action.update({
            "name": "Agent Call Analytics",
            "views": [(pivot.id, "pivot"), (graph.id, "graph"), (False, "list")],
            "view_mode": "pivot,graph,list",
        })
        return action

    def action_open_auto_dialer(self):
        return self.env.ref("twilio_dialer.action_twilio_auto_dialer").read()[0]

    def action_open_contacts(self):
        return self.env.ref("contacts.action_contacts").read()[0]

    def action_open_duplicate_contact_apps(self):
        """Open Smart Duplicate Contact Manager on the Odoo Apps Store."""
        series = release.major_version
        return {
            "type": "ir.actions.act_url",
            "url": "https://apps.odoo.com/apps/modules/%s/sm_duplicate_contact" % series,
            "target": "new",
        }


class TwilioDialerDashboardDateLine(models.TransientModel):
    _name = "twilio.dialer.dashboard.date.line"
    _description = "Twilio Dashboard Date Analytics"
    _order = "date desc"

    dashboard_id = fields.Many2one(
        "twilio.dialer.dashboard",
        required=True,
        ondelete="cascade",
    )
    date = fields.Date(readonly=True)
    total_calls = fields.Integer(readonly=True)
    completed_calls = fields.Integer(readonly=True)
    missed_calls = fields.Integer(readonly=True)
    duration_display = fields.Char(readonly=True)


class TwilioDialerDashboardAgentLine(models.TransientModel):
    _name = "twilio.dialer.dashboard.agent.line"
    _description = "Twilio Dashboard Agent Analytics"
    _order = "total_calls desc"

    dashboard_id = fields.Many2one(
        "twilio.dialer.dashboard",
        required=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one("res.users", readonly=True)
    total_calls = fields.Integer(readonly=True)
    completed_calls = fields.Integer(readonly=True)
    missed_calls = fields.Integer(readonly=True)
    outgoing_calls = fields.Integer(readonly=True)
    completion_rate = fields.Float(readonly=True)
    duration_display = fields.Char(readonly=True)
