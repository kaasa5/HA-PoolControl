domain = data.get("domain", "")

pool_notifications = hass.states.get("input_boolean.pool_notifications").state == "on"

if not pool_notifications:
    exit(0)

def trigger(trig):
    if trig in ("online", "onlineSwim"):
        return "online"
    elif trig in ("button", "buttonSwim"):
        return "the button"
    elif trig in ("watch", "watchSwim"):
        return "Watch"
    elif trig == "timer":
        return "the timer"
    elif trig == "heatpump":
        return "the heating"
    elif trig == "heated_timer":
        return "the heating"
    elif trig == "schedule":
        return "the schedule"
    elif trig == "solar":
        return "the sun"
    elif trig == "reset":
        return "automatic mode"

def get_schedule_round():
    now_dt = datetime.datetime.now()
    end_schedule = datetime.datetime.strptime(hass.states.get("input_datetime.pool_schedule_end").state, "%H:%M:%S").replace(day=now_dt.day, month=now_dt.month, year=now_dt.year)
    diff = (now_dt - end_schedule).total_seconds()
    if diff < 0:
        return 0
    elif diff < 60:
        return 1
    else:
        return 2

def state(state):
    return "On" if state == "on" else "Off"

if domain == "Pump":
    old_state = data.get("old_state", "")
    new_state = data.get("new_state", "")
    old_trigger = data.get("old_trigger", "")
    new_trigger = data.get("new_trigger", "")
    
    send = False
    manual = ["onlineSwim", "buttonSwim", "watchSwim"]

    if old_state == new_state and old_trigger != new_trigger:
        # trigger change

        if old_trigger == "solar" and new_trigger == "schedule":
            round = get_schedule_round()
            if round == 0:
                message = "Pump starts with the first pumping round"
            elif round == 1:
                message = "Pump continues with the first pumping round"
            elif round == 2:
                message = "Pump continues with the second pumping round"
        elif old_trigger == "schedule" and new_trigger == "solar":
            if get_schedule_round() == 1:
                message = "First round of pumping completed, continues on the sun"
            else:
                message = "Daily schedule is completed, continues on the sun"
        #elif old_trigger in manual and new_trigger == "schedule":
        #    if get_schedule_round() == 1:
        #        message = "Manual has been reset, continues with first pumping round"
        #    else:
        #        message = "Manual has been reset, continues with second pumping round"
        elif new_trigger == "schedule":
            round = get_schedule_round()
            if round == 0:
                end = str(hass.states.get("input_datetime.pool_schedule_end").state)[0:5]
                message = "Pump has been changed from " + trigger(old_trigger) + " according to schedule and starts with the first pumping round with end time " + end + "."
            elif round == 1:
                end = str(hass.states.get("input_datetime.pool_schedule_end").state)[0:5]
                message = "Pump has been changed from " + trigger(old_trigger) + " according to schedule and continues with the first pumping round with end time " + end + "."
            elif round == 2:
                end = str(hass.states.get("input_datetime.pool_schedule_last_cycle_end").state)[0:5]
                message = "Pump has been changed from " + trigger(old_trigger) + " according to schedule and continues with the second pumping round with end time " + end + "."
        else:
            message = "Pump has been changed from " + trigger(old_trigger) + " Unpleasant " + trigger(new_trigger) + ", stays " + state(new_state)
        send = True
    elif old_state != new_state:
        # new state
        if new_state == "on":
            if new_trigger == "schedule":
                end = str(hass.states.get("input_datetime.pool_schedule_end").state)[0:5]
                round = get_schedule_round()
                if round == 0:
                    message = "Pump starts with the first pump round with end time " + end
                elif round == 1:
                    message = "Pump continues with the first pump round with end time " + end
                elif round == 2:
                    end = str(hass.states.get("input_datetime.pool_schedule_last_cycle_end").state)[0:5]
                    message = "Pump is switched on for second pump round with end time " + end
            elif new_trigger == "solar":
                power = hass.states.get("sensor.util_power_solar_average").state
                message = "Pump is turned on by the sun (" + power + "W)"
            elif new_trigger == "timer":
                end = str(hass.states.get("input_datetime.pool_timer_end").state)[10:16]
                message = "Pump is turned on by the timer which ends at " + end + "."
            else:
                message = "Pump is switched on by " + trigger(new_trigger)
        elif new_state == "off":
            message = "Pump has been switched off by " + trigger(new_trigger)
        send = True
    else:
        # do nothing
        send = False

    if send == True:
        data = {
            "title": "Pool",
            "message": message
        }
        hass.services.call("notify", "mobile_app_iphone_van_wesley", service_data=data)        


