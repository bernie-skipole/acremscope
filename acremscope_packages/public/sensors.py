##################################
#
# These functions populate the public sensors pages
# and the weather (temperature) displays
#
##################################



import subprocess, tempfile, os, random, time, glob, json

from datetime import date, timedelta, datetime, timezone

from skipole import FailPage, GoTo, ValidateError, ServerError, PageData, SectionData

from indi_mr import tools

from .. import sun, database_ops, redis_ops, cfg


SIG_WEATHER = ["Clear night", "Sunny day", "Partly cloudy (night)", "Partly cloudy (day)",
               "Not used", "Mist", "Fog", "Cloudy", "Overcast", "Light rain shower (night)",
               "Light rain shower (day)", "Drizzle", "Light rain", "Heavy rain shower (night)",
               "Heavy rain shower (day)", "Heavy rain", "Sleet shower (night)", "Sleet shower (day)",
               "Sleet", "Hail shower (night)", "Hail shower (day)", "Hail", "Light snow shower (night)",
               "Light snow shower (day)", "Light snow", "Heavy snow shower (night)", "Heavy snow shower (day)",
               "Heavy snow", "Thunder shower (night)", "Thunder shower (day)", "Thunder"]


def retrieve_sensors_data(skicall):
    "Display sensor values, initially just the led status"

    rconn = skicall.proj_data.get("rconn")
    redisserver = skicall.proj_data.get("redisserver")
    skicall.page_data['led_status', 'para_text'] = "LED : " + redis_ops.get_led(rconn, redisserver)
    skicall.page_data['temperature_status', 'para_text'] = "Temperature : " + redis_ops.last_temperature(rconn, redisserver)
    skicall.page_data['door_status', 'para_text'] = "Door : " + redis_ops.get_door(rconn, redisserver)

    # get timestamp of the network monitor, display alarm if greater than 15 secods
    # tools.elements_dict returns a dictionary of element attributes for the given element, property and device
    monitor = tools.elements_dict(rconn, redisserver, 'KeepAlive', 'TenSecondHeartbeat', 'Network Monitor')
    if not monitor:
        skicall.page_data['show_error'] = "Network Error : Unable to read monitor timestamp"
        return

    # note fromisoformat method requires python 3.7 +
    timed = datetime.utcnow() - datetime.fromisoformat(monitor['timestamp'])
    if timed.total_seconds() > 15:
        skicall.page_data['show_error'] = "Network Error : Communications to observatory lost"


def temperature_page(skicall):
    "Creates the waether page including met office data, and temperature graph and meter"


    call_data = skicall.call_data
    pd = call_data['pagedata']
    sd_weather = SectionData("weather")

    # datetime needed in a format like 2021-06-13T12:00Z
    thistime = datetime.now(timezone.utc).strftime("%G-%m-%dT%H:00Z")
    weatherfile = os.path.join(cfg.get_astrodata_directory(),"weather.json")
    try:
        with open(weatherfile, 'r') as fp:
            weather_dict = json.load(fp)

        if thistime not in weather_dict:
            sd_weather.show = False
        else:
            weathernow = weather_dict[thistime]
            columns = list(zip(*weathernow))
            sd_weather["wtable","col1"] = columns[0]
            sd_weather["wtable","col2"] = columns[1]
            sd_weather["wtable","col3"] = columns[2]
            sd_weather["weatherhead","large_text"] = f"Met office data for UTC time : {thistime[:-4]}"
            try:
                index = columns[0].index("Significant Weather Code")
                code = int(columns[1][index])
                sd_weather["weatherhead","small_text"] = "Weather summary : " + SIG_WEATHER[code]
            except:
                pass                
            sd_weather["weatherhead","large_text"]
    except:
        # The file does not exist, or is not readable by json
        sd_weather.show = False

    pd.update(sd_weather)

    date_temp = redis_ops.last_temperature(skicall.proj_data.get("rconn"), skicall.proj_data.get("redisserver"))
    #if not date_temp:
    #    raise FailPage("No temperature values available")

    if date_temp:
        last_date, last_time, last_temp = date_temp.split()

        pd['datetemp', 'para_text'] = last_date + " " + last_time + " Temperature: " + last_temp
        pd["meter", "measurement"] = last_temp
    else:
        pd['datetemp', 'para_text'] = "No temperature values available"
        pd["meter", "measurement"] = "0.0"

    # create a time, temperature dataset
    dataset = []
    datalog = redis_ops.get_temperatures(skicall.proj_data.get("rconn"), skicall.proj_data.get("redisserver"))
    if not datalog:
        pd['temperaturegraph', 'values'] = []
    else:
        # so there is some data in datalog
        for log_date, log_time, log_temperature in datalog:
            log_year,log_month,log_day = log_date.split("-")
            loghms = log_time.split(":")
            log_hour = loghms[0]
            log_min = loghms[1]
            dtm = datetime(year=int(log_year), month=int(log_month), day=int(log_day), hour=int(log_hour), minute=int(log_min))
            dataset.append((log_temperature, dtm))
        pd['temperaturegraph', 'values'] = dataset
    skicall.update(pd)



def last_temperature(skicall):
    "Gets the day, temperature for the last logged value"

    date_temp = redis_ops.last_temperature(skicall.proj_data.get("rconn"), skicall.proj_data.get("redisserver"))
    if not date_temp:
        raise FailPage("No temperature values available")

    last_date, last_time, last_temp = date_temp.split()

    skicall.page_data['datetemp', 'para_text'] = last_date + " " + last_time + " Temperature: " + last_temp
    skicall.page_data["meter", "measurement"] = last_temp








