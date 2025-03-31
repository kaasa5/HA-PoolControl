"""
Pool notification script for Home Assistant
Handles notifications for pool pump state and trigger changes
"""
import datetime

# Get input data
domain = data.get("domain", "")
pool_notifications = hass.states.get("input_boolean.pool_notifications").state == "on"

if not pool_notifications:
    # Exit if notifications are disabled
    exit(0)

def trigger_to_display_text(trig):
    """Convert trigger IDs to human-readable text"""
    triggers = {
        "online": "online",
        "onlineSwim": "online",
        "button": "the button",
        "buttonSwim": "the button",
        "watch": "Watch",
        "watchSwim": "Watch",
        "timer": "the timer",
        "heatpump": "the heating",
        "heated_timer": "the heating",
        "schedule": "the schedule",
        "solar": "the sun",
        "reset": "automatic mode"
    }
    return triggers.get(trig, trig)

def get_schedule_round():
    """Determine which pumping round we're in based on current time"""
    now_dt = datetime.datetime.now()
    end_schedule = datetime.datetime.strptime(
        hass.states.get("input_datetime.pool_schedule_end").state, 
        "%H:%M:%S"
    ).replace(day=now_dt.day, month=now_dt.month, year=now_dt.year)
    
    diff = (now_dt - end_schedule).total_seconds()
    if diff < 0:
        return 0  # Before first round
    elif diff < 60:
        return 1  # During first round
    else:
        return 2  # Second round

def format_state(state):
    """Format state string for display"""
    return "On" if state == "on" else "Off"

def format_time(time_str):
    """Format time string to display only HH:MM"""
    return time_str[0:5] if time_str else ""

# Process pool pump notifications
if domain == "Pump":
    old_state = data.get("old_state", "")
    new_state = data.get("new_state", "")
    old_trigger = data.get("old_trigger", "")
    new_trigger = data.get("new_trigger", "")
    
    send = False
    manual_triggers = ["onlineSwim", "buttonSwim", "watchSwim"]
    message = ""

    # Handle trigger change but same state
    if old_state == new_state and old_trigger != new_trigger:
        if old_trigger == "solar" and new_trigger == "schedule":
            round_num = get_schedule_round()
            if round_num == 0:
                message = "Pump starts with the first pumping round"
            elif round_num == 1:
                message = "Pump continues with the first pumping round"
            elif round_num == 2:
                message = "Pump continues with the second pumping round"
                
        elif old_trigger == "schedule" and new_trigger == "solar":
            if get_schedule_round() == 1:
                message = "First round of pumping completed, continues on the sun"
            else:
                message = "Daily schedule is completed, continues on the sun"
                
        elif new_trigger == "schedule":
            round_num = get_schedule_round()
            if round_num == 0:
                end_time = format_time(hass.states.get("input_datetime.pool_schedule_end").state)
                message = f"Pump has been changed from {trigger_to_display_text(old_trigger)} according to schedule and starts with the first pumping round with end time {end_time}."
            elif round_num == 1:
                end_time = format_time(hass.states.get("input_datetime.pool_schedule_end").state)
                message = f"Pump has been changed from {trigger_to_display_text(old_trigger)} according to schedule and continues with the first pumping round with end time {end_time}."
            elif round_num == 2:
                end_time = format_time(hass.states.get("input_datetime.pool_schedule_last_cycle_end").state)
                message = f"Pump has been changed from {trigger_to_display_text(old_trigger)} according to schedule and continues with the second pumping round with end time {end_time}."
        else:
            message = f"Pump has been changed from {trigger_to_display_text(old_trigger)} to {trigger_to_display_text(new_trigger)}, stays {format_state(new_state)}"
        send = True
        
    # Handle state change
    elif old_state != new_state:
        if new_state == "on":
            if new_trigger == "schedule":
                end_time = format_time(hass.states.get("input_datetime.pool_schedule_end").state)
                round_num = get_schedule_round()
                if round_num == 0:
                    message = f"Pump starts with the first pump round with end time {end_time}"
                elif round_num == 1:
                    message = f"Pump continues with the first pump round with end time {end_time}"
                elif round_num == 2:
                    end_time = format_time(hass.states.get("input_datetime.pool_schedule_last_cycle_end").state)
                    message = f"Pump is switched on for second pump round with end time {end_time}"
            elif new_trigger == "solar":
                power = hass.states.get("sensor.util_power_solar_average").state
                message = f"Pump is turned on by the sun ({power}W)"
            elif new_trigger == "timer":
                end_time = format_time(hass.states.get("input_datetime.pool_timer_end").state[10:16])
                message = f"Pump is turned on by the timer which ends at {end_time}."
            else:
                message = f"Pump is switched on by {trigger_to_display_text(new_trigger)}"
        elif new_state == "off":
            message = f"Pump has been switched off by {trigger_to_display_text(new_trigger)}"
        send = True

    # Send notification if needed
    if send:
        service_data = {
            "title": "Pool",
            "message": message
        }
        hass.services.call("notify", "mobile_app_iphone_van_wesley", service_data=service_data)