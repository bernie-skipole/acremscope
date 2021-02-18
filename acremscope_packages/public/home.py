##################################
#
# These functions populate the top public pages
#
##################################

import os

from datetime import date, timedelta, datetime

from skipole import FailPage, GoTo, ValidateError, ServerError

from indi_mr import tools

from .. import sun, database_ops, cfg


def index_page(skicall):
    "Fills in the public index page"

    # Sets the top paragraph of the home page
    home_text = database_ops.get_text('home_text')
    if home_text:
        skicall.page_data['home_text', 'para_text'] = home_text


    message_string = database_ops.get_all_messages()
    if message_string:
        skicall.page_data['messages', 'messages', 'para_text'] = message_string

    # get timestamp of the network monitor, display alarm if greater than 15 secods
    # tools.elements_dict returns a dictionary of element attributes for the given element, property and device
    monitor = tools.elements_dict(skicall.proj_data.get("rconn"),
                                  skicall.proj_data.get("redisserver"),
                                  'KeepAlive',
                                  'TenSecondHeartbeat',
                                  'Network Monitor')

    timed = datetime.utcnow() - datetime.fromisoformat(monitor['timestamp'])
    if timed.total_seconds() > 15:
        skicall.page_data['show_error'] = "Network Error : Communications lost"



def index_image(skicall):
    "Called by SubmitIterator responder to return an image"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # directory where image file is kept
    servedfiles_dir = cfg.get_servedfiles_directory()
    if not servedfiles_dir:
        raise FailPage()
    if not os.path.isdir(servedfiles_dir):
        raise FailPage()
    path = os.path.join(servedfiles_dir, "public_images", "site_image.jpg")
    try:
        with open(path, 'rb') as f:
            file_data = f.read()
    except:
        raise FailPage()
    page_data['content-length'] = str(len(file_data))
    page_data['mimetype'] = "image/jpeg"
    return (file_data,)


def sessions_index(skicall):
    "Fills in the public sessions page"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Called by responder id 4001

    now = datetime.utcnow()
    today = now.date()

    now_15 = now + timedelta(minutes=15)

    rise_hour, rise_min = sun.sunrisetoday()


    if now.hour < rise_hour:
        # show timeslots from yesterday
        fromdate = today - timedelta(days=1)
    else:
        fromdate = today


    # observing hours are in a sequence of 0 to 23
    # where sequence 0 is 12 mid day of the observing day
    # sequence 12 is midnight, or hour zero of the observing night
    # sequence 23 is 11 am of the next day


    # get night 0 start and end observing hour
    hour, minute = sun.sunset(fromdate)
    start_hour_0 = hour + 1
    # observing can start after start_hour_0 as the sun will set before it
    # and convert this to the sequence number start0
    start0 = start_hour_0 - 12

    nextday = fromdate + timedelta(days=1)
    hour, minute = sun.sunrise(nextday)
    end_hour_0 = hour
    # observing must end at end_hour_0 as the sun will rise after that hour
    # and convert this to the sequence number end0
    end0 = 12 + end_hour_0

    # get night 1 start and end observing hour
    hour, minute = sun.sunset(nextday)
    start_hour_1 = hour + 1
    # observing can start after start_hour_1 as the sun will set before it
    # and convert this to the sequence number start1
    start1 = start_hour_1 - 12

    postday = nextday + timedelta(days=1)
    hour, minute = sun.sunrise(postday)
    end_hour_1 = hour
    # observing must end at end_hour_1 as the sun will rise after that hour
    # and convert this to the sequence number end1
    end1 = 12 + end_hour_1

    # get two nights of Slots
    night0, night1 = sun.twoday_slots(fromdate)

    start_seq = night0[0].sequence
    end_seq = night0[-1].sequence

    con = database_ops.open_database()

    try:

        sessions_enabled = database_ops.get_sessions(con)
        if sessions_enabled is None:
            raise FailPage("Database access error")


        for seq in range(0,24):
            slot0 = "slot_0_" + str(seq)
            slot1 = "slot_1_" + str(seq)
            if seq < start_seq:
                page_data[slot0, 'show'] = False
                page_data[slot1, 'show'] = False
                continue
            if seq > end_seq:
                page_data[slot0, 'show'] = False
                page_data[slot1, 'show'] = False
                continue

            SLOT0 = night0[seq - start_seq]
            SLOT1 = night1[seq - start_seq]
            page_data[slot0, 'timepara', 'para_text'] = str(SLOT0)
            page_data[slot1, 'timepara', 'para_text'] = str(SLOT1)

            slot0_status_id = database_ops.get_slot_status(SLOT0, con)
            slot1_status_id = database_ops.get_slot_status(SLOT1, con)

            if (slot0_status_id is None) or (slot1_status_id is None):
                raise FailPage("Unable to get slot info from database")

            slot0_status, slot0_user_id = slot0_status_id
            slot1_status, slot1_user_id = slot1_status_id

            page_data[slot0, 'planets', 'get_field1'] = SLOT0.startday_string()
            page_data[slot1, 'planets', 'get_field1'] = SLOT1.startday_string()

            if sessions_enabled:
                # Default value is sessions are available
                page_data[slot0, 'section_class'] = "w3-panel w3-green"
                page_data[slot0, 'available', 'para_text'] = 'Available'
                page_data[slot1, 'section_class'] = "w3-panel w3-green"
                page_data[slot1, 'available', 'para_text'] = 'Available'
            else:
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Unavailable'
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'available', 'para_text'] = 'Unavailable'


            # night0
            if now_15 > SLOT0.endtime:
                # slot has passed, tests now_15 rather than now, so slot is considered
                # past when it only has 15 or less minutes to go
                # This test only done on night0, since night1 is for tomorrow
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Past'
            elif seq < start0:
                # sun still up in this slot
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Sun Up'
            elif seq >= end0:
                # sun rising in this slot
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Sun Up'
            elif slot0_status:
                # slot unavailable or booked
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Unavailable'
                if slot0_status == 1:
                    page_data[slot0, 'section_class'] = "w3-panel w3-red"
                    page_data[slot0, 'available', 'para_text'] = 'Booked'

            # night1
            if seq < start1:
                # sun still up in this slot
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'available', 'para_text'] = 'Sun Up'
            elif seq >= end1:
                # sun rising in this slot
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'available', 'para_text'] = 'Sun Up'
            elif slot1_status:
                # slot unavailable or booked
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'available', 'para_text'] = 'Unavailable'
                if slot1_status == 1:
                    page_data[slot1, 'section_class'] = "w3-panel w3-red"
                    page_data[slot1, 'available', 'para_text'] = 'Booked'

    finally:
        database_ops.close_database(con)



