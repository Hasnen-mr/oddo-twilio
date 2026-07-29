#!/usr/bin/env python3
"""Prepare twilio_dialer version_info.json from recent git commits.

Usage (from repo root):
  python3 scripts/prepare_version_info.py
  python3 scripts/prepare_version_info.py --since HEAD~10
  python3 scripts/prepare_version_info.py --version 18.0.1.2.63

Reads the current module version from __manifest__.py unless --version is set.
Writes twilio_dialer/static/description/version_info.json with an auto-built
feature list derived from git commit subjects.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "twilio_dialer" / "__manifest__.py"
OUT = ROOT / "twilio_dialer" / "static" / "description" / "version_info.json"

SKIP_PREFIXES = (
    "merge ",
    "set module version",
    "bump version",
    "wip ",
)


def read_manifest_version() -> str:
    text = MANIFEST.read_text(encoding="utf-8")
    match = re.search(r"['\"]version['\"]\s*:\s*['\"]([^'\"]+)['\"]", text)
    if not match:
        raise SystemExit("Could not find version in __manifest__.py")
    return match.group(1)


def git_subjects(since: str) -> list[str]:
    raw = subprocess.check_output(
        ["git", "log", "--pretty=%s", since],
        cwd=ROOT,
        text=True,
    )
    subjects = []
    for line in raw.splitlines():
        subject = line.strip()
        if not subject:
            continue
        lower = subject.lower()
        if any(lower.startswith(p) for p in SKIP_PREFIXES):
            continue
        # Prefer sentence-style features
        if subject[0].islower():
            subject = subject[0].upper() + subject[1:]
        if subject not in subjects:
            subjects.append(subject)
    return subjects[:12]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Override module version")
    parser.add_argument(
        "--since",
        default="HEAD~15",
        help="git log range start (default: HEAD~15)",
    )
    parser.add_argument(
        "--message",
        default=(
            "A newer version of Twilio Dialer is available. "
            "Update from Apps to get the latest improvements."
        ),
    )
    args = parser.parse_args()

    version = args.version or read_manifest_version()
    features = git_subjects(args.since)
    if not features:
        features = ["Bug fixes and performance improvements"]

    existing: dict = {}
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    changelog = existing.get("changelog") or {}
    if not isinstance(changelog, dict):
        changelog = {}
    changelog[version] = features

    payload = {
        "module": "twilio_dialer",
        "version": version,
        "title": "New Version Available",
        "message": args.message,
        "release_date": date.today().isoformat(),
        "download_url": existing.get("download_url")
        or "https://apps.odoo.com/apps/modules/19.0/twilio_dialer",
        "features": features,
        "changelog": changelog,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"version: {version}")
    for item in features:
        print(f"  - {item}")


if __name__ == "__main__":
    main()
