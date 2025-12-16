from flask import Flask, render_template, request, send_file, flash
from convert_to_ics import parse_training_data, create_ics_file
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for flash messages

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        training_data = request.form.get('training_data')
        start_date_str = request.form.get('start_date')
        
        if not training_data:
            flash('Please paste your training data.', 'error')
            return render_template('index.html')
            
        try:
            workouts = parse_training_data(training_data)
            if not workouts:
                flash('No workouts found in the data. Please check the format.', 'error')
                return render_template('index.html')
                
            start_date = None
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(hour=6, minute=0, second=0, microsecond=0)
                except ValueError:
                    pass # Default to today if invalid
            
            ics_bytes = create_ics_file(workouts, start_date=start_date, output_file=None)
            
            return send_file(
                io.BytesIO(ics_bytes),
                as_attachment=True,
                download_name='coros_training_plan.ics',
                mimetype='text/calendar'
            )
            
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return render_template('index.html')

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
