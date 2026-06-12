from flask import Flask, render_template, request, send_file, flash, Response
from convert_to_ics import parse_training_data, create_ics_file, build_dated_workouts
from datetime import datetime
import io
import os

app = Flask(__name__)
# Only used to sign flash-message cookies (no auth/session data). Override in prod.
app.secret_key = os.environ.get('SECRET_KEY', 'dev-flash-key')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        plan_url = request.form.get('plan_url')
        start_date_str = request.form.get('start_date')
        
        if not plan_url:
            flash('Please enter a COROS Training Plan URL.', 'error')
            return render_template('index.html')
            
        try:
            import json
            from convert_to_ics import parse_coros_url

            # Determine the start date first; it's passed into build_dated_workouts below.
            start_date = None
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                except ValueError:
                    pass
            if start_date is None:
                start_date = datetime.now()

            # A workout link self-identifies (programId vs planId). Bad links
            # raise ValueError, which we surface as a friendly message.
            try:
                kind, _id, _region = parse_coros_url(plan_url)
            except ValueError as e:
                flash(str(e), 'error')
                return render_template('index.html')

            # One shared path to a dated workout list — preview, download and the
            # subscription feed all run through build_dated_workouts, so they agree.
            workouts_with_dates = build_dated_workouts(plan_url, start_date)
            if not workouts_with_dates:
                flash('Failed to read that workout. Please check the link.' if kind == "workout"
                      else 'Failed to scrape workouts. Please check the URL.', 'error')
                return render_template('index.html')

            # Prepare data for preview
            total_weeks = max((w.get('week', 1) for w in workouts_with_dates), default=0)
            
            # Serialize for hidden input
            # We need to serialize the dates as strings for JSON
            # But the preview template needs the objects? No, preview template uses .date_str which is in the dict
            # calculate_plan_dates adds 'date_str', 'weekday_name', 'date_obj'
            # We must remove 'date_obj' before json dumping or use a custom encoder
            
            json_workouts = []
            for w in workouts_with_dates:
                w_safe = w.copy()
                if 'date_obj' in w_safe:
                    del w_safe['date_obj']
                json_workouts.append(w_safe)
            
            workouts_json = json.dumps(json_workouts)
            
            return render_template('preview.html',
                                   workouts=workouts_with_dates,
                                   start_date=start_date.strftime('%Y-%m-%d'),
                                   total_workouts=len(workouts_with_dates),
                                   total_weeks=total_weeks,
                                   workouts_json=workouts_json,
                                   plan_url=plan_url)
            
        except Exception as e:
            import traceback
            traceback.print_exc()   # server-side log
            flash('Something went wrong reading that plan. Check the URL and try again.', 'error')
            return render_template('index.html')

    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        import json
        workouts_json = request.form.get('workouts_json')
        
        if not workouts_json:
            return "Error: No workout data provided", 400
            
        workouts = json.loads(workouts_json)

        # Validate shape (this is a public endpoint; the field is POST-able directly)
        if not isinstance(workouts, list) or not all(isinstance(w, dict) for w in workouts):
            return "Invalid workout data.", 400
        for w in workouts:
            if 'title' not in w:
                return "Invalid workout data: missing title.", 400
            ds = w.get('date_str')
            if ds is not None:
                try:
                    w['date_obj'] = datetime.strptime(str(ds), '%Y-%m-%d')
                except ValueError:
                    return "Invalid workout data: bad date.", 400
        
        ics_bytes = create_ics_file(workouts, output_file=None)
        
        return send_file(
            io.BytesIO(ics_bytes),
            as_attachment=True,
            download_name='coros_training_plan.ics',
            mimetype='text/calendar'
        )
    except Exception:
        import traceback
        traceback.print_exc()   # server-side log; don't leak internals to client
        return "Sorry, we couldn't generate the calendar from that data.", 500


