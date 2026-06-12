#!/usr/bin/env python3
"""Refresh coros_dictionary.json from COROS's own web i18n bundle.

The bundled dictionary is COROS's Training Hub locale table, served as a JS
assignment:

    https://static.coros.com/locale/coros-traininghub-v2/en-US.prod.js
    -> window.en_US = { "T3001": "Training", "W30291": "...", ... }

Strip the `window.<var> =` prefix and trailing `;`, parse the object as JSON,
and that IS the dictionary. The live bundle drifts ahead of what we ship
(newer workout name-codes like W302xx), so re-pull on demand.

Usage:
    python scripts/refresh_dictionary.py            # refresh ./coros_dictionary.json
    python scripts/refresh_dictionary.py --dry-run  # report the diff, write nothing

Safety: the file is only overwritten when the freshly-parsed dictionary has at
least as many entries as the current one (the live bundle is a superset). A
short/garbled fetch never clobbers the committed dictionary.
"""
from __future__ import annotations

import argparse
import json
import os
import re

import requests

LOCALE_URL = "https://static.coros.com/locale/coros-traininghub-v2/en-US.prod.js"
DICT_PATH = os.path.join(os.path.dirname(__file__), "..", "coros_dictionary.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

_PREFIX = re.compile(r"^\s*window\.\w+\s*=\s*")


def parse_locale_bundle(text: str) -> dict:
    """Parse `window.<var> = { ... };` into a dict. Raises ValueError if the
    text isn't the expected assignment or the body isn't a JSON object."""
    m = _PREFIX.match(text)
    if not m:
        raise ValueError("not a COROS locale bundle (missing 'window.<var> =' prefix)")
    body = text[m.end():].strip().rstrip(";").strip()
    obj = json.loads(body)            # raises on malformed JSON
    if not isinstance(obj, dict) or not obj:
        raise ValueError("locale bundle did not parse to a non-empty object")
    return obj


def fetch_bundle(url: str = LOCALE_URL) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def load_existing(dict_path: str) -> dict:
    try:
        with open(dict_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def refresh_dictionary(dict_path: str = DICT_PATH, url: str = LOCALE_URL,
                       fetch=fetch_bundle, dry_run: bool = False) -> dict:
    """Fetch, parse, guard, and (unless dry_run) write the dictionary.

    Returns a summary dict {old, new, added, removed, written}. Raises
    ValueError on a bad parse or if the new dictionary is smaller than the
    current one (the shrink guard) — the existing file is left untouched.
    """
    new = parse_locale_bundle(fetch(url))
    old = load_existing(dict_path)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))

    if old and len(new) < len(old):
        raise ValueError(
            f"refusing to overwrite: parsed {len(new)} entries < current "
            f"{len(old)} (likely a bad/short fetch). File left untouched.")

    written = False
    if not dry_run:
        with open(dict_path, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, sort_keys=True, indent=2)
        written = True

    return {"old": len(old), "new": len(new),
            "added": len(added), "removed": len(removed),
            "added_keys": added, "removed_keys": removed, "written": written}


def main():
    ap = argparse.ArgumentParser(description="Refresh coros_dictionary.json from COROS locale bundle")
    ap.add_argument("--url", default=LOCALE_URL)
    ap.add_argument("--out", default=DICT_PATH)
    ap.add_argument("--dry-run", action="store_true", help="report the diff, write nothing")
    args = ap.parse_args()

    summary = refresh_dictionary(args.out, args.url, dry_run=args.dry_run)
    verb = "Would update" if args.dry_run else "Updated"
    print(f"{verb} {os.path.relpath(args.out)}: {summary['old']} -> {summary['new']} entries "
          f"(+{summary['added']}, -{summary['removed']})")
    if summary["added"]:
        sample = ", ".join(summary["added_keys"][:8])
        print(f"  new codes (sample): {sample}{' …' if summary['added'] > 8 else ''}")
    if summary["removed"]:
        print(f"  removed: {', '.join(summary['removed_keys'][:8])}")


if __name__ == "__main__":
    main()
