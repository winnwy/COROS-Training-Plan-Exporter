"""Web-endpoint tests: /generate input validation (no network)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import app as A


def _client():
    A.app.testing = True
    return A.app.test_client()


def test_generate_rejects_non_list():
    r = _client().post("/generate", data={"workouts_json": "{}"})
    assert r.status_code == 400


def test_generate_rejects_missing_title():
    body = json.dumps([{"date_str": "2026-07-01"}])
    assert _client().post("/generate", data={"workouts_json": body}).status_code == 400


def test_generate_rejects_bad_date():
    body = json.dumps([{"title": "X", "date_str": "not-a-date"}])
    assert _client().post("/generate", data={"workouts_json": body}).status_code == 400


def test_generate_rejects_empty():
    assert _client().post("/generate", data={}).status_code == 400


def test_generate_ok_minimal():
    body = json.dumps([{"title": "Easy Run", "date_str": "2026-07-01",
                        "description": "", "duration": None, "distance": None,
                        "training_load": None}])
    r = _client().post("/generate", data={"workouts_json": body})
    assert r.status_code == 200
    assert "calendar" in r.headers.get("Content-Type", "")
