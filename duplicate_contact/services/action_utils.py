# -*- coding: utf-8 -*-
"""Helpers for Odoo 18-compatible client actions."""

from odoo.tools.safe_eval import safe_eval


def _as_context(value):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    if isinstance(value, str):
        return safe_eval(value, {"uid": False}) or {}
    return {}


def act_window(env, res_model, view_modes="list,form", **kwargs):
    """Build an act_window dict including views (required by Odoo 18 web client)."""
    modes = [mode.strip() for mode in view_modes.split(",") if mode.strip()]
    action = {
        "type": "ir.actions.act_window",
        "res_model": res_model,
        "view_mode": ",".join(modes),
        "views": [(False, mode) for mode in modes],
        "target": kwargs.pop("target", "current"),
    }
    for key in ("name", "domain", "res_id", "context"):
        if key in kwargs:
            action[key] = kwargs[key]
    return action


def xml_id_action(env, xmlid, **overrides):
    """Load a stored window action with views resolved for the web client."""
    action = dict(env["ir.actions.act_window"]._for_xml_id(xmlid))
    context = overrides.pop("context", None)
    if context:
        action["context"] = {**_as_context(action.get("context")), **_as_context(context)}
    action.update(overrides)
    return action
