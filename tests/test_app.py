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


# ---- /feed.ics subscription feed (offline via monkeypatch) ----

def _one_workout(url, start=None):
    return [{"week": 1, "day_of_week": 2, "title": "Feed Workout", "description": "steps",
             "duration": "30min", "distance": None, "training_load": "50",
             "date_obj": datetime.datetime(2026, 7, 1),
             "date_str": "2026-07-01", "weekday_name": "Wednesday"}]


def test_feed_returns_calendar(monkeypatch):
    monkeypatch.setattr(C, "scrape_workout_from_url", _one_workout)
    r = _client().get(f"/feed.ics?src={WURL}&start=2026-07-01")
    assert r.status_code == 200
    assert "text/calendar" in r.headers.get("Content-Type", "")
    body = r.get_data(as_text=True)
    assert "BEGIN:VEVENT" in body and "Feed Workout" in body
    # a feed must NOT force a download — calendar apps poll it in place
    assert "attachment" not in r.headers.get("Content-Disposition", "")


def test_feed_missing_src_is_400():
    assert _client().get("/feed.ics?start=2026-07-01").status_code == 400


def test_feed_bad_start_is_400():
    r = _client().get(f"/feed.ics?src={WURL}&start=nope")
    assert r.status_code == 400


def test_feed_bad_link_is_400():
    r = _client().get("/feed.ics?src=https://example.com/nope&start=2026-07-01")
    assert r.status_code == 400


def test_feed_empty_is_502(monkeypatch):
    # The scrapers swallow upstream errors into [] (can't distinguish a COROS
    # outage from a genuinely empty plan), so a feed returns 502 "retry later",
    # NOT 404 — a 404 makes Apple/Google stop refreshing the subscription.
    monkeypatch.setattr(C, "scrape_workout_from_url", lambda url, start=None: [])
    r = _client().get(f"/feed.ics?src={WURL}&start=2026-07-01")
    assert r.status_code == 502


def test_feed_upstream_failure_is_502(monkeypatch):
    # A transient COROS fetch error (not a bad link) must become a 502 so the
    # calendar app retries later, not a 4xx it would give up on.
    def _boom(url, start=None):
        raise RuntimeError("coros timed out")
    monkeypatch.setattr(A, "build_dated_workouts", _boom)
    r = _client().get(f"/feed.ics?src={WURL}&start=2026-07-01")
    assert r.status_code == 502


def test_feed_missing_start_is_400():
    # start= is REQUIRED on the feed (no silent today-default), so the plan can't
    # slide forward on each poll. The subscribe UI always bakes start= in.
    r = _client().get(f"/feed.ics?src={WURL}")
    assert r.status_code == 400


# ---- index() plan + empty-result branches (the refactor's changed paths) ----

def test_index_plan_url_renders_preview(monkeypatch):
    # The refactored index() plan branch: scrape_from_url -> real calculate_plan_dates,
    # then 'date_obj' is stripped before the workouts are embedded as JSON in the form.
    monkeypatch.setattr(C, "scrape_from_url", lambda url: [
        {"week": 1, "day_of_week": 2, "title": "Plan Run", "description": "d",
         "duration": "30min", "distance": None, "training_load": "40"}])
    r = _client().post("/", data={"plan_url": PLAN_URL, "start_date": "2026-07-01"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Plan Run" in html
    assert "2026-07-01" in html      # aligned to the Wednesday start
    assert "date_obj" not in html    # stripped from the embedded workouts_json


def test_index_empty_workout_flashes(monkeypatch):
    monkeypatch.setattr(C, "scrape_workout_from_url", lambda url, start=None: [])
    r = _client().post("/", data={"plan_url": WURL, "start_date": "2026-07-01"})
    assert "Failed to read that workout" in r.get_data(as_text=True)


def test_index_empty_plan_flashes(monkeypatch):
    monkeypatch.setattr(C, "scrape_from_url", lambda url: [])
    r = _client().post("/", data={"plan_url": PLAN_URL, "start_date": "2026-07-01"})
    assert "Failed to scrape workouts" in r.get_data(as_text=True)


# ---- build_dated_workouts branching contract (independent of the HTTP layer) ----

def test_build_dated_workouts_workout_branch_no_shift(monkeypatch):
    # A workout link self-dates to start_date and must NOT be weekday-aligned/shifted.
    monkeypatch.setattr(C, "scrape_workout_from_url",
                        lambda url, start=None: [{"title": "W", "date_obj": start,
                                                  "date_str": start.strftime("%Y-%m-%d")}])
    out = C.build_dated_workouts(WURL, datetime.datetime(2026, 7, 3))  # a Friday
    assert out[0]["date_str"] == "2026-07-03"   # unshifted


def test_build_dated_workouts_plan_branch_aligns(monkeypatch):
    # A plan link runs the real calculate_plan_dates: the first workout aligns to its
    # weekday on/after start. day_of_week=0 (Mon); first Mon on/after Wed 2026-07-01 is 07-06.
    monkeypatch.setattr(C, "scrape_from_url", lambda url: [
        {"week": 1, "day_of_week": 0, "title": "P", "description": ""}])
    out = C.build_dated_workouts(PLAN_URL, datetime.datetime(2026, 7, 1))  # a Wednesday
    assert out[0]["date_str"] == "2026-07-06"


PLAN_URL = "https://training.coros.com/schedule-plan/share?planId=99&region=1"


def test_feed_plan_path_dates_and_renders(monkeypatch):
    # The headline multi-week path: a planId link runs scrape_from_url through
    # the real calculate_plan_dates (not monkeypatched) so we exercise date
    # alignment, then renders a calendar. day_of_week=2 (Wed) on/after a Wed start.
    monkeypatch.setattr(C, "scrape_from_url", lambda url: [
        {"week": 1, "day_of_week": 2, "title": "Easy Run", "description": "d",
         "duration": "30min", "distance": None, "training_load": "40"}])
    r = _client().get(f"/feed.ics?src={PLAN_URL}&start=2026-07-01")  # 2026-07-01 is a Wed
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "BEGIN:VEVENT" in body and "Easy Run" in body
    assert "20260701" in body   # aligned to the Wednesday start, not shifted