@app.route('/generate-fit', methods=['POST'])
def generate_fit():
    """Build Garmin .FIT workout files (run/bike) and return them as a .zip."""
    plan_url = request.form.get('plan_url')
    if not plan_url:
        return "Error: No plan URL provided", 400
    try:
        import coros_to_fit
        from convert_to_ics import parse_coros_url
        kind, _id, _region = parse_coros_url(plan_url)
        if kind == "workout":
            # one workout -> bare .fit (no zip to unzip for a single file)
            filename, fit_bytes = coros_to_fit.fit_for_workout(plan_url)
            return send_file(
                io.BytesIO(fit_bytes),
                as_attachment=True,
                download_name=filename,
                mimetype='application/octet-stream'
            )
        zip_bytes = coros_to_fit.fit_zip_for_plan(plan_url)
        return send_file(
            io.BytesIO(zip_bytes),
            as_attachment=True,
            download_name='coros_garmin_workouts.zip',
            mimetype='application/zip'
        )
    except ValueError as e:
        # our own message (e.g. "No run/bike/strength workouts ..."), safe to show
        return f"Could not build Garmin workouts: {str(e)}", 400
    except Exception:
        import traceback
        traceback.print_exc()   # server-side log; don't leak internals to client
        return "Sorry, we couldn't build the Garmin workouts.", 500


@app.route('/feed.ics', methods=['GET'])
def feed():
    """Auto-updating calendar feed for webcal:// subscriptions (optional).

    Stateless by design (no DB, Vercel-friendly): the subscription URL carries
    everything — the COROS link (src=) and a required, baked-in start date
    (start=). The start date is fixed in the URL on purpose: defaulting it would
    slide the whole plan forward every time the calendar app refreshed, so a
    missing start= is a 400 rather than a silent today-default.

    Calendar apps poll this on THEIR schedule (a few hours up to a day — not
    instant), so we re-fetch COROS and rebuild the .ics each time. Stable
    per-event UIDs (see create_ics_file) mean those refreshes update events in
    place rather than duplicating them.
    """
    src = request.args.get('src')
    if not src:
        return "Missing 'src' (the COROS plan or workout link).", 400

    # start= is REQUIRED, not defaulted. Defaulting to today would re-anchor the
    # plan to 'now' on every poll — the exact sliding-forward drift the baked-in
    # start date exists to prevent. The subscribe UI always bakes it in, so this
    # only rejects malformed/hand-edited URLs.
    start_str = request.args.get('start')
    if not start_str:
        return "Missing 'start' date (YYYY-MM-DD) — the feed needs a fixed start so the plan doesn't drift.", 400
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
    except ValueError:
        return "Bad 'start' date — expected YYYY-MM-DD.", 400

    try:
        workouts = build_dated_workouts(src, start_date)
    except ValueError as e:
        # unrecognized link — caller's fault, won't fix itself on retry
        return str(e), 400
    except Exception:
        import traceback
        traceback.print_exc()   # server-side log
        # transient upstream failure: 502 so the calendar app retries later
        return "Couldn't reach COROS to refresh this calendar.", 502

    # No workouts means the fetch came back empty. The scrapers swallow upstream
    # errors (timeout/500/DNS) into [] (see scrape_from_url), so for a feed we
    # CANNOT tell a transient outage from a genuinely empty plan — and both should
    # tell the calendar client "retry later, keep what you have." A 404 would make
    # Apple/Google treat the subscription as gone and stop refreshing; a 200-empty
    # would wipe every event. 502 is the only safe answer for a live feed.
    if not workouts:
        return "Couldn't read any workouts from COROS right now — the calendar will retry.", 502

    ics_bytes = create_ics_file(workouts, output_file=None)
    return Response(
        ics_bytes,
        mimetype='text/calendar',
        headers={
            'Content-Type': 'text/calendar; charset=utf-8',
            # per-user plan content: keep it out of shared edge caches. Clients
            # poll on their own cadence, so an hour of private caching is plenty.
            'Cache-Control': 'private, max-age=3600',
        },
    )


if __name__ == '__main__':
    # debug off by default; opt in locally with FLASK_DEBUG=1
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
