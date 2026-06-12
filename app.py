from flask import Flask, render_template, request, send_file, flash
from convert_to_ics import parse_training_data, create_ics_file
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
            # Import the updated scraper with dictionary translation
            # scrape_from_url now uses API and translates workout names/descriptions automatically
            from convert_to_ics import (scrape_from_url, scrape_workout_from_url,
                                        parse_coros_url, calculate_plan_dates)
            import json

            # Determine start date first (the workout path dates at scrape time)
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

            if kind == "workout":
                # Single undated workout: scrape_workout_from_url already dates it
                # to start_date — do NOT run calculate_plan_dates (it would force
                # the day to Monday and shift the date).
                workouts_with_dates = scrape_workout_from_url(plan_url, start_date)
                if not workouts_with_dates:
                    flash('Failed to read that workout. Please check the link.', 'error')
                    return render_template('index.html')
            else:
                workouts = scrape_from_url(plan_url)
                if not workouts:
                    flash('Failed to scrape workouts. Please check the URL.', 'error')
                    return render_template('index.html')
                # Calculate Preview Dates
                workouts_with_dates = calculate_plan_dates(workouts, start_date)

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


if __name__ == '__main__':
    # debug off by default; opt in locally with FLASK_DEBUG=1
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
