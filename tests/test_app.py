"""Web-endpoint tests: /generate input validation + workout routing (no network)."""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import app as A
import convert_to_ics as C
import coros_to_fit as F

WURL = "https://training.coros.com/workout-program?programId=478&region=1"


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


# ---- workout routing (offline via monkeypatch) ----

def test_index_workout_url_renders_preview(monkeypatch):
    monkeypatch.setattr(C, "scrape_workout_from_url", lambda url, start=None: [{
        "week": 1, "day_of_week": 2, "title": "My Workout", "description": "steps",
        "duration": "30min", "distance": None, "training_load": "50",
        "date_obj": datetime.datetime(2026, 7, 1),
        "date_str": "2026-07-01", "weekday_name": "Wednesday"}])
    r = _client().post("/", data={"plan_url": WURL, "start_date": "2026-07-01"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "My Workout" in html
    assert "2026-07-01" in html and "Wednesday" in html   # dated as given, no Monday shift


def test_generate_fit_workout_returns_bare_fit(monkeypatch):
    monkeypatch.setattr(F, "fit_for_workout", lambda url: ("My_Workout.fit", b"FITBYTES"))
    r = _client().post("/generate-fit", data={"plan_url": WURL})
    assert r.status_code == 200
    assert "octet-stream" in r.headers.get("Content-Type", "")
    assert "My_Workout.fit" in r.headers.get("Content-Disposition", "")
    assert r.get_data() == b"FITBYTES"


def test_generate_fit_workout_error_is_friendly(monkeypatch):
    def _raise(url):
        raise ValueError("This Swim workout can't be exported as .FIT yet — use the calendar (.ics) export.")
    monkeypatch.setattr(F, "fit_for_workout", _raise)
    r = _client().post("/generate-fit", data={"plan_url": WURL})
    assert r.status_code == 400
    assert "calendar" in r.get_data(as_text=True)


def test_index_bad_link_flashes(monkeypatch):
    r = _client().post("/", data={"plan_url": "https://example.com/nope"})
    assert "full COROS link" in r.get_data(as_text=True)
