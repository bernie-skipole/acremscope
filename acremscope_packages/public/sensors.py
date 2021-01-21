##################################
#
# These functions populate the public sensors pages
#
##################################



import subprocess, tempfile, os, random, time, glob

import urllib.request

from datetime import date, timedelta, datetime

from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import sun, database_ops, redis_ops, cfg


def retrieve_sensors_data(skicall):
    "Display sensor values, initially just the led status"
    skicall.page_data['led_status', 'para_text'] = "LED : " + redis_ops.get_led(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"))
    skicall.page_data['temperature_status', 'para_text'] = "Temperature : " + redis_ops.last_temperature(skicall.proj_data.get("rconn_0"))
    skicall.page_data['door_status', 'para_text'] = "Door : " + redis_ops.get_door(skicall.proj_data.get("rconn_0"))
    skicall.page_data['webcam01_status', 'para_text'] = "Webcam01 : " + redis_ops.get_webcam01(skicall.proj_data.get("rconn_0"))


def _temperature_files():
    "Returns temperature files directory and list of temperature filenames in the directory"
    # directory where files will be served
    servedfiles_dir = cfg.get_servedfiles_directory()
    temperature_dir = os.path.join(servedfiles_dir, 'temperature')
    if not os.path.isdir(temperature_dir):
        return None, []
    # get logged temperature files
    temperaturefiles = []
    for f in os.listdir(temperature_dir):
        path = os.path.join(temperature_dir, f)
        if os.path.isfile(path):
            temperaturefiles.append(f)
    return temperature_dir, temperaturefiles


def temperature_page(skicall):
    "Creates the page of temperature graph and logs"
    temperature_dir, temperaturefiles = _temperature_files()
    if not temperaturefiles:
        skicall.page_data['logfiles','show'] = False
    else:
        logfiles = []
        for f in temperaturefiles:
            logfiles.append((f, 'logs/temperature/' + f, ''))
        logfiles.sort(key=lambda lf: lf[0], reverse=True)
        skicall.page_data['logfiles','links'] = logfiles
    page_data = skicall.page_data
    # create a time, temperature dataset
    this_day = datetime.utcnow().date()
    dataset = []
    datalog = redis_ops.get_temperatures(skicall.proj_data.get("rconn_0"))
    if datalog:
        datalog = [ item.decode('utf-8') for item in datalog ]
    else:
        # empty data, show empty graph of today
        page_data['temperaturegraph', 'last_day'] = this_day
        prevday = this_day - timedelta(days=1)
        page_data['left', 'get_field1'] = prevday.isoformat()
        page_data['temperaturegraph', 'values'] = []
        return

    # so there is some data in datalog

    latest_date = None

    for item in datalog:
        log_date, log_time, log_temperature = item.split()
        log_year,log_month,log_day = log_date.split("-")
        log_hour, log_min = log_time.split(":")
        dtm = datetime(year=int(log_year), month=int(log_month), day=int(log_day), hour=int(log_hour), minute=int(log_min))
        dt = dtm.date()
        if latest_date is None:
            latest_date = dt
        elif dt > latest_date:
            latest_date = dt
        dataset.append((log_temperature, dtm))
    page_data['temperaturegraph', 'values'] = dataset

    if this_day != latest_date:
        # show graph of this_day, including last_day endpoint
        page_data['temperaturegraph', 'last_day'] = this_day

    # if latest_date is equal to this_day, then show graph of this_day
    # but not including endpoint, so this makes the right hand of the graph
    # equal to the latest point measured - acting more like a chart

    prevday = this_day - timedelta(days=1)
    page_data['left', 'get_field1'] = prevday.isoformat()
    page_data['right', 'show'] = False



def graph_day_temperature(skicall):
    "Creates the temperature graph for a given day from CVS logs"

    temperature_dir, temperaturefiles = _temperature_files()
    if not temperaturefiles:
        skicall.page_data['logfiles','show'] = False
    else:
        logfiles = []
        for f in temperaturefiles:
            logfiles.append((f, 'logs/temperature/' + f, ''))
        logfiles.sort(key=lambda lf: lf[0], reverse=True)
        skicall.page_data['logfiles','links'] = logfiles

    call_data = skicall.call_data
    page_data = skicall.page_data

    day = ''
    if ('left', 'get_field1') in call_data:
        day = call_data['left', 'get_field1']
    if not day:
        if ('right', 'get_field1') in call_data:
            day = call_data['right', 'get_field1']
    if not day:
        raise FailPage("A day to graph temperature has not been given")

    try:
        y,m,d = day.split("-")
        day = date(int(y), int(m), int(d))
        prevday = day - timedelta(days=1)
        nextday = day + timedelta(days=1)
    except Exception:
        raise FailPage("Invalid date")

    if day >= datetime.utcnow().date():
        return temperature_page(skicall)

    dataset = _get_logs_for_day(day)
    prevdataset = _get_logs_for_day(prevday)
    dataset.extend(prevdataset)

    # ensure last point is for midnight
    page_data['temperaturegraph', 'last_day'] = day
    page_data['temperaturegraph', 'values'] = dataset
    page_data['left', 'get_field1'] = prevday.isoformat()
    page_data['right', 'get_field1'] = nextday.isoformat()


def _get_logs_for_day(day):
    "Return a list of logs for the given day, or empty list if none found"
    if day.month < 10:
        str_month = "0"+str(day.month)
    else:
        str_month = str(day.month)
    # log file required
    filename = str(day.year) + "_" + str_month + ".csv"

    # directory where temperature logfiles are kept
    temperature_dir, temperaturefiles = _temperature_files()
    if not temperaturefiles:
        return []
    if filename not in temperaturefiles:
        return []
    path = os.path.join(temperature_dir, filename)
    if not os.path.isfile(path):
        return []

    # create a dataset for day requested
    dataset = []
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                str_linedatetime, str_temperature = line.split(",")
                str_linedate, str_linetime = str_linedatetime.split("T")
                hr, minutes, seconds = str_linetime.split(":")
                yy,mm,dd = list(int(i) for i in str_linedate.split("-"))
                linedate = date(yy,mm,dd)
                if day == linedate:
                    dataset.append((str_temperature, datetime(linedate.year, linedate.month, linedate.day, int(hr), int(minutes), int(seconds))))
    except Exception:
        return []
    return dataset
    


def get_logfile(skicall):
    "Called by SubmitIterator responder to return a logfile"

    call_data = skicall.call_data
    page_data = skicall.page_data

    page_data['mimetype'] = "text/csv"
    urlpath = call_data['path']

    # directory where temperature logfiles are kept
    temperature_dir, temperaturefiles = _temperature_files()
    if not temperaturefiles:
        raise FailPage("File not found")

    # get required server path
    path = None
    if urlpath.startswith("/remscope/sensors/logs/temperature/"):
        filename = urlpath[35:]
        if filename not in temperaturefiles:
            raise FailPage("File not found")
        path = os.path.join(temperature_dir, filename)
        if not os.path.isfile(path):
            raise FailPage("File not found")
        with open(path, 'rb') as f:
            file_data = f.read()
        page_data['content-length'] = str(len(file_data))
        return (file_data,)
    raise FailPage("File not found")



def _oldtemperature(skicall):
    """Creates a temperature graph svg image using gnuplot, no longer used, but left here
       in case something similar required in future"""

    result = b''
    dataset = []
    # create a dataset of values against hourly time points
    # with a graph starting at now minus 2 days and 30 minutes
    # and with the end range at today, 23:59
    now = datetime.now()
    start_time = now - timedelta(days=2, minutes=30)

   
    dataset = redis_ops.get_temperatures(skicall.proj_data.get("rconn_0"))
    if dataset:
        dataset = [ item.decode('utf-8') for item in dataset ]

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as mydata:
        # write the dataset to the temporary file, each line separated by newline character
        mydata.writelines("%s\n" % point for point in dataset)
    try:
        # plot the points from temporary file mydata
        # the format of the x labels will be "day abbreviated month" above "hour:minute"
        commands = ['set title "temperature.svg" textcolor rgb "white"',
                    'set border lw 1 lc rgb "white"',
                    'set ytics textcolor rgb "white"',
                    'set key off',
                    'set xdata time',
                    'set timefmt "%Y-%m-%d %H:%M"',
                    'set yrange [*<-10:35<*]',
                    'set xrange ["%s":"%s 23:59"]' % (start_time.strftime("%Y-%m-%d %H:%M"), datetime.utcnow().date().strftime("%Y-%m-%d")),
                    'set format x "%d %b\n%H:%M"',
                    'plot "%s" using 1:3' % (mydata.name,)
                   ]
        # Call gnuplot with commands, result is svg image
        commandstring = "set terminal svg;" + ";".join(commands)
        args = ["gnuplot", "-e", commandstring]
        try:
            result = subprocess.check_output(args, timeout=2)
        except Exception:
            raise FailPage()
        if not result:
            raise FailPage()
    finally:
        # remove the temporary file
        os.unlink(mydata.name)

    # set mimetype and content-length
    skicall.page_data["mimetype"] = "image/svg+xml"
    skicall.page_data['content-length'] = str(len(result))
    return [result]


def last_temperature(skicall):
    "Gets the day, temperature for the last logged value"

    date_temp = redis_ops.last_temperature(skicall.proj_data.get("rconn_0"))
    if not date_temp:
        raise FailPage("No temperature values available")

    last_date, last_time, last_temp = date_temp.split()
    last_year,last_month,last_day = last_date.split("-")
    last_hour, last_min = last_time.split(":")

    skicall.page_data['datetemp', 'para_text'] = last_date + " " + last_time + " Temperature: " + last_temp
    skicall.page_data["meter", "measurement"] = last_temp


def fill_webcam_page(skicall):
    "Called to set the latest url into the image1 widget on the webcam page"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # directory where image files are kept
    servedfiles_dir = cfg.get_servedfiles_directory()
    webcam01_dir = os.path.join(servedfiles_dir, 'webcam01')
    try:
        filelist = glob.glob(webcam01_dir+'/*.jpg')
    except FileNotFoundError:
        raise FailPage("Directory %s not found" % (webcam01_dir,))
    if not filelist:
        raise FailPage("No files found in directory %s" % (webcam01_dir,))
    # sort the list and get the latest file name
    latest_file_path = max(filelist, key=os.path.getctime)
    latest_file = os.path.basename(latest_file_path)
    page_data['webcam01', 'img_url'] = "/webcam/cam01/" + latest_file
    page_data['webcam01_para', 'para_text'] = "Image " + latest_file
    webcam01_status = redis_ops.get_webcam01(skicall.proj_data.get("rconn_0"))
    if webcam01_status != 'WORKING':
        raise FailPage("ERROR: Webcam01 images are not updating")


def webcam_image(skicall):
    "Called by SubmitIterator responder to return an image"

    call_data = skicall.call_data
    page_data = skicall.page_data

    page_data['mimetype'] = "image/jpeg"
    urlpath = call_data['path']
    if not urlpath.startswith("/webcam/cam"):
        raise FailPage("File not found")
    # get 01 and filename if urlpath is "/webcam/cam01/filename"
    try:
        # webcam_number is a string such as "01/"
        webcam_number = urlpath[11:14]
        filename = urlpath[14:]
    except Exception:
        raise FailPage("File not found")

    # filename is typically 2018-11-16-09-25-01.jpg
    # check filename is twenty three characters and ends in '.jpg'
    if len(filename) != 23:
        raise FailPage("File not found")
    if filename[-4:] != ".jpg":
        raise FailPage("File not found")

    # directory where image files are kept
    servedfiles_dir = cfg.get_servedfiles_directory()
    if not servedfiles_dir:
        raise FailPage("File not found")

    # expand for each webcam added
    if webcam_number == "01/":
        webcam_dir = os.path.join(servedfiles_dir, 'webcam01')
    # elif webcam_number == "02/":
    #    webcam_dir = os.path.join(servedfiles_dir, 'webcam02')
    else:
        # webcam number not recognised
        raise FailPage("File not found")

    # get required server path
    path = None

    if not os.path.isdir(webcam_dir):
        raise FailPage("File not found")
    for f in os.listdir(webcam_dir):
        if filename == f:
            path = os.path.join(webcam_dir, f)
            break
    if not path:
        raise FailPage("File not found")
    with open(path, 'rb') as f:
        file_data = f.read()
    page_data['content-length'] = str(len(file_data))
    return (file_data,)


def fill_timelapse_page(skicall):
    "Called to fill paragraph on the timelapse page"

    call_data = skicall.call_data
    page_data = skicall.page_data

    servedfiles_dir = cfg.get_servedfiles_directory()
    video_file = os.path.join(servedfiles_dir, 'public_images', 'video.mp4')
    try:
        # time file modified in seconds
        mt = time.gmtime(os.stat(video_file).st_mtime)
        page_data['toppara', 'para_text'] = "One week time lapse video ending %s-%s-%s" % (mt.tm_year, mt.tm_mon, mt.tm_mday)
    except Exception:
        page_data['toppara', 'para_text'] = "One week time lapse video"


