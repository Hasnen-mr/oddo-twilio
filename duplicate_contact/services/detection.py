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
        """Run the next scan batch (continues an active sync when present)."""
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()
        active = ScanLog._get_active_scan()
        if not active:
            active = ScanLog._start_scan(
                source="cron" if source == "cron" else "manual"
            )
        return self.run_scan_batch(scan_log=active, source=source, max_batches=1)

    def run_scan_batch(self, scan_log=None, source="manual", max_batches=5):
        """Process contacts in batches with progress for large databases."""
        rules = self._get_rules()
        Partner = self.env["res.partner"].sudo()
        Pair = self.env["duplicate.contact.pair"].sudo()
        icp = self.env["ir.config_parameter"].sudo()
        ScanLog = self.env["duplicate.contact.scan.log"].sudo()

        if not scan_log:
            scan_log = ScanLog._get_active_scan() or ScanLog._start_scan(
                source="cron" if source == "cron" else "manual"
            )

        batch_size = scan_log.batch_size or int(
            icp.get_param("duplicate_contact.scan_limit", "5000") or 5000
        )
        total_contacts = scan_log.total_contacts or Partner.search_count([
            ("active", "=", True)
        ])
        offset = scan_log.scan_offset or 0

        auto_merge = icp.get_param("duplicate_contact.auto_merge", "False") == "True"
        Merge = None
        if auto_merge:
            from .merge import DuplicateMergeService
            Merge = DuplicateMergeService(self.env)

        created = updated = skipped = 0
        batches_done = 0
        has_more = True

        log_pairs_created = scan_log.pairs_created
        log_pairs_updated = scan_log.pairs_updated
        log_pairs_skipped = scan_log.pairs_skipped

        while has_more and batches_done < max_batches:
            partners = Partner.search(
                [("active", "=", True)],
                order="id",
                limit=batch_size,
                offset=offset,
            )
            if not partners:
                has_more = False
                break

            batch_stats = self._scan_partner_set(
                partners,
                rules,
                Pair,
                source,
                auto_merge=auto_merge,
                Merge=Merge,
            )
            created += batch_stats["created"]
            updated += batch_stats["updated"]
            skipped += batch_stats["skipped"]

            offset += len(partners)
            batches_done += 1
            has_more = offset < total_contacts and len(partners) == batch_size

            log_pairs_created += batch_stats["created"]
            log_pairs_updated += batch_stats["updated"]
            log_pairs_skipped += batch_stats["skipped"]

            progress = min(100.0, (offset / total_contacts) * 100.0) if total_contacts else 100.0
            scan_log.write({
                "processed_contacts": offset,
                "scan_offset": offset,
                "progress": round(progress, 2),
                "pairs_created": log_pairs_created,
                "pairs_updated": log_pairs_updated,
                "pairs_skipped": log_pairs_skipped,
                "total_contacts": total_contacts,
            })
            icp.set_param("duplicate_contact.scan_progress", str(round(progress, 2)))
            icp.set_param("duplicate_contact.scan_processed", str(offset))
            icp.set_param("duplicate_contact.scan_offset", str(offset))
            self.env.cr.commit()

        if not has_more:
            scan_log._mark_done(
                "Scanned %(processed)s contacts. Created %(created)s, updated %(updated)s pairs."
                % {
                    "processed": f"{offset:,}",
                    "created": scan_log.pairs_created,
                    "updated": scan_log.pairs_updated,
                }
            )
        else:
            icp.set_param("duplicate_contact.scan_active", "True")
            scan_log.write({
                "message": "Batch sync running: %s / %s contacts scanned."
                % (f"{offset:,}", f"{total_contacts:,}"),
            })

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "processed": offset,
            "total": total_contacts,
            "progress": scan_log.progress,
            "has_more": has_more,
            "scan_log_id": scan_log.id,
        }

    def _scan_partner_set(self, partners, rules, Pair, source, auto_merge=False, Merge=None):
        existing = {}
        for pair in Pair.search([("state", "in", ("open", "review"))]):
            key = self._pair_key(pair.partner_a_id.id, pair.partner_b_id.id)
            existing[key] = pair

        created = updated = skipped = 0

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
                and Merge
                and vals["confidence"] >= 99.5
                and pair.state in ("open", "review")
            ):
                survivor, duplicate = (
                    (pa, pb) if key[0] == pa.id else (pb, pa)
                )
                Merge.merge_partners(survivor, duplicate)
                pair.state = "merged"
            return pair

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
                    if pa.id == pb.id:
                        continue
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
                        "detection_source": source if source in ("manual", "cron") else "manual",
                    }
                    _upsert_pair(key, vals, pa, pb)

        return {"created": created, "updated": updated, "skipped": skipped}

    def revalidate_open_pairs(self):
        """Re-score open duplicate rows and close false positives."""
        rules = self._get_rules()
        Pair = self.env["duplicate.contact.pair"].sudo()
        cleared = updated = 0
        for pair in Pair.search([("state", "in", ("open", "review"))]):
            if pair.partner_a_id.id == pair.partner_b_id.id:
                pair.write({"state": "not_duplicate"})
                cleared += 1
                continue
            confidence, reasons = compare_partners(
                pair.partner_a_id,
                pair.partner_b_id,
                rules,
            )
            if confidence < rules["min_threshold"]:
                pair.write({"state": "not_duplicate"})
                cleared += 1
                continue
            pair.write({
                "confidence": confidence,
                "match_reasons": "\n".join("✓ %s" % r for r in reasons),
                "confidence_label": confidence_label(
                    confidence, rules["review_threshold"]
                ),
                "state": (
                    "review"
                    if confidence >= rules["review_threshold"]
                    else "open"
                ),
            })
            updated += 1
        return {"cleared": cleared, "updated": updated}
