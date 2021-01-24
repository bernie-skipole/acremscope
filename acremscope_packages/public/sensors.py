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

    rconn0 = skicall.proj_data.get("rconn_0")
    redisserver = skicall.proj_data.get("redisserver")
    skicall.page_data['led_status', 'para_text'] = "LED : " + redis_ops.get_led(rconn0, redisserver)
    skicall.page_data['temperature_status', 'para_text'] = "Temperature : " + redis_ops.last_temperature(rconn0, redisserver)
    skicall.page_data['door_status', 'para_text'] = "Door : " + redis_ops.get_door(rconn0)
    skicall.page_data['webcam01_status', 'para_text'] = "Webcam01 : " + redis_ops.get_webcam01(rconn0)


def temperature_page(skicall):
    "Creates the page of temperature graph and logs"

    page_data = skicall.page_data
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

    date_temp = redis_ops.last_temperature(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"))
    if not date_temp:
        raise FailPage("No temperature values available")

    last_date, last_time, last_temp = date_temp.split()

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


