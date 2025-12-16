# COROS Training Plan to ICS Converter

This tool allows you to export your COROS training plan to an ICS calendar file that can be imported into Google Calendar, Apple Calendar, Outlook, etc.

## Prerequisites

- Python 3 installed
- A COROS account with a training plan

## Setup

1.  Clone the repository:
    ```bash
    git clone https://github.com/YOUR_USERNAME/coros-to-ics.git
    cd coros-to-ics
    ```
2.  Create a virtual environment:
    ```bash
    python3 -m venv venv
    ```
3.  Activate the virtual environment:
    -   **Mac/Linux:** `source venv/bin/activate`
    -   **Windows:** `venv\Scripts\activate`
4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Step 1: Get the Training Data

1.  Navigate to a training plan. You can use:
    -   **Public Plans:** [COROS Training Plans](https://coros.com/training) (no login required).
    -   **Personal Plans:** [COROS Training Hub](https://training.coros.com/).
2.  Open the Developer Tools in your browser:
    - **Chrome/Edge:** Press `F12` or right-click anywhere and select "Inspect".
    - **Safari:** Enable the Develop menu in Preferences, then press `Option + Command + C`.
3.  Go to the **Console** tab.
4.  Open the file `get_raw_data.js` in a text editor, copy all the code, and paste it into the browser console.
5.  Press **Enter**.
6.  The script will automatically copy the training data to your clipboard.
7.  Create a new file in this folder named `training_data.txt`.
8.  Paste the clipboard content into `training_data.txt` and save the file.

### Step 2: Convert to ICS

1.  Run the Python script:
    ```bash
    python convert_to_ics.py
    ```
    *(Make sure your virtual environment is activated)*
2.  The script will ask for a start date.
    - Press **Enter** to start the plan today.
    - Or enter a specific date in `YYYY-MM-DD` format (e.g., `2024-01-01`).
3.  The script will generate a file named `coros_training_plan.ics`.

### Step 3: Import to Calendar

- **Google Calendar:** Go to Settings > Import & export > Import, select `coros_training_plan.ics`.
- **Apple Calendar:** File > Import, select `coros_training_plan.ics`.
- **Outlook:** File > Open & Export > Import/Export > Import an iCalendar (.ics) or vCalendar file.
