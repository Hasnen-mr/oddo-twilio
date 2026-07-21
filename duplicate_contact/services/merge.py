# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

# Models with a direct partner field to reassign.
_PARTNER_FIELD_MAP = [
    ("mail.message", "author_id"),
    ("mail.followers", "partner_id"),
]


class DuplicateMergeService:
    """Merge duplicate partner into survivor."""

    def __init__(self, env):
        self.env = env

    def _available_models(self):
        models = list(_PARTNER_FIELD_MAP)
        optional = [
            ("crm.lead", "partner_id"),
            ("sale.order", "partner_id"),
            ("account.move", "partner_id"),
            ("project.task", "partner_id"),
            ("calendar.event", "partner_id"),
        ]
        for model_name, field_name in optional:
            if model_name in self.env:
                models.append((model_name, field_name))
        return models

    def merge_partners(
        self,
        survivor,
        duplicate,
        field_choices=None,
        combine_notes=True,
        partner_a=None,
        partner_b=None,
    ):
        """Merge duplicate into survivor. field_choices map fields to 'a' or 'b'."""
        field_choices = field_choices or {}
        dup = duplicate
        if survivor.id == dup.id:
            return survivor

        partner_a = partner_a or survivor
        partner_b = partner_b or duplicate

        def pick(field):
            source = partner_a if field_choices.get(field, "a") == "a" else partner_b
            return getattr(source, field)

        write_vals = {
            "name": pick("name"),
            "email": pick("email") or survivor.email or dup.email,
            "phone": pick("phone") or survivor.phone or dup.phone,
            "mobile": pick("mobile") or survivor.mobile or dup.mobile,
            "street": pick("street") or survivor.street or dup.street,
            "city": pick("city") or survivor.city or dup.city,
            "zip": pick("zip") or survivor.zip or dup.zip,
            "website": pick("website") or survivor.website or dup.website,
            "vat": pick("vat") or survivor.vat or dup.vat,
        }
        if combine_notes:
            notes = []
            for p in (survivor, dup):
                if p.comment:
                    notes.append(p.comment)
            if notes:
                write_vals["comment"] = "\n\n---\n\n".join(dict.fromkeys(notes))

        survivor.write(write_vals)
        self._reassign_relations(survivor, dup)
        self._merge_followers(survivor, dup)
        self._merge_messages(survivor, dup)

        dup.active = False
        dup.write({"comment": (dup.comment or "") + "\n[Merged into %s]" % survivor.name})

        self.env["duplicate.contact.merge.history"].sudo().create({
            "survivor_id": survivor.id,
            "merged_id": dup.id,
            "merged_name": dup.name,
            "survivor_name": survivor.name,
        })
        return survivor

    def _reassign_relations(self, survivor, duplicate):
        for model_name, field_name in self._available_models():
            if model_name not in self.env:
                continue
            Model = self.env[model_name].sudo()
            if field_name not in Model._fields:
                continue
            records = Model.search([(field_name, "=", duplicate.id)])
            if records:
                records.write({field_name: survivor.id})

        # Child contacts
        children = self.env["res.partner"].sudo().search([("parent_id", "=", duplicate.id)])
        if children:
            children.write({"parent_id": survivor.id})

        # Generic res_id for partner attachments
        Attachment = self.env["ir.attachment"].sudo()
        atts = Attachment.search([
            ("res_model", "=", "res.partner"),
            ("res_id", "=", duplicate.id),
        ])
        if atts:
            atts.write({"res_id": survivor.id})

    def _merge_followers(self, survivor, duplicate):
        Followers = self.env["mail.followers"].sudo()
        dup_followers = Followers.search([
            ("res_model", "=", "res.partner"),
            ("res_id", "=", duplicate.id),
        ])
        existing = {
            (f.partner_id.id, f.channel_id.id)
            for f in Followers.search([
                ("res_model", "=", "res.partner"),
                ("res_id", "=", survivor.id),
            ])
        }
        for follower in dup_followers:
            key = (follower.partner_id.id, follower.channel_id.id)
            if key in existing:
                follower.unlink()
            else:
                follower.write({"res_id": survivor.id})
                existing.add(key)

    def _merge_messages(self, survivor, duplicate):
        Message = self.env["mail.message"].sudo()
        messages = Message.search([
            ("model", "=", "res.partner"),
            ("res_id", "=", duplicate.id),
        ])
        if messages:
            messages.write({"res_id": survivor.id})
