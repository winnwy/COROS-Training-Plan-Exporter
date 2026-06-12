#!/usr/bin/env python3
"""
Convert COROS training plan data to ICS calendar format.
Reads data from 'training_data.txt' OR scrapes from a COROS URL.
"""

import os
import re
import sys
import json
import requests
from datetime import datetime, timedelta, date
from urllib.parse import urlparse, parse_qs
try:
    from icalendar import Calendar, Event, vCalAddress, vText
except ImportError:
    print("❌ Error: 'icalendar' library not found.")
    print("   Please run: pip install icalendar")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Error: 'beautifulsoup4' library not found.")
    print("   Please run: pip install beautifulsoup4")
    # We don't exit here as the user might just want to use the text method

# Global dictionary cache
_DICTIONARY_CACHE = None

def load_dictionary(dict_file=None):
    """Load the COROS dictionary file for translating keys to natural language.

    Resolve relative to this module (not the cwd) so the CLI translates
    correctly when run from any directory."""
    global _DICTIONARY_CACHE
    if _DICTIONARY_CACHE is not None:
        return _DICTIONARY_CACHE

    if dict_file is None:
        dict_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coros_dictionary.json')

    try:
        with open(dict_file, 'r', encoding='utf-8') as f:
            _DICTIONARY_CACHE = json.load(f)
            return _DICTIONARY_CACHE
    except FileNotFoundError:
        print(f"⚠️  Warning: Dictionary file '{dict_file}' not found. Workout names won't be translated.")
        return {}
    except json.JSONDecodeError:
        print(f"⚠️  Warning: Invalid dictionary file. Workout names won't be translated.")
        return {}

def translate_key(key, dictionary, max_length=None):
    """Translate a dictionary key to natural language"""
    translation = dictionary.get(key, key)
    if max_length and len(translation) > max_length:
        translation = translation[:max_length] + '...'
    return translation

