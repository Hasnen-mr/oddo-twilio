# Part of Odoo. See LICENSE file for full copyright and licensing details.
# License: LGPL-3

def post_init_hook(env):
    """Create ir.model.access records after models are loaded (fixes import-from-zip)."""
    Access = env["ir.model.access"]
    group_user = env.ref("base.group_user")
    models_to_access = [
        "twilio_config",
        "twilio.send.sms.wizard",
        "twilio.sms.line",
        "twilio.fetch.sms.wizard",
        "twilio.call.line",
        "twilio.fetch.calls.wizard",
        "twilio.click.to.call.wizard",
    ]
    for model_name in models_to_access:
        model = env["ir.model"].search([("model", "=", model_name)], limit=1)
        if not model:
            continue
        name = model_name.replace(".", " ") + " (user)"
        existing = Access.search([
            ("model_id", "=", model.id),
            ("group_id", "=", group_user.id),
        ], limit=1)
        if not existing:
            Access.create({
                "name": name,
                "model_id": model.id,
                "group_id": group_user.id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": True,
            })
