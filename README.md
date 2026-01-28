# COROS Training Plan Exporter to ICS

A simple web tool to convert COROS training plans into ICS calendar files for Google Calendar, Apple Calendar, Outlook, etc.

## Features

- **🔗 Direct URL Scraping**: Simply paste a COROS training plan URL from [COROS Training Plans](https://coros.com/training) or any shared plan link.
- **📋 Detailed Workout Information**: Extracts specific workout names (e.g., "Aerobic run", "Easy Run with 400m Pickups") and coach's instructions from COROS API.
- **📊 Complete Workout Breakdown**: Each event includes detailed structure showing warm-up, training segments, cool-down with durations and distances.
- **📅 Smart Start Date**: Automatically aligns your start date to the correct weekday. If your plan starts on a Tuesday and you pick a Monday, it shifts to the next Tuesday.
- **👀 Plan Preview**: View calculated dates, workout titles, and detailed descriptions before downloading.
- **✅ All-Day Events**: Workouts are created as all-day events for maximum visibility in your calendar.
- **🌍 Multi-Region Support**: Works with all COROS training plans regardless of region.

## Use Online
You can use the hosted version directly without installing anything:
[COROS Training Plan Exporter](https://coros-training-plan-exporter.vercel.app/)

## Example Output

Each calendar event includes:

**Title**: `Easy Run with 400m Pickups`

**Description**:
```
The pace for the 400m pickups is up to the runner. They should 
feel smooth and controlled, but faster than your easy pace.

Workout Structure:
• Warm Up: 5min
• Training: 6.44km
• Cool Down: 5min
```

## Development / Run Locally

If you want to run the code yourself or contribute:

### Prerequisites

- Python 3.10+
- Internet connection (to fetch the plan)

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/winnwy/COROS-Training-Plan-Exporter.git
    cd COROS-Training-Plan-Exporter
    ```

2.  Create and activate a virtual environment (optional but recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Start the application:
    ```bash
    ./run.sh
    # OR
    python3 app.py
    ```

2.  Open your browser and navigate to: http://127.0.0.1:5000

3.  **Paste your COROS Plan URL**.
    - You can get this from the COROS app or website.

4.  **(Optional) Select a Start Date**.
    - Leave blank to start "today" (aligned to the plan's first weekday).
    - Pick a specific date to align the plan anchor to that week.

5.  Click **Preview Plan**.

6.  Review the schedule and click **Confirm & Download ICS**.

7.  Import the downloaded `.ics` file into your favorite calendar app.

## Development

- **`app.py`**: Flask web server handling the UI and routing.
- **`convert_to_ics.py`**: Core logic for scraping URLs, calculating dates, and generating ICS files.
- **`templates/`**: HTML frontend (`index.html`, `preview.html`).

## License

MIT
