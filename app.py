from flask import Flask, render_template, request, send_file, flash
from convert_to_ics import parse_training_data, create_ics_file
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for flash messages

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        plan_url = request.form.get('plan_url')
        start_date_str = request.form.get('start_date')
        
        if not plan_url:
            flash('Please enter a COROS Training Plan URL.', 'error')
            return render_template('index.html')
            
        try:
            from convert_to_ics import scrape_from_url, calculate_plan_dates
            import json
            
            workouts = scrape_from_url(plan_url)
            if not workouts:
                flash('Failed to scrape workouts. Please check the URL.', 'error')
                return render_template('index.html')
            
            # Determine start date
            start_date = None
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                except ValueError:
                    pass
            
            if start_date is None:
                start_date = datetime.now()
                
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
                                   total_workouts=len(workouts),
                                   total_weeks=total_weeks,
                                   workouts_json=workouts_json)
            
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            import traceback
            traceback.print_exc()
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
        
        # Re-hydrate date objects for create_ics_file
        for w in workouts:
            if 'date_str' in w:
                w['date_obj'] = datetime.strptime(w['date_str'], '%Y-%m-%d')
        
        ics_bytes = create_ics_file(workouts, output_file=None)
        
        return send_file(
            io.BytesIO(ics_bytes),
            as_attachment=True,
            download_name='coros_training_plan.ics',
            mimetype='text/calendar'
        )
    except Exception as e:
        return f"Error generating ICS: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
