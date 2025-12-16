# COROS Training Plan Exporter

This tool allows you to export your COROS training plan to an ICS calendar file that can be imported into Google Calendar, Apple Calendar, Outlook, etc.

## Prerequisites

- Python 3 installed
- A COROS account with a training plan

## Usage

### Step 1: Get the Training Data

1.  Navigate to a training plan. You can use:
    -   **Public Plans:** [COROS Training Plans](https://coros.com/training) (no login required).
    -   **Personal Plans:** [COROS Training Hub](https://training.coros.com/).
2.  Open the Developer Tools in your browser:
    - **Chrome/Edge:** Press `F12` or right-click anywhere and select "Inspect".
    - **Safari:** Enable the Develop menu in Preferences, then press `Option + Command + C`.
3.  Go to the **Console** tab.
4.  Copy the code from [get_raw_data.js](https://github.com/winnwy/COROS-Training-Plan-Exporter/blob/main/get_raw_data.js) and paste it into the browser console.
5.  Press **Enter**.
6.  The script will automatically copy the training data to your clipboard.

### Step 2: Generate ICS File

1.  Open the [COROS Training Plan Exporter](https://coros-training-plan-exporter.vercel.app/).
2.  Paste the training data into the text area.
3.  (Optional) Enter a start date.
4.  Click **Download ICS**.

### Step 3: Import to Calendar

- **Google Calendar:** Go to Settings > Import & export > Import, select `coros_training_plan.ics`.
- **Apple Calendar:** File > Import, select `coros_training_plan.ics`.
- **Outlook:** File > Open & Export > Import/Export > Import an iCalendar (.ics) or vCalendar file.

## Development

To run the project locally:

1.  Clone the repository.
2.  Install dependencies: `pip install -r requirements.txt`.
3.  Run the app: `python app.py`.