def load_training_data(filename='training_data.txt'):
    """Load training data from text file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{filename}'")
        print("   Please follow the instructions in README.md to create this file.")
        sys.exit(1)

def day_no_to_week_dow(day_no):
    """Map a COROS absolute day index (`dayNo`, 0-based across the whole plan:
    0,1,2,…) to (week, day_of_week), both used by calculate_plan_dates.

    Invariant: (week - 1) * 7 + day_of_week == day_no  (must hold for all dayNo,
    or workout dates drift — see tests/test_dates.py). day_of_week is the weekday
    only under a Monday plan-start; calculate_plan_dates re-anchors to the user's
    chosen start date afterward.
    """
    return (day_no // 7) + 1, day_no % 7


def parse_coros_url(url):
    """Classify a COROS link as a workout or a plan and pull its id + region.

    Returns (kind, id, region) where kind is 'workout' or 'plan'. Workout
    links carry programId= (or workoutId=); plan links carry planId=. A bare
    number or anything else raises ValueError — the link self-identifies, so we
    don't guess by double-fetching (see docs/WORKOUT_EXPORT_PLAN.md D1).

    Reads the URL's actual top-level query params (not a substring match on the
    whole URL) so an id nested in a redirect/next= value can't hijack the
    classification, and planId wins over programId when both are present — a
    planId is the unambiguous "this is a plan" signal.
    """
    q = parse_qs(urlparse(url or "").query)
    region = q.get("region", ["1"])[0]
    if "planId" in q:
        return ("plan", q["planId"][0], region)
    if "programId" in q:
        return ("workout", q["programId"][0], region)
    if "workoutId" in q:
        return ("workout", q["workoutId"][0], region)
    raise ValueError(
        "Couldn't find a workout or plan id in that link. Paste the full COROS "
        "link — it should contain planId= (a plan) or programId= (a workout).")


def scrape_workout_from_url(url, start_date=None):
    """Fetch a single COROS workout (program/detail) and return a one-element
    list shaped like create_ics_file expects — dated to start_date (default
    today), no week/day alignment (a workout has no schedule)."""
    kind, workout_id, region = parse_coros_url(url)   # raises ValueError on bad input
    if kind != "workout":
        # a plan link slipped in here — defer to the plan path
        return scrape_from_url(url)

    dictionary = load_dictionary()
    api_url = "https://teamapi.coros.com/training/program/detail"
    params = {'id': workout_id, 'region': region}
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
    }
    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=25)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Error fetching workout from API: {e}")
        return []

    program = data.get('data')
    if not program:
        print("❌ Error: Invalid API response")
        return []

    import coros_decode
    tr = lambda k: (translate_key(k, dictionary) if k else "")
    w = coros_decode.decode_workout(program, tr)
    # create_ics_file prints its own Distance/Duration/TL, so suppress the
    # decoder's summary line to avoid duplicating them (include_summary=False).
    description = coros_decode.format_description(w, include_summary=False) or w.overview or ""

    if start_date is None:
        start_date = datetime.now()
    # week=1 + day_of_week=the chosen weekday so that even if a caller runs this
    # through calculate_plan_dates, the anchor shift is 0 and the date stays put
    # (the web path skips alignment outright). date_obj is honoured directly by
    # create_ics_file.
    return [{
        'week': 1,
        'day_of_week': start_date.weekday(),
        'title': w.title,
        'description': description,
        'duration': f"{w.duration_s // 60}min" if w.duration_s else None,
        'distance': f"{w.distance_m / 1000:.2f} km" if w.distance_m else None,
        'training_load': str(w.training_load) if w.training_load else None,
        'date_obj': start_date,
        'date_str': start_date.strftime('%Y-%m-%d'),
        'weekday_name': start_date.strftime('%A'),
    }]


def scrape_from_url(url):
    """Fetch training plan from COROS API and translate dictionary keys"""
    # Extract plan ID and region from URL
    plan_id_match = re.search(r'planId=([0-9]+)', url)
    region_match = re.search(r'region=([0-9]+)', url)
    
    if not plan_id_match:
        print("❌ Error: Could not extract plan ID from URL")
        return []
    
    plan_id = plan_id_match.group(1)
    region = region_match.group(1) if region_match else "1"
    
    # Load dictionary for translations
    dictionary = load_dictionary()
    
    # Fetch from API
    api_url = f"https://teamapi.coros.com/training/plan/detail"
    params = {
        'supportRestExercise': '1',
        'id': plan_id,
        'region': region
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
    }
    
    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=25)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Error fetching training plan from API: {e}")
        return []
    
    if 'data' not in data or 'entities' not in data['data']:
        print("❌ Error: Invalid API response")
        return []
    
    workouts = []
    entities = data['data']['entities']
    # Build programs dict keyed by idInPlan (entities reference programs by idInPlan, not by index)
    programs = {prog.get('idInPlan'): prog for prog in data['data'].get('programs', []) if prog.get('idInPlan')}

    # Rich per-workout detail via the shared decoder (run/bike). Falls back to
    # the legacy per-entity rendering below for other sports / older payloads.
    try:
        import coros_decode
        _tr = lambda k: (translate_key(k, dictionary) if k else "")
        _decoded = coros_decode.decode_plan(data['data'], _tr)
        _rich_by_id = {w.id_in_plan: w for w in _decoded.workouts if w.id_in_plan is not None}
    except Exception as e:
        print(f"⚠️  Rich decoder unavailable, using basic rendering: {e}")
        coros_decode, _rich_by_id = None, {}
    
    # Calculate which week each day belongs to (7 days per week)
    for entity in entities:
        day_no = entity.get('dayNo') or 0   # missing/None/0 -> plan day 0
        week, day_of_week = day_no_to_week_dow(day_no)
        
        # Get program info for this entity using idInPlan
        entity_id_in_plan = entity.get('idInPlan')
        program = programs.get(entity_id_in_plan, {})
        
        # Get detailed workout name from program  
        workout_name_key = program.get('name', '')
        workout_overview_key = program.get('overview', '')
        workout_title = translate_key(workout_name_key, dictionary) if workout_name_key else None
        workout_overview = translate_key(workout_overview_key, dictionary) if workout_overview_key else None
        
        # Check if there's exerciseBarChart data (new API format)
        exercise_bar_chart = entity.get('exerciseBarChart', [])
        
        # Also check for old sport format for backwards compatibility
        sport = entity.get('sport')

        # Decoded rich workout for this day (run/bike/strength/hybrid)
        rich = _rich_by_id.get(entity_id_in_plan) if coros_decode else None

        if not exercise_bar_chart and not sport:
            # No bar-chart/sport summary (e.g. strength plans). If the decoder has
            # rich blocks for this program, build the event entirely from it.
            if rich is not None and rich.has_structure:
                rich_desc = coros_decode.format_description(rich, include_summary=False)
                workouts.append({
                    'week': week,
                    'day_of_week': day_of_week,
                    'title': rich.title or workout_title or 'Workout',
                    'description': rich_desc or (workout_overview or ''),
                    'duration': f"{rich.duration_s // 60}min" if rich.duration_s else None,
                    'distance': f"{rich.distance_m / 1000:.2f} km" if rich.distance_m else None,
                    'training_load': str(rich.training_load) if rich.training_load else None,
                })
            # else: genuinely no workout data, skip
            continue

        # Parse based on which format is available
        if exercise_bar_chart:
            # New format: parse from exerciseBarChart
            exercise_details = []
            total_duration = 0
            total_distance = 0
            training_exercises = []  # Track non-warmup/cooldown exercises
            
            for exercise in exercise_bar_chart:
                ex_name_key = exercise.get('name', '')
                ex_name = translate_key(ex_name_key, dictionary)
                
                # Format target (time or distance)
                target_type = exercise.get('targetType')
                target_value = exercise.get('targetValue', 0)
                
                if target_type == 2:  # Time
                    total_duration += target_value
                    target = f"{target_value // 60}min" if target_value >= 60 else f"{target_value}s"
                elif target_type == 5:  # Distance
                    total_distance += target_value
                    target = f"{target_value / 100000:.2f}km"
                else:
                    target = ""
                
                if ex_name and target:
                    exercise_details.append(f"{ex_name}: {target}")
                    # Track training segments (exclude warm up and cool down)
                    if ex_name not in ['Warm Up', 'Cool Down']:
                        training_exercises.append({
                            'name': ex_name,
                            'target_type': target_type,
                            'target_value': target_value,
                            'distance': target_value if target_type == 5 else 0
                        })
            
            # Build title - use program name if available, otherwise build from components
            if workout_title:
                # Use the detailed workout name from programs
                title = workout_title
            else:
                # Fallback: build title from actual workout components 
                title_parts = []
                for detail in exercise_details[:5]:  # Limit to first 5 components for readability
                    title_parts.append(detail.replace(": ", " "))
                
                if len(exercise_details) > 5:
                    title = " + ".join(title_parts) + f" + {len(exercise_details) - 5} more"
                elif title_parts:
                    title = " + ".join(title_parts)
                else:
                    title = "Workout"
            
            # Build description with overview and component breakdown
            description = workout_overview if workout_overview else ""
            
            # Always add workout structure breakdown
            if exercise_details:
                if description:
                    description += "\n\n"
                description += "Workout Structure:\n" + "\n".join([f"• {d}" for d in exercise_details])
            
            # Strip any leading/trailing whitespace
            description = description.strip()
            
            duration = f"{total_duration // 60}min" if total_duration > 0 else None
            distance = f"{total_distance / 100000:.2f} km" if total_distance > 0 else None
            training_load = None  # Not available in exerciseBarChart format
            
        else:
            # Old format: parse from sport object
            workout_name_key = sport.get('name', '')
            workout_overview_key = sport.get('overview', '')
            
            title = translate_key(workout_name_key, dictionary) if workout_name_key else "Workout"
            description = translate_key(workout_overview_key, dictionary) if workout_overview_key else ""
            
            # Convert distance and duration
            distance_cm = sport.get('distance', 0)
            duration_sec = sport.get('duration', 0)
            training_load = sport.get('trainingLoad', 0)
            
            # Build exercise details
            exercise_details = []
            for exercise in sport.get('exercises', []):
                ex_name_key = exercise.get('name', '')
                ex_name = translate_key(ex_name_key, dictionary)
                
                # Format target (time or distance)
                target_type = exercise.get('targetType')
                target_value = exercise.get('targetValue', 0)
                
                if target_type == 2:  # Time
                    target = f"{target_value // 60}min" if target_value >= 60 else f"{target_value}s"
                elif target_type == 5:  # Distance
                    target = f"{target_value / 100000:.2f}km"
                else:
                    target = ""
                
                # Format intensity
                intensity_type = exercise.get('intensityType', 0)
                intensity_str = ""
                if intensity_type == 3:  # Pace
                    intensity_pct = exercise.get('intensityPercent', 0) / 1000
                    intensity_pct_ext = exercise.get('intensityPercentExtend', 0) / 1000
                    if intensity_pct > 0:
                        intensity_str = f"@ {intensity_pct:.0f}-{intensity_pct_ext:.0f}% threshold"
                
                if ex_name and target:
                    detail = f"{ex_name}: {target}"
                    if intensity_str:
                        detail += f" {intensity_str}"
                    exercise_details.append(detail)
            
            # Combine description with exercise details
            if exercise_details:
                description += "\n\nWorkout Structure:\n" + "\n".join([f"• {d}" for d in exercise_details])
            
            # Strip any leading/trailing whitespace
            description = description.strip()
            
            duration = f"{duration_sec // 60}min" if duration_sec > 0 else None
            distance = f"{distance_cm / 100000:.2f} km" if distance_cm > 0 else None
            training_load = str(training_load) if training_load > 0 else None
        
        # Structured-detail override for any sport that decoded into steps
        # (run/bike/strength + swim/climb — was is_rich-only, which left swim
        # events overview-blank). create_ics_file prints its own
        # Distance/Duration, so include_summary=False.
        if rich is not None and rich.has_structure:
            rich_desc = coros_decode.format_description(rich, include_summary=False)
            if rich_desc:
                description = rich_desc
                if rich.training_load and not training_load:
                    training_load = str(rich.training_load)

        workouts.append({
            'week': week,
            'day_of_week': day_of_week,
            'title': title,
            'description': description,
            'duration': duration,
            'distance': distance,
            'training_load': training_load
        })
    
    return workouts


def parse_training_data(data_text):
    """Parse the raw training data text into structured workout objects"""
    workouts = []
    lines = [line.strip() for line in data_text.strip().split('\n') if line.strip()]
    
    current_week = 0
    i = 0
    
    # Helper to track relative day in week if we are parsing linear text
    # The text format is a bit lossy on exact weekdays unless we track it carefully
    # Assuming standard flow for text parser: Week X header -> Mon -> Tue...
    
    # Simple heuristic to guess day based on previous logic might be flaky for exact dates
    # But let's keep existing logic for backwards compatibility if it works for the USER's snippet approach
    
    while i < len(lines):
        line = lines[i]
        
        # Check for week marker
        if 'Week(s)' in line or line.startswith('Week '):
             # Try to parse week number
            try:
                current_week = int(re.search(r'\d+', line).group())
            except:
                pass
            i += 1
            continue
        
        # Skip summary lines
        if line in ['Activity Time:', 'Distance:', 'Training Load:'] or '/' in line:
            i += 1
            continue
        
        # Check if this is a workout title
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            
            # Check if next line is a time or distance (indicating this is a workout title)
            is_time = re.match(r'\d{2}:\d{2}:\d{2}', next_line)
            is_distance = re.match(r'\d+\.\d+ km', next_line)
            
            if is_time or is_distance or 'Target race day' in line:
                title = line
                duration = None
                distance = None
                tl = None
                description_lines = []
                
                i += 1
                
                # Parse workout details
                while i < len(lines):
                    detail_line = lines[i]
                    
                    # Stop if we hit the next workout or week marker
                    if 'Week(s)' in detail_line or detail_line.startswith('Week ') or detail_line in ['Activity Time:', 'Distance:', 'Training Load:']:
                        break
                    
                    # Check if this looks like a new workout title
                    if i + 1 < len(lines):
                        next_detail = lines[i + 1]
                        if re.match(r'\d{2}:\d{2}:\d{2}', next_detail) or re.match(r'\d+\.\d+ km', next_detail):
                            break
                    
                    # Parse the detail
                    if re.match(r'\d{2}:\d{2}:\d{2}', detail_line):
                        duration = detail_line
                    elif re.match(r'\d+\.\d+ km', detail_line):
                        distance = detail_line
                    elif 'TL' in detail_line and re.match(r'\d+', detail_line):
                        tl = detail_line
                    elif detail_line and detail_line not in ['/', '0.00 km', '00:00:00', '0 TL']:
                        description_lines.append(detail_line)
                    
                    i += 1
                
                # Create workout object
                # Note: The text parser doesn't explicitly extract "Day of Week" easily
                # We will assign day_of_week parsing in create_ics_file by simple distribution if not present
                workout = {
                    'week': current_week,
                    'title': title,
                    'duration': duration,
                    'distance': distance,
                    'training_load': tl,
                    'description': ' '.join(description_lines) if description_lines else '',
                    'day_of_week': None # To be assigned
                }
                workouts.append(workout)
                continue
        
        i += 1
    
    return workouts

def calculate_plan_dates(workouts, start_date=None):
    """
    Calculate the actual date for each workout based on the start date.
    Aligns the first workout to the first occurrence of its specific weekday
    on or after the provided start_date.
    """
    if not workouts:
        return []

    if start_date is None:
        start_date = datetime.now()

    # Find the first workout to determine the anchor weekday
    # Assumes workouts are sorted by week/day
    sorted_workouts = sorted(workouts, key=lambda x: (x.get('week', 1), x.get('day_of_week', 0)))
    first_workout = sorted_workouts[0]
    
    first_workout_weekday = first_workout.get('day_of_week', 0) # 0=Mon
    if first_workout_weekday is None:
         # Fallback for text parsed data where day is unknown
         first_workout_weekday = 0 
    
    # Align start_date to the next occurrence of first_workout_weekday
    # User selected start_date. We want the first workout to happen ON or AFTER this date,
    # specifically on its assigned weekday.
    
    days_shift = (first_workout_weekday - start_date.weekday()) % 7
    # If days_shift is 0, it matches today.
    # If start_date is Wed(2) and first is Tue(1): (1 - 2) % 7 = -1 % 7 = 6. Wed+6 = Tue. Correct.
    # If start_date is Mon(0) and first is Tue(1): (1 - 0) % 7 = 1. Mon+1 = Tue. Correct.
    
    aligned_first_workout_date = start_date + timedelta(days=days_shift)
    
    # Now we need to determine the "Plan Base Date" (Week 1, Day 0 - Monday)
    # relative to this aligned first workout.
    # aligned_date = BaseDate + (Week-1)*7 + DayOfWeek
    # BaseDate = aligned_date - (Week-1)*7 - DayOfWeek
    
    # Be careful with dates. We want to return a list of workouts with 'date' attached.
    
    base_date = aligned_first_workout_date - timedelta(days=((first_workout.get('week', 1) - 1) * 7) + first_workout_weekday)
    
    # Recalculate all dates relative to base_date
    rich_workouts = []
    for w in sorted_workouts:
        w_copy = w.copy()
        
        wd = w.get('day_of_week')
        wk = w.get('week', 1)
        
        if wd is None:
            # Fallback for legacy text parsing without explicit days
            # This logic is imperfect but text parsing is legacy
            # We will just append them sequentially? 
            # Reusing the loop logic might imply we need days.
            # Let's Skip date calc for legacy or enforce day 0-6 cycle?
            # convert_to_ics legacy logic did a simple loop.
            # Let's assign temporary days if missing
            wd = 0 
        
        days_offset = ((wk - 1) * 7) + wd
        current_date = base_date + timedelta(days=days_offset)
        
        w_copy['date_obj'] = current_date
        w_copy['date_str'] = current_date.strftime('%Y-%m-%d')
        w_copy['weekday_name'] = current_date.strftime('%A')
        
        rich_workouts.append(w_copy)
        
    return rich_workouts

def create_ics_file(workouts, start_date=None, output_file='coros_training_plan.ics'):
    """Create an ICS calendar file from the workout data"""
    
    # Use today as start date if not provided
    if start_date is None:
        start_date = datetime.now()
    
    # Calculate dates
    # If workouts already have 'date_obj', use it (parsed from preview), otherwise calculate
    if not workouts or 'date_obj' not in workouts[0]:
        workouts_with_dates = calculate_plan_dates(workouts, start_date)
    else:
        workouts_with_dates = workouts

    # Create calendar
    cal = Calendar()
    cal.add('prodid', '-//COROS Training Plan//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', 'COROS Training Plan')
    
    for workout in workouts_with_dates:
        event_date = workout['date_obj']
        
        # Create event
        event = Event()
        event.add('summary', workout['title'])
        
        # Use All Day Event (VALUE=DATE)
        event_date_val = event_date.date() if isinstance(event_date, datetime) else event_date
        
        event.add('dtstart', event_date_val)
        event.add('dtend', event_date_val + timedelta(days=1)) 
        
        # Description
        description_parts = []
        if workout.get('distance'):
            description_parts.append(f"Distance: {workout['distance']}")
        if workout.get('duration'):
            description_parts.append(f"Duration: {workout['duration']}")
        if workout.get('training_load'):
            description_parts.append(f"Training Load: {workout['training_load']}")
        if workout.get('description'):
            description_parts.append(f"\n{workout['description']}")
        
        event.add('description', '\n'.join(description_parts))
        
        # Add to calendar
        cal.add_component(event)
    
    # Write to file or return bytes
    if output_file:
        with open(output_file, 'wb') as f:
            f.write(cal.to_ical())
        
        print(f"✅ ICS file created: {output_file}")
        print(f"📅 Total events: {len(workouts)}")
        return output_file
    else:
        return cal.to_ical()

def resolve_start_date(start_arg=None):
    """Resolve the plan start date.

    - start_arg is a 'YYYY-MM-DD' string -> parse and return it (no prompt).
      Invalid strings raise ValueError (the CLI validates up front).
    - start_arg is None -> prompt interactively; Enter / EOF / no TTY = today.
    Returns a datetime.
    """
    if start_arg is not None:
        return datetime.strptime(start_arg, '%Y-%m-%d')

    print("\n📅 When would you like to start the training plan? (Week 1 Day 1)")
    print("   Press Enter to start today, or enter a date (YYYY-MM-DD):")
    try:
        user_input = input().strip()
    except EOFError:
        user_input = ""
    if user_input:
        try:
            return datetime.strptime(user_input, '%Y-%m-%d')
        except ValueError:
            print("⚠️  Invalid date format. Using today as start date.")
    return datetime.now()


def main():
    """Main function"""
    import argparse
    parser = argparse.ArgumentParser(description='Convert COROS plan to ICS')
    parser.add_argument('--url', help='COROS Training Plan URL')
    parser.add_argument('--file', default='training_data.txt', help='Input text file')
    parser.add_argument('--start', '--date', dest='start', metavar='YYYY-MM-DD',
                        help='Plan start date (Week 1 Day 1). Skips the interactive '
                             'prompt for non-interactive use. Defaults to today.')
    args = parser.parse_args()

    # Validate --start up front so we fail fast (before any network work).
    if args.start is not None:
        try:
            datetime.strptime(args.start, '%Y-%m-%d')
        except ValueError:
            parser.error(f"invalid --start date '{args.start}': expected YYYY-MM-DD")
    
    workouts = []

    if args.url:
        print(f"🌐 Scraping from URL: {args.url}")
        try:
            kind, _id, _region = parse_coros_url(args.url)
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
        if kind == "workout":
            # A single workout has no schedule — date it to --start (or today)
            # and write a one-event calendar. No week/day alignment.
            start_date = resolve_start_date(args.start)
            workouts = scrape_workout_from_url(args.url, start_date)
            if not workouts:
                print("❌ Could not read that workout.")
                sys.exit(1)
            print(f"✅ Workout: {workouts[0]['title']}")
            print(f"\n🚀 Creating ICS file dated {start_date.strftime('%Y-%m-%d')}...")
            output_file = create_ics_file(workouts, start_date, output_file='coros_workout.ics')
            print(f"\n✨ Done! Import '{output_file}' into your calendar app.")
            return
        workouts = scrape_from_url(args.url)
    else:
        print(f"🔍 Reading '{args.file}'...")
        # Check if file exists, if not prompt or exit
        try:
            data_text = load_training_data(args.file)
            workouts = parse_training_data(data_text)
        except SystemExit:
             # If default file not found and no arguments, guide user
            print("\nUsage:")
            print("  python3 convert_to_ics.py --url \"https://...\"")
            print("  python3 convert_to_ics.py --file training_data.txt")
            return

    if not workouts:
        print("❌ No workouts found.")
        sys.exit(1)
        
    print(f"✅ Found {len(workouts)} workouts")
    
    # Use --start if given (non-interactive), else prompt.
    start_date = resolve_start_date(args.start)

    print(f"\n🚀 Creating ICS file starting from {start_date.strftime('%Y-%m-%d')}...")
    output_file = create_ics_file(workouts, start_date)
    
    print(f"\n✨ Done! Import '{output_file}' into your calendar app.")

if __name__ == '__main__':
    main()

