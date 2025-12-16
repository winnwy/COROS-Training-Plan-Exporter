#!/usr/bin/env python3
"""
Convert COROS training plan data to ICS calendar format.
Reads data from 'training_data.txt'.
"""

import re
import sys
from datetime import datetime, timedelta
try:
    from icalendar import Calendar, Event
except ImportError:
    print("❌ Error: 'icalendar' library not found.")
    print("   Please run: pip install icalendar")
    sys.exit(1)

def load_training_data(filename='training_data.txt'):
    """Load training data from text file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: Could not find '{filename}'")
        print("   Please follow the instructions in README.md to create this file.")
        sys.exit(1)

def parse_training_data(data_text):
    """Parse the raw training data text into structured workout objects"""
    workouts = []
    lines = [line.strip() for line in data_text.strip().split('\n') if line.strip()]
    
    current_week = 0
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check for week marker
        if 'Week(s)' in line:
            current_week = int(line.split()[0])
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
                    if 'Week(s)' in detail_line or detail_line in ['Activity Time:', 'Distance:', 'Training Load:']:
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
                workout = {
                    'week': current_week,
                    'title': title,
                    'duration': duration,
                    'distance': distance,
                    'training_load': tl,
                    'description': ' '.join(description_lines) if description_lines else ''
                }
                workouts.append(workout)
                continue
        
        i += 1
    
    return workouts

def create_ics_file(workouts, start_date=None, output_file='coros_training_plan.ics'):
    """Create an ICS calendar file from the workout data"""
    
    # Use today as start date if not provided
    if start_date is None:
        start_date = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    
    # Create calendar
    cal = Calendar()
    cal.add('prodid', '-//COROS Training Plan//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', 'Marathon Training Plan')
    cal.add('x-wr-timezone', 'UTC')
    
    # Track current date (distribute workouts across the week)
    current_date = start_date
    workout_count_in_week = 0
    last_week = 0
    
    for workout in workouts:
        # If we're in a new week, reset to Monday
        if workout['week'] != last_week:
            # Move to next Monday if we're not already on one
            days_until_monday = (7 - current_date.weekday()) % 7
            if days_until_monday > 0 or workout_count_in_week > 0:
                current_date += timedelta(days=days_until_monday if days_until_monday > 0 else 7)
            workout_count_in_week = 0
            last_week = workout['week']
        
        # Create event
        event = Event()
        event.add('summary', workout['title'])
        
        # Parse duration if available
        duration_minutes = 60  # Default duration
        if workout['duration']:
            try:
                h, m, s = map(int, workout['duration'].split(':'))
                duration_minutes = h * 60 + m
            except:
                pass
        
        # Set event start and end times
        event.add('dtstart', current_date)
        event.add('dtend', current_date + timedelta(minutes=duration_minutes))
        
        # Build description
        description_parts = []
        if workout['distance']:
            description_parts.append(f"Distance: {workout['distance']}")
        if workout['duration']:
            description_parts.append(f"Duration: {workout['duration']}")
        if workout['training_load']:
            description_parts.append(f"Training Load: {workout['training_load']}")
        if workout['description']:
            description_parts.append(f"\n{workout['description']}")
        
        event.add('description', '\n'.join(description_parts))
        event.add('location', 'Training Run')
        
        # Add to calendar
        cal.add_component(event)
        
        # Move to next day (skip Sunday, move to Monday)
        current_date += timedelta(days=1)
        if current_date.weekday() == 6:  # Sunday
            current_date += timedelta(days=1)  # Move to Monday
        
        workout_count_in_week += 1
    
    # Write to file or return bytes
    if output_file:
        with open(output_file, 'wb') as f:
            f.write(cal.to_ical())
        
        print(f"✅ ICS file created: {output_file}")
        print(f"📅 Total events: {len(workouts)}")
        print(f"🏃 Training plan starts: {start_date.strftime('%Y-%m-%d')}")
        return output_file
    else:
        return cal.to_ical()

def main():
    """Main function"""
    print("🔍 Reading 'training_data.txt'...")
    data_text = load_training_data()
    
    workouts = parse_training_data(data_text)
    
    if not workouts:
        print("❌ No workouts found in data. Please check 'training_data.txt'.")
        sys.exit(1)
        
    print(f"✅ Found {len(workouts)} workouts across {max(w['week'] for w in workouts)} weeks")
    
    # Ask user for start date
    print("\n📅 When would you like to start the training plan?")
    print("   Press Enter to start today, or enter a date (YYYY-MM-DD):")
    user_input = input().strip()
    
    start_date = None
    if user_input:
        try:
            start_date = datetime.strptime(user_input, '%Y-%m-%d').replace(hour=6, minute=0, second=0, microsecond=0)
        except ValueError:
            print("⚠️  Invalid date format. Using today as start date.")
    
    if start_date is None:
        start_date = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    
    print(f"\n🚀 Creating ICS file starting from {start_date.strftime('%Y-%m-%d')}...")
    output_file = create_ics_file(workouts, start_date)
    
    print(f"\n✨ Done! Import '{output_file}' into your calendar app.")

if __name__ == '__main__':
    main()
