##################################
#
# These functions populate the public sensors pages
# and the weather (temperature) displays
#
##################################



import subprocess, tempfile, os, random, time, glob

import urllib.request

from datetime import date, timedelta, datetime

from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import sun, database_ops, redis_ops, cfg


def retrieve_sensors_data(skicall):
    "Display sensor values, initially just the led status"

    rconn0 = skicall.proj_data.get("rconn_0")
    redisserver = skicall.proj_data.get("redisserver")
    skicall.page_data['led_status', 'para_text'] = "LED : " + redis_ops.get_led(rconn0, redisserver)
    skicall.page_data['temperature_status', 'para_text'] = "Temperature : " + redis_ops.last_temperature(rconn0, redisserver)
    skicall.page_data['door_status', 'para_text'] = "Door : " + redis_ops.get_door(rconn0)


def temperature_page(skicall):
    "Creates the page of temperature graph and meter"

    page_data = skicall.page_data

    date_temp = redis_ops.last_temperature(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"))
    #if not date_temp:
    #    raise FailPage("No temperature values available")

    if date_temp:
        last_date, last_time, last_temp = date_temp.split()

        page_data['datetemp', 'para_text'] = last_date + " " + last_time + " Temperature: " + last_temp
        page_data["meter", "measurement"] = last_temp
    else:
        page_data['datetemp', 'para_text'] = "No temperature values available"
        page_data["meter", "measurement"] = "0.0"


    # create a time, temperature dataset
    dataset = []
    datalog = redis_ops.get_temperatures(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"))
    if not datalog:
        page_data['temperaturegraph', 'values'] = []
        return
    # so there is some data in datalog
    for log_date, log_time, log_temperature in datalog:
        log_year,log_month,log_day = log_date.split("-")
        log_hour, log_min = log_time.split(":")
        dtm = datetime(year=int(log_year), month=int(log_month), day=int(log_day), hour=int(log_hour), minute=int(log_min))
        dataset.append((log_temperature, dtm))
    page_data['temperaturegraph', 'values'] = dataset



def last_temperature(skicall):
    "Gets the day, temperature for the last logged value"

    date_temp = redis_ops.last_temperature(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"))
    if not date_temp:
        raise FailPage("No temperature values available")

    last_date, last_time, last_temp = date_temp.split()

    skicall.page_data['datetemp', 'para_text'] = last_date + " " + last_time + " Temperature: " + last_temp
    skicall.page_data["meter", "measurement"] = last_temp





