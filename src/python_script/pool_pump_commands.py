"""
Pool Pump Control Script for Home Assistant
Manages the pool pump based on different triggers with priority handling
"""
import datetime
import logging

# Get input data
command = data.get("command", "")
trigger = data.get("trigger", "")

# Set up logger
logger = logging.getLogger(__name__)

def get_priority(trigger):
    """
    Get priority level for a given trigger
    Lower number = higher priority
    """
    priorities = {
        # Priority 1: Manual controls
        "online": 1, 
        "button": 1, 
        "watch": 1,
        "onlineSwim": 1, 
        "buttonSwim": 1, 
        "watchSwim": 1,
        # Other priorities
        "heated_timer": 2,
        "heatpump": 3,
        "after_timer": 4,
        "timer": 5,
        "schedule": 6,
        "solar": 7,
        "reset": 8
    }
    return priorities.get(trigger, 9)  # Default to lowest priority if not found

def format_datetime(dt):
    """Format datetime for Home Assistant input_datetime"""
    return f"{dt.year}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"

def pump(command, trigger, recover=False, after_timer=False):
    """
    Control the pool pump based on commands and triggers
    
    Args:
        command: "on", "off", or "recover"
        trigger: The source of the command
        recover: Whether this is a recovery operation
        after_timer: Whether this is after a timer
    """
    # Get current states
    old_trigger = hass.states.get("input_select.pool_pump_trigger").state
    old_state = hass.states.get("switch.pool_pump_relay").state
    
    # Standard commands (on/off)
    if command in ["on", "off"]:
        # Calculate priorities and restrictions
        priority = get_priority(trigger)
        old_priority = float(hass.states.get("input_number.pool_pump_priority").state)
        
        # Check time restrictions
        time_on = float(hass.states.get("sensor.pool_pump_time_on").state) * 60
        max_time = float(hass.states.get("input_number.pool_pump_duration_upper_threshold").state)
        time_restricted = (time_on >= max_time) and trigger in ("schedule", "solar")
        
        # Process command if higher priority or recovery mode and not time restricted
        if (priority <= old_priority or recover) and not time_restricted:
            # Update trigger and priority
            service_data_priority = {"entity_id": "input_number.pool_pump_priority", "value": priority}
            hass.services.call("input_number", "set_value", service_data_priority)
            
            service_data_trigger = {"entity_id": "input_select.pool_pump_trigger", "option": trigger}
            hass.services.call("input_select", "select_option", service_data_trigger)
            
            # Set pool pump state
            service_data_pump = {"entity_id": "switch.pool_pump_relay"}
            hass.services.call("switch", f"turn_{command}", service_data_pump)
            
            # Send notification
            service_data_notify = {
                "domain": "Pump", 
                "old_state": old_state, 
                "new_state": command, 
                "old_trigger": old_trigger, 
                "new_trigger": trigger
            }
            hass.services.call("python_script", "pool_notify", service_data_notify)
            
            # Control heat pump
            is_heating_trigger = trigger in ("heated_timer", "heatpump")
            was_heating_trigger = old_trigger in ("heated_timer", "heatpump")
            cmd_heatpump = "on" if (command == "on" and is_heating_trigger) or (priority == 1 and was_heating_trigger) else "off"
            
            service_data_heat = {"entity_id": "switch.pool_heatpump_climate"}
            hass.services.call("switch", f"turn_{cmd_heatpump}", service_data_heat)
            
            # Handle after timer settings
            swimming_triggers = ["onlineSwim", "buttonSwim", "watchSwim"]
            heating_triggers = ["heatpump", "heated_timer"]
            after_timer_planned = "on" if command == "on" and (trigger in swimming_triggers or trigger in heating_triggers) else "off"
            after_timer_state = "on" if trigger == "after_timer" else "off"
            
            service_data_timer_planned = {"entity_id": "input_boolean.pool_after_timer_planned"}
            hass.services.call("input_boolean", f"turn_{after_timer_planned}", service_data_timer_planned)
            
            service_data_timer_active = {"entity_id": "input_boolean.pool_after_timer_active"}
            hass.services.call("input_boolean", f"turn_{after_timer_state}", service_data_timer_active)
            
        elif time_restricted:
            # Time limit reached, reset and turn off
            service_data_priority = {"entity_id": "input_number.pool_pump_priority", "value": 8}
            hass.services.call("input_number", "set_value", service_data_priority)
            
            service_data_trigger = {"entity_id": "input_select.pool_pump_trigger", "option": "reset"}
            hass.services.call("input_select", "select_option", service_data_trigger)
            
            service_data_pump = {"entity_id": "switch.pool_pump_relay"}
            hass.services.call("switch", "turn_off", service_data_pump)
            
            service_data_heat = {"entity_id": "switch.pool_heatpump_climate"}
            hass.services.call("switch", "turn_off", service_data_heat)
            
            # Send notification about time limit
            data = {
                "title": "Pool",
                "message": f"Pomp trigger {trigger} genegeerd vanwege tijdslimiet, pomp gaat uit."
            }
            hass.services.call("notify", "mobile_app_iphone_van_wesley", service_data=data)
            
        elif command != old_state:
            # Lower priority command is ignored, but offer override
            data = {
                "title": "Pool",
                "message": f"Pomp trigger {trigger} met lagere prioriteit genegeerd vanwege {old_trigger}, wil je dit overbruggen?",
                "data": {"push": {"category": "PUMP_OVERRIDE"}}
            }
            hass.services.call("notify", "mobile_app_iphone_van_wesley", service_data=data)
    
    elif command == "recover":
        # Recovery logic - determine what state the pump should be in
        priority = float(hass.states.get("input_number.pool_pump_priority").state)
        now = datetime.datetime.now()
        
        # Get schedule times
        start_schedule = datetime.datetime.strptime(
            hass.states.get("input_datetime.pool_schedule_start").state, 
            "%H:%M:%S"
        ).replace(day=now.day, month=now.month, year=now.year)
        
        start_last = datetime.datetime.strptime(
            hass.states.get("input_datetime.pool_schedule_last_cycle_start").state, 
            "%H:%M:%S"
        ).replace(day=now.day, month=now.month, year=now.year)
        
        end_schedule = datetime.datetime.strptime(
            hass.states.get("input_datetime.pool_schedule_end").state, 
            "%H:%M:%S"
        ).replace(day=now.day, month=now.month, year=now.year)
        
        remaining = int(hass.states.get("sensor.pool_pump_remaining_time").attributes['seconds'])
        
        # Check conditions in priority order
        if priority == 1.0 and trigger != "reset":
            # Manually switched on, keep it
            pass
            
        elif (hass.states.is_state("input_boolean.pool_timer_heat", "on") and 
              hass.states.is_state("binary_sensor.pool_timer_active", "on")):
            # Heated timer is active
            service_data = {"entity_id": "input_boolean.pool_timer_state"}
            hass.services.call("input_boolean", "turn_on", service_data)
            pump_call("on", "heated_timer", old_trigger)
            
        elif (hass.states.is_state("switch.pool_heatpump_climate", "on") and 
              old_trigger != "heated_timer"):
            # Heat pump is on, pump needs to be on too
            pump_call("on", "heatpump", old_trigger)
            
        elif (hass.states.is_state("binary_sensor.pool_after_timer_active", "on") or 
              after_timer):
            # After timer is active
            pump_call("on", "after_timer", old_trigger)
            
        elif hass.states.is_state("input_boolean.pool_after_timer_planned", "on"):
            # After timer is planned - calculate and set end time
            duration = float(hass.states.get("input_number.pool_after_timer_duration").state)
            end_time = now + datetime.timedelta(minutes=duration)
            formatted_datetime = format_datetime(end_time)
            
            service_data = {
                "entity_id": "input_datetime.pool_after_timer_end", 
                "datetime": formatted_datetime
            }
            hass.services.call("input_datetime", "set_datetime", service_data)
            
            # Update after timer states
            service_data_off = {"entity_id": "input_boolean.pool_after_timer_planned"}
            hass.services.call("input_boolean", "turn_off", service_data_off)
            
            service_data_on = {"entity_id": "input_boolean.pool_after_timer_active"}
            hass.services.call("input_boolean", "turn_on", service_data_on)
            
            # Set after timer
            new_trigger = "after_timer" if trigger != "reset" else "reset"
            pump("recover", new_trigger, after_timer=True)
            
        elif hass.states.is_state("binary_sensor.pool_timer_active", "on"):
            # Timed schedule is active
            state = "on" if hass.states.is_state("input_boolean.pool_timer_state", "on") else "off"
            pump_call(state, "timer", old_trigger)
            
        elif start_schedule <= now < end_schedule:
            # First round of schedule
            pump_call("on", "schedule", old_trigger)
            
        elif now >= start_last and remaining > 60:
            # Second (optional) round of schedule
            pump_call("on", "schedule", old_trigger)
            end_time = now + datetime.timedelta(seconds=remaining)
            
            service_data = {
                "entity_id": "input_datetime.pool_schedule_last_cycle_end", 
                "time": f"{end_time.hour:02d}:{end_time.minute:02d}:{end_time.second:02d}"
            }
            hass.services.call("input_datetime", "set_datetime", service_data)
            
        elif hass.states.is_state("binary_sensor.pool_solar_active", "on"):
            # Solar power available
            pump_call("on", "solar", old_trigger)
            
        else:
            # No active conditions, turn off the pump
            pump_call("off", "reset", old_trigger)
            
    else:
        # Invalid command
        logger.warning(f"Command not recognized: {command}")

def pump_call(command, trigger, old_trigger):
    """Helper function to call pump with proper parameters"""
    # Check time restrictions
    time_on = float(hass.states.get("sensor.pool_pump_time_on").state) * 60
    max_time = float(hass.states.get("input_number.pool_pump_duration_upper_threshold").state)
    time_restricted = (time_on >= max_time) and trigger in ("schedule", "solar")
    current_state = hass.states.get("switch.pool_pump_relay").state
    
    # Only call pump if state changes or restrictions apply
    if time_restricted or old_trigger != trigger or command != current_state:
        pump(command, trigger, recover=True)

# Execute the command
pump(command, trigger)