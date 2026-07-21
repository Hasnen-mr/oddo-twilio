# -*- coding: utf-8 -*-
"""Normalize contact fields before duplicate comparison."""

import re
from urllib.parse import urlparse

_NAME_TITLES = re.compile(
    r"^(mr|mrs|ms|miss|dr|prof|sir|madam|mme|mlle)\.?\s+",
    re.IGNORECASE,
)
_NON_DIGIT = re.compile(r"\D+")


def normalize_name(value):
    if not value:
        return ""
    text = _NAME_TITLES.sub("", value.strip())
    return re.sub(r"\s+", " ", text).lower()


def normalize_email(value):
    if not value:
        return ""
    return value.strip().lower()


def normalize_phone(value, strip_country_prefix=True):
    if not value:
        return ""
    digits = _NON_DIGIT.sub("", value)
    if not digits:
        return ""
    if strip_country_prefix:
        if len(digits) > 10 and digits.startswith("91"):
            digits = digits[-10:]
        elif len(digits) > 10 and digits.startswith("1"):
            digits = digits[-10:]
        elif len(digits) > 10:
            digits = digits[-10:]
        if len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
    return digits


def normalize_website(value):
    if not value:
        return ""
    text = value.strip().lower()
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    host = (parsed.netloc or parsed.path or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip("/")


def normalize_tax_id(value):
    if not value:
        return ""
    return re.sub(r"[\s\-./]", "", value.upper())


def normalize_company(value):
    if not value:
        return ""
    text = value.lower().strip()
    replacements = (
        (r"\bprivate limited\b", "pvt ltd"),
        (r"\bprivate ltd\b", "pvt ltd"),
        (r"\blimited\b", "ltd"),
        (r"\btechnologies\b", "technology"),
        (r"\btechnology\b", "tech"),
        (r"\bincorporated\b", "inc"),
        (r"\bcorporation\b", "corp"),
    )
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_address_parts(street=False, city=False, zip_code=False):
    parts = []
    for part in (street, city, zip_code):
        if part:
            parts.append(re.sub(r"\s+", " ", str(part).strip().lower()))
    return " ".join(parts)
