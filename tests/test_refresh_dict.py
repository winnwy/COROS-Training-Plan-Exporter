"""Tests for scripts/refresh_dictionary.py — bundle parsing + shrink guard.

Offline only: the network fetch is injected, so these never hit COROS.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import refresh_dictionary as R


def test_parse_locale_bundle_ok():
    txt = 'window.en_US={\n  "T3001": "Training",\n  "W1": "Hi"\n};'
    assert R.parse_locale_bundle(txt) == {"T3001": "Training", "W1": "Hi"}


def test_parse_locale_bundle_handles_trailing_semicolon_and_whitespace():
    assert R.parse_locale_bundle('  window.zh_CN = {"A":"x"}  ;  ') == {"A": "x"}


def test_parse_locale_bundle_rejects_non_bundle():
    # plain JSON with no `window.<var> =` assignment prefix
    with pytest.raises(ValueError):
        R.parse_locale_bundle('{"T3001": "Training"}')


def test_parse_locale_bundle_rejects_garbage_body():
    # json.JSONDecodeError is a subclass of ValueError
    with pytest.raises(ValueError):
        R.parse_locale_bundle("window.en_US={ not json ;")


def test_parse_locale_bundle_rejects_empty_object():
    with pytest.raises(ValueError):
        R.parse_locale_bundle("window.en_US={}")


def test_parse_locale_bundle_tolerates_sourcemap_trailer():
    # production .prod.js bundles often append a source-map comment after `};`
    txt = 'window.en_US={"A":"x","B":"y"};\n//# sourceMappingURL=en-US.prod.js.map\n'
    assert R.parse_locale_bundle(txt) == {"A": "x", "B": "y"}


def test_refresh_shrink_guard_refuses_and_leaves_file(tmp_path):
    p = tmp_path / "dict.json"
    p.write_text(json.dumps({"A": "1", "B": "2", "C": "3"}))
    fetch = lambda url: 'window.en_US={"A":"1","B":"2"}'   # 2 < 3 -> refuse
    with pytest.raises(ValueError):
        R.refresh_dictionary(str(p), fetch=fetch)
    assert json.loads(p.read_text()) == {"A": "1", "B": "2", "C": "3"}  # untouched


def test_refresh_near_superset_guard_refuses_locale_swap(tmp_path):
    # equal-or-larger count but mostly-different keys (e.g. wrong locale served
    # at the same URL) must be refused — count alone wouldn't catch it.
    p = tmp_path / "dict.json"
    p.write_text(json.dumps({f"K{i}": "en" for i in range(100)}))
    # 100 brand-new keys, all 100 old ones removed -> way over the 10% threshold
    swap = "window.en_US={" + ",".join(f'"Z{i}":"zh"' for i in range(100)) + "}"
    with pytest.raises(ValueError, match="removed"):
        R.refresh_dictionary(str(p), fetch=lambda url: swap)
    assert "K0" in json.loads(p.read_text())   # untouched


def test_refresh_writes_superset(tmp_path):
    p = tmp_path / "dict.json"
    p.write_text(json.dumps({"A": "1"}))
    fetch = lambda url: 'window.en_US={"A":"1","B":"2"}'
    summary = R.refresh_dictionary(str(p), fetch=fetch)
    assert summary["written"] and summary["added"] == 1 and summary["removed"] == 0
    assert json.loads(p.read_text()) == {"A": "1", "B": "2"}


def test_refresh_dry_run_writes_nothing(tmp_path):
    p = tmp_path / "dict.json"
    p.write_text(json.dumps({"A": "1"}))
    fetch = lambda url: 'window.en_US={"A":"1","B":"2"}'
    summary = R.refresh_dictionary(str(p), fetch=fetch, dry_run=True)
    assert summary["added"] == 1 and not summary["written"]
    assert json.loads(p.read_text()) == {"A": "1"}   # unchanged
