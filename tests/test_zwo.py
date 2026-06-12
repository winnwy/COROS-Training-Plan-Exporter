"""Tests for the Zwift .ZWO exporter (coros_to_zwo). Offline — network mocked."""
import io
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import coros_decode as D
import convert_to_ics as C
import coros_to_zwo as Z

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _data(name):
    return json.load(open(os.path.join(FIX, f"{name}.json")))["data"]


def _tr():
    d = C.load_dictionary()
    return lambda k: (C.translate_key(k, d) if k else "")


def _workout(name):
    return D.decode_workout(_data(name), _tr())


# ---- ZWO validity (no official schema → well-formed + structural asserts) ----

def _assert_valid_zwo(xml):
    root = ET.fromstring(xml)                       # raises on malformed XML
    assert root.tag == "workout_file"
    assert root.findtext("sportType") in ("run", "bike")
    wk = root.find("workout")
    assert wk is not None and len(wk) > 0
    known = {"Warmup", "Cooldown", "SteadyState", "FreeRide", "IntervalsT", "Ramp", "textevent"}
    for el in wk:
        assert el.tag in known, f"unknown ZWO tag {el.tag}"
        if el.tag != "textevent":
            secs = int(el.get("Duration"))
            assert secs > 0, "Duration must be a positive int"
        for attr in ("Power", "PowerLow", "PowerHigh"):
            if el.get(attr) is not None:
                assert 0.3 <= float(el.get(attr)) <= 2.0, f"{attr} out of sane FTP range"
    return root


def test_run_pace_workout_is_freeride_no_fake_power():
    xml = Z.to_zwo(_workout("workout_run_intervals"))
    _assert_valid_zwo(xml)
    assert "<FreeRide" in xml and "Power=" not in xml, "pace workout must not emit a fake power number"
    assert "% pace" in xml, "the real pace target must be carried in a textevent note"


def test_bike_power_workout_emits_ftp_fraction():
    xml = Z.to_zwo(_workout("workout_bike_power"))
    root = _assert_valid_zwo(xml)
    assert root.findtext("sportType") == "bike"
    powered = [el for el in root.find("workout") if el.get("Power") or el.get("PowerLow")]
    assert powered, "a power workout must emit SteadyState/Warmup with an FTP fraction"


def test_repeat_groups_expand_into_repeated_steps():
    w = _workout("workout_run_intervals")
    groups = [b for b in w.blocks if isinstance(b, D.RepeatGroup)]
    assert groups, "fixture should have an interval group"
    expected = sum(g.count * len(g.steps) for g in groups) + \
        sum(1 for b in w.blocks if isinstance(b, D.Step))
    steps = [el for el in ET.fromstring(Z.to_zwo(w)).find("workout") if el.tag != "textevent"]
    assert len(steps) == expected, "RepeatGroups must expand into repeated elements"


def test_exportable_filters_to_run_bike():
    assert Z.exportable([D.Workout(index=0, sport="Swim", title="s",
                                   blocks=[D.Step(role="active", name="x", dur_kind="time", dur_value=60)])]) == []
    rb = D.Workout(index=0, sport="Run", title="r",
                   blocks=[D.Step(role="active", name="x", dur_kind="time", dur_value=60)])
    assert Z.exportable([rb]) == [rb]


# ---- end-to-end (mocked network) ----

def test_zwo_for_workout_run(monkeypatch):
    monkeypatch.setattr(Z, "fetch_program", lambda pid, region: _data("workout_run_intervals"))
    fname, xml = Z.zwo_for_workout("https://x?programId=1&region=1")
    assert fname.endswith(".zwo")
    _assert_valid_zwo(xml)


def test_zwo_for_workout_swim_raises(monkeypatch):
    monkeypatch.setattr(Z, "fetch_program", lambda pid, region: _data("workout_swim"))
    with pytest.raises(ValueError, match="run/bike only"):
        Z.zwo_for_workout("https://x?programId=1&region=1")


def test_zwo_for_workout_rejects_plan_url():
    with pytest.raises(ValueError, match="plan link"):
        Z.zwo_for_workout("https://x?planId=123")


def test_zwo_zip_for_plan(monkeypatch):
    monkeypatch.setattr(Z, "fetch_plan", lambda pid, region: _data_plan("bike_threshold"))
    data = Z.zwo_zip_for_plan("https://x?planId=1&region=1")
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    assert names and all(n.endswith(".zwo") for n in names)
    _assert_valid_zwo(zf.read(names[0]).decode("utf-8"))


def test_zwo_zip_for_plan_no_run_bike_raises(monkeypatch):
    # a plan with only a swim workout -> clear error, not an empty zip
    swim_only = {"name": "P", "programs": [_data("workout_swim")]}
    monkeypatch.setattr(Z, "fetch_plan", lambda pid, region: swim_only)
    with pytest.raises(ValueError, match="No run/bike"):
        Z.zwo_zip_for_plan("https://x?planId=1&region=1")


def _data_plan(name):
    return json.load(open(os.path.join(FIX, f"{name}.json")))["data"]
