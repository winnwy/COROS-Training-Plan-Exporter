# COROS Training Plan Exporter to ICS

A simple web tool to convert COROS training plans into ICS calendar files for Google Calendar, Apple Calendar, Outlook, etc.

## Features

- **🔗 Direct URL Scraping**: Simply paste a COROS training plan URL (find one at [COROS Training Plans](https://coros.com/training)). No need for manual copying or developer console scripts.
- **📅 Smart Start Date**: The app aligns your start date to the correct weekday. If your plan starts on a Tuesday and you pick a Monday, it automatically shifts to the next Tuesday.
- **👀 Plan Preview**: View the calculated dates and workouts before downloading to ensure everything looks right.
- **✅ All-Day Events**: Workouts are created as all-day events at the top of your calendar for better visibility.

## Use Online
You can use the hosted version directly without installing anything:
[COROS Training Plan Exporter](https://coros-training-plan-exporter.vercel.app/)


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
    - You can get this from the COROS app or website. For example, `https://t.coros.com/schedule-plan/share?planId=447304491073716224&region=2`

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
