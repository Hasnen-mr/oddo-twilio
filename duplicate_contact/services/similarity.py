# -*- coding: utf-8 -*-
"""Fuzzy and exact similarity scoring for contacts."""

from difflib import SequenceMatcher

from .normalization import (
    normalize_address_parts,
    normalize_company,
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_tax_id,
    normalize_website,
)

EXACT_CONFIDENCE = 100.0
STRONG_REASONS = {
    "Same Tax ID / GST / VAT",
    "Same Email",
    "Same Phone",
    "Same Website",
}


def _ratio(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 100.0
    return SequenceMatcher(None, a, b).ratio() * 100.0


def _token_sort_ratio(a, b):
    if not a or not b:
        return 0.0
    ta = " ".join(sorted(a.split()))
    tb = " ".join(sorted(b.split()))
    return _ratio(ta, tb)


def _jaro_winkler(s1, s2, prefix_scale=0.1):
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 100.0
    len1, len2 = len(s1), len(s2)
    match_distance = max(len1, len2) // 2 - 1
    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = s2_matches[j] = True
            matches += 1
            break
    if not matches:
        return 0.0
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1
    jaro = (
        matches / len1
        + matches / len2
        + (matches - transpositions / 2) / matches
    ) / 3.0
    prefix = 0
    for c1, c2 in zip(s1, s2):
        if c1 != c2:
            break
        prefix += 1
    return (jaro + prefix * prefix_scale * (1 - jaro)) * 100.0


def _reason(label, score):
    return "%s (%.0f%%)" % (label, score)


def compare_partners(partner_a, partner_b, rules=None):
    """Return confidence score 0-100 and list of match reason strings."""
    rules = rules or {}
    reasons = []
    scores = []
    strong_hits = 0

    def rule_on(key, default=True):
        return rules.get(key, default)

    def add_match(label, score, strong=False):
        reasons.append(_reason(label, score))
        scores.append(score)
        if strong or label in STRONG_REASONS:
            nonlocal strong_hits
            strong_hits += 1

    # Exact tax identifiers
    vat_a = normalize_tax_id(partner_a.vat)
    vat_b = normalize_tax_id(partner_b.vat)
    if rule_on("match_vat") and vat_a and vat_b and vat_a == vat_b:
        return EXACT_CONFIDENCE, ["Same Tax ID / GST / VAT (100%)"]

    # Email
    if rule_on("match_email"):
        ea = normalize_email(partner_a.email)
        eb = normalize_email(partner_b.email)
        if ea and eb and ea == eb:
            add_match("Same Email", 100.0, strong=True)

    # Phone / mobile
    if rule_on("match_phone"):
        phones_a = {
            normalize_phone(partner_a.phone),
            normalize_phone(partner_a.mobile),
        } - {""}
        phones_b = {
            normalize_phone(partner_b.phone),
            normalize_phone(partner_b.mobile),
        } - {""}
        if phones_a & phones_b:
            add_match("Same Phone", 98.0, strong=True)

    # Website
    if rule_on("match_website"):
        wa = normalize_website(partner_a.website)
        wb = normalize_website(partner_b.website)
        if wa and wb:
            if wa == wb:
                add_match("Same Website", 95.0, strong=True)
            else:
                site_score = _ratio(wa, wb)
                if site_score >= 90:
                    add_match("Very Similar Website", site_score)

    # Company name (for companies or parent)
    if rule_on("match_company"):
        ca = normalize_company(
            getattr(partner_a, "commercial_company_name", None) or partner_a.name
        )
        cb = normalize_company(
            getattr(partner_b, "commercial_company_name", None) or partner_b.name
        )
        if ca and cb and ca != cb:
            company_score = max(_token_sort_ratio(ca, cb), _jaro_winkler(ca, cb))
            if company_score >= 88:
                add_match("Similar Company Name", company_score)

    # Contact name
    if rule_on("match_name"):
        na = normalize_name(partner_a.name)
        nb = normalize_name(partner_b.name)
        if na and nb and na != nb:
            name_score = max(_token_sort_ratio(na, nb), _jaro_winkler(na, nb))
            if name_score >= 85:
                add_match("Similar Contact Name", name_score)
        elif na and nb and na == nb:
            add_match("Same Contact Name", 96.0, strong=True)

    # Address — city alone is never enough
    if rule_on("match_address"):
        street_a = (partner_a.street or "").strip()
        street_b = (partner_b.street or "").strip()
        zip_a = (partner_a.zip or "").strip()
        zip_b = (partner_b.zip or "").strip()
        if (street_a and street_b) or (zip_a and zip_b):
            aa = normalize_address_parts(street_a, partner_a.city, zip_a)
            ab = normalize_address_parts(street_b, partner_b.city, zip_b)
            if aa and ab:
                addr_score = _token_sort_ratio(aa, ab)
                if addr_score >= 85:
                    add_match("Similar Street / Address", addr_score)

    if not scores:
        return 0.0, []

    # A single weak fuzzy signal must not create a duplicate.
    if strong_hits == 0 and len(scores) == 1 and max(scores) < 92:
        return 0.0, []

    if len(scores) == 1:
        confidence = min(99.0, max(scores))
    else:
        confidence = min(
            99.0,
            sum(scores) / len(scores) + min(8, len(reasons) * 2),
        )

    if strong_hits == 0 and confidence < 90:
        return 0.0, []

    return round(confidence, 2), reasons


def confidence_label(confidence, review_threshold=90.0):
    if confidence >= 99.5:
        return "duplicate"
    if confidence >= review_threshold:
        return "possible"
    return "low"
