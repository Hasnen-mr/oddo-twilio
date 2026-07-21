# -*- coding: utf-8 -*-
import logging

from .similarity import compare_partners, confidence_label

_logger = logging.getLogger(__name__)


class DuplicateDetectionService:
    """Scan partners and create duplicate pair records."""

    def __init__(self, env):
        self.env = env

    def _get_rules(self):
        icp = self.env["ir.config_parameter"].sudo()
        return {
            "match_name": icp.get_param("duplicate_contact.match_name", "True") == "True",
            "match_phone": icp.get_param("duplicate_contact.match_phone", "True") == "True",
            "match_email": icp.get_param("duplicate_contact.match_email", "True") == "True",
            "match_vat": icp.get_param("duplicate_contact.match_vat", "True") == "True",
            "match_company": icp.get_param("duplicate_contact.match_company", "True") == "True",
            "match_website": icp.get_param("duplicate_contact.match_website", "True") == "True",
            "match_address": icp.get_param("duplicate_contact.match_address", "True") == "True",
            "review_threshold": float(
                icp.get_param("duplicate_contact.review_threshold", "90") or 90
            ),
            "min_threshold": float(
                icp.get_param("duplicate_contact.min_threshold", "72") or 72
            ),
        }

    def _is_ignored(self, partner_a_id, partner_b_id):
        Ignore = self.env["duplicate.contact.ignore"]
        low, high = sorted((partner_a_id, partner_b_id))
        return bool(
            Ignore.search_count([
                ("partner_low_id", "=", low),
                ("partner_high_id", "=", high),
            ])
        )

    def _pair_key(self, a_id, b_id):
        return tuple(sorted((a_id, b_id)))

    def run_scan(self, limit=500, source="manual"):
        """Detect duplicates among active partners. Returns stats dict."""
        rules = self._get_rules()
        Partner = self.env["res.partner"].sudo()
        Pair = self.env["duplicate.contact.pair"].sudo()
        partners = Partner.search([("active", "=", True)], order="id", limit=limit)
        icp = self.env["ir.config_parameter"].sudo()
        auto_merge = icp.get_param("duplicate_contact.auto_merge", "False") == "True"
        Merge = None
        if auto_merge:
            from .merge import DuplicateMergeService
            Merge = DuplicateMergeService(self.env)

        def _upsert_pair(key, vals, pa, pb):
            nonlocal created, updated
            if key in existing:
                existing[key].write(vals)
                updated += 1
                pair = existing[key]
            else:
                pair = Pair.create(vals)
                existing[key] = pair
                created += 1
            if (
                auto_merge
                and vals["confidence"] >= 99.5
                and pair.state in ("open", "review")
            ):
                survivor, duplicate = (
                    (pa, pb) if key[0] == pa.id else (pb, pa)
                )
                Merge.merge_partners(survivor, duplicate)
                pair.state = "merged"
            return pair

        created = updated = skipped = 0
        existing = {}
        for pair in Pair.search([("state", "in", ("open", "review"))]):
            key = self._pair_key(pair.partner_a_id.id, pair.partner_b_id.id)
            existing[key] = pair

        by_email = {}
        by_phone = {}
        by_vat = {}

        from .normalization import normalize_email, normalize_phone, normalize_tax_id

        for partner in partners:
            email = normalize_email(partner.email)
            if email:
                by_email.setdefault(email, []).append(partner)
            for phone in (partner.phone, partner.mobile):
                norm = normalize_phone(phone)
                if norm:
                    by_phone.setdefault(norm, []).append(partner)
            vat = normalize_tax_id(partner.vat)
            if vat:
                by_vat.setdefault(vat, []).append(partner)

        candidate_sets = []
        for bucket in (by_email, by_phone, by_vat):
            for group in bucket.values():
                if len(group) > 1:
                    candidate_sets.append(group)

        seen_pairs = set()
        for group in candidate_sets:
            for i, pa in enumerate(group):
                for pb in group[i + 1 :]:
                    key = self._pair_key(pa.id, pb.id)
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    if self._is_ignored(pa.id, pb.id):
                        skipped += 1
                        continue
                    confidence, reasons = compare_partners(pa, pb, rules)
                    if confidence < rules["min_threshold"]:
                        continue
                    state = (
                        "review"
                        if confidence >= rules["review_threshold"]
                        else "open"
                    )
                    label = confidence_label(confidence, rules["review_threshold"])
                    vals = {
                        "partner_a_id": key[0],
                        "partner_b_id": key[1],
                        "confidence": confidence,
                        "match_reasons": "\n".join("✓ %s" % r for r in reasons),
                        "state": state,
                        "confidence_label": label,
                        "detection_source": source,
                    }
                    _upsert_pair(key, vals, pa, pb)

        # Fuzzy pass on smaller subsets with same city
        city_groups = {}
        for partner in partners:
            city = (partner.city or "").strip().lower()
            if city:
                city_groups.setdefault(city, []).append(partner)
        for group in city_groups.values():
            if len(group) < 2 or len(group) > 40:
                continue
            for i, pa in enumerate(group):
                for pb in group[i + 1 :]:
                    key = self._pair_key(pa.id, pb.id)
                    if key in seen_pairs:
                        continue
                    if self._is_ignored(pa.id, pb.id):
                        continue
                    confidence, reasons = compare_partners(pa, pb, rules)
                    if confidence < rules["min_threshold"]:
                        continue
                    seen_pairs.add(key)
                    state = (
                        "review" if confidence >= rules["review_threshold"] else "open"
                    )
                    vals = {
                        "partner_a_id": key[0],
                        "partner_b_id": key[1],
                        "confidence": confidence,
                        "match_reasons": "\n".join("✓ %s" % r for r in reasons),
                        "state": state,
                        "confidence_label": confidence_label(
                            confidence, rules["review_threshold"]
                        ),
                        "detection_source": source,
                    }
                    _upsert_pair(key, vals, pa, pb)

        _logger.info(
            "Duplicate scan (%s): created=%s updated=%s skipped=%s",
            source, created, updated, skipped,
        )
        return {"created": created, "updated": updated, "skipped": skipped}
