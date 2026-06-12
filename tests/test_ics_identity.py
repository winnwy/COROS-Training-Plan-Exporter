"""Stable VEVENT identity: re-importing an updated plan updates events in place
(matched by UID) instead of duplicating; deterministic DTSTAMP keeps the same
plan version byte-identical. All offline."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import convert_to_ics as C

DOMAIN = "coros-training-plan-exporter"


def _wk(week, dow, title="Workout", date="2026-07-01"):
    return {"week": week, "day_of_week": dow, "title": title,
            "date_str": date, "date_obj": dt.datetime.strptime(date, "%Y-%m-%d"),
            "description": "", "duration": None, "distance": None, "training_load": None}


def test_assign_identity_uid_keyed_on_dayno():
    ws = [_wk(1, 0), _wk(2, 3)]
    C._assign_event_identity(ws, "PLAN1", 6, 1779108252)
    assert ws[0]["uid"] == f"PLAN1-d0@{DOMAIN}"
    assert ws[1]["uid"] == f"PLAN1-d10@{DOMAIN}"   # (2-1)*7 + 3
    assert all(w["sequence"] == 6 for w in ws)
    assert all(w["dtstamp_ts"] == 1779108252 for w in ws)


def test_assign_identity_disambiguates_multisession_day():
    ws = [_wk(1, 0, "AM"), _wk(1, 0, "PM")]
    C._assign_event_identity(ws, "P", None, None)
    assert ws[0]["uid"] == f"P-d0@{DOMAIN}"
    assert ws[1]["uid"] == f"P-d0-1@{DOMAIN}"
    assert ws[0]["uid"] != ws[1]["uid"]
    assert "sequence" not in ws[0]   # version None -> not set


def test_create_ics_is_deterministic_and_carries_identity():
    ws = [_wk(1, 0)]
    C._assign_event_identity(ws, "P", 6, 1779108252)
    a = C.create_ics_file([dict(x) for x in ws], output_file=None)
    b = C.create_ics_file([dict(x) for x in ws], output_file=None)
    assert a == b, "same plan version must regenerate a byte-identical .ics"
    assert b"UID:P-d0@" in a
    assert b"DTSTAMP:20260518T124412Z" in a   # from updateTimestamp, not wall-clock
    assert b"SEQUENCE:6" in a
    assert dt.datetime.now().strftime("%Y%m%dT").encode() not in a, "no wall-clock in output"


def test_create_ics_fallback_uid_and_fixed_dtstamp_without_plan_id():
    # legacy/no-identity dict still gets a stable hash UID + fixed sentinel DTSTAMP
    a = C.create_ics_file([_wk(1, 0, "Easy Run")], output_file=None)
    b = C.create_ics_file([_wk(1, 0, "Easy Run")], output_file=None)
    assert a == b
    assert f"@{DOMAIN}".encode() in a
    assert b"DTSTAMP:20240101T000000Z" in a


def test_identity_is_additive_existing_fields_unchanged():
    a = C.create_ics_file([_wk(1, 0, "Threshold", "2026-07-01")], output_file=None)
    assert b"SUMMARY:Threshold" in a
    assert b"DTSTART;VALUE=DATE:20260701" in a   # all-day event, unchanged
