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


def compare_partners(partner_a, partner_b, rules=None):
    """Return confidence score 0-100 and list of match reason strings."""
    rules = rules or {}
    reasons = []
    scores = []

    def rule_on(key, default=True):
        return rules.get(key, default)

    # Exact tax identifiers
    vat_a = normalize_tax_id(partner_a.vat)
    vat_b = normalize_tax_id(partner_b.vat)
    if rule_on("match_vat") and vat_a and vat_b and vat_a == vat_b:
        return EXACT_CONFIDENCE, ["Same Tax ID / GST / VAT"]

    # Email
    if rule_on("match_email"):
        ea = normalize_email(partner_a.email)
        eb = normalize_email(partner_b.email)
        if ea and eb:
            if ea == eb:
                reasons.append("Same Email")
                scores.append(100.0)
            elif ea.split("@")[-1] == eb.split("@")[-1]:
                scores.append(75.0)

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
            reasons.append("Same Phone")
            scores.append(98.0)

    # Website
    if rule_on("match_website"):
        wa = normalize_website(partner_a.website)
        wb = normalize_website(partner_b.website)
        if wa and wb:
            if wa == wb:
                reasons.append("Same Website")
                scores.append(95.0)
            else:
                site_score = _ratio(wa, wb)
                if site_score >= 85:
                    scores.append(site_score)

    # Company name (for companies or parent)
    if rule_on("match_company"):
        ca = normalize_company(partner_a.commercial_company_name or partner_a.name)
        cb = normalize_company(partner_b.commercial_company_name or partner_b.name)
        if ca and cb:
            company_score = max(_token_sort_ratio(ca, cb), _jaro_winkler(ca, cb))
            if company_score >= 80:
                reasons.append("Similar Company")
                scores.append(company_score)

    # Contact name
    if rule_on("match_name"):
        na = normalize_name(partner_a.name)
        nb = normalize_name(partner_b.name)
        if na and nb:
            name_score = max(_token_sort_ratio(na, nb), _jaro_winkler(na, nb))
            if name_score >= 75:
                reasons.append("Similar Name")
                scores.append(name_score)

    # Address
    if rule_on("match_address"):
        aa = normalize_address_parts(partner_a.street, partner_a.city, partner_a.zip)
        ab = normalize_address_parts(partner_b.street, partner_b.city, partner_b.zip)
        if aa and ab:
            addr_score = _token_sort_ratio(aa, ab)
            if addr_score >= 80:
                reasons.append("Similar Address")
                scores.append(addr_score)

    if not scores:
        return 0.0, []

    confidence = min(99.0, max(scores)) if len(scores) == 1 else min(
        99.0, sum(scores) / len(scores) + min(10, len(reasons) * 3)
    )
    return round(confidence, 2), reasons


def confidence_label(confidence, review_threshold=90.0):
    if confidence >= 99.5:
        return "duplicate"
    if confidence >= review_threshold:
        return "possible"
    return "low"
