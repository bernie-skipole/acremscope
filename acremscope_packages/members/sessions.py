##################################
#
# These functions populate the members sessions page
#
##################################

from datetime import date, timedelta, datetime

from functools import wraps

from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import sun, database_ops, redis_ops



def members_sessions_index(skicall):
    "Fills in the members sessions index page"

    call_data = skicall.call_data
    page_data = skicall.page_data

    today = datetime.utcnow().date()
    now = datetime.utcnow()
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

        # List of current slots already booked by this user for night0
        user_sessions0 = database_ops.get_users_sessions(night0[0].starttime, night0[-1].endtime, call_data['user_id'], con)
        if user_sessions0 is None:
            raise FailPage("Database access error")

        # List of current slots already booked by this user for night1
        user_sessions1 = database_ops.get_users_sessions(night1[0].starttime, night1[-1].endtime, call_data['user_id'], con)
        if user_sessions1 is None:
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

            page_data[slot0, 'bookit', 'button_text'] = 'Book it'
            page_data[slot0, 'bookit', 'get_field1'] = SLOT0.startday_string()
            page_data[slot0, 'bookit', 'get_field2'] = "book"

            page_data[slot1, 'bookit', 'button_text'] = 'Book it'
            page_data[slot1, 'bookit', 'get_field1'] = SLOT1.startday_string()
            page_data[slot1, 'bookit', 'get_field2'] = "book"

            if sessions_enabled:
                # Default value is sessions are available
                page_data[slot0, 'bookit', 'hide'] = False
                page_data[slot0, 'section_class'] = "w3-panel w3-green"
                page_data[slot0, 'available', 'para_text'] = 'Available'
                page_data[slot1, 'bookit', 'hide'] = False
                page_data[slot1, 'section_class'] = "w3-panel w3-green"
                page_data[slot1, 'available', 'para_text'] = 'Available'
            else:
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Unavailable'
                page_data[slot1, 'bookit', 'hide'] = True
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'available', 'para_text'] = 'Unavailable'


            # night0
            if now_15 > SLOT0.endtime:
                # slot has passed, tests now_15 rather than now, so slot is considered
                # past when it only has 15 or less minutes to go
                # This test only done on night0, since night1 is for tomorrow
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'available', 'para_text'] = 'Past'
            elif seq < start0:
                # sun still up in this slot
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'available', 'para_text'] = 'Sun Up'
            elif seq >= end0:
                # sun rising in this slot
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'available', 'para_text'] = 'Sun Up'
            elif slot0_status:
                # slot unavailable or booked
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Unavailable'
                if slot0_status == 1:
                    if slot0_user_id == call_data["user_id"]:
                        page_data[slot0, 'bookit', 'hide'] = False
                        page_data[slot0, 'bookit', 'button_text'] = 'Free it'
                        page_data[slot0, 'bookit', 'get_field2'] = "free"
                        page_data[slot0, 'section_class'] = "w3-panel w3-yellow"
                        page_data[slot0, 'available', 'para_text'] = 'Booked by you'
                    else:
                        page_data[slot0, 'section_class'] = "w3-panel w3-red"
                        page_data[slot0, 'available', 'para_text'] = 'Booked'
            elif now_15 > SLOT0.starttime:
                # From 15 minutes prior to an available slot starting, it is available
                # even if a user has already got a slot booked
                pass
            elif user_sessions0:
                # user already has a slot booked
                page_data[slot0, 'bookit', 'hide'] = True


            # night1
            if seq < start1:
                # sun still up in this slot
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'bookit', 'hide'] = True
                page_data[slot1, 'available', 'para_text'] = 'Sun Up'
            elif seq >= end1:
                # sun rising in this slot
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'bookit', 'hide'] = True
                page_data[slot1, 'available', 'para_text'] = 'Sun Up'
            elif slot1_status:
                # slot unavailable or booked
                page_data[slot1, 'bookit', 'hide'] = True
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'available', 'para_text'] = 'Unavailable'
                if slot1_status == 1:
                    if slot1_user_id == call_data["user_id"]:
                        page_data[slot1, 'bookit', 'hide'] = False
                        page_data[slot1, 'bookit', 'button_text'] = 'Free it'
                        page_data[slot1, 'bookit', 'get_field2'] = "free"
                        page_data[slot1, 'section_class'] = "w3-panel w3-yellow"
                        page_data[slot1, 'available', 'para_text'] = 'Booked by you'
                    else:
                        page_data[slot1, 'section_class'] = "w3-panel w3-red"
                        page_data[slot1, 'available', 'para_text'] = 'Booked'
            elif user_sessions1:
                # user already has a slot booked
                page_data[slot1, 'bookit', 'hide'] = True

    finally:
        database_ops.close_database(con)



def show_terms(skicall):
    "Shows booking terms by refreshing the entire page, with the terms div unhidden"
    members_sessions_index(skicall)
    skicall.page_data['terms', 'hide'] = False


def json_show_terms(skicall):
    "Shows booking terms by setting the terms div unhidden via JSON"
    skicall.page_data['terms', 'hide'] = False


def json_hide_terms(skicall):
    "Hides booking terms by setting the terms div hidden via JSON"
    skicall.page_data['terms', 'hide'] = True


def _slot_from_received_data(received_data):
    "Returns (slot, action) where action is either 'free' or 'book'"

    # Check received data
    if not received_data:
        raise FailPage("Invalid data")
    # received data should be a dictionary with two elements
    received_item = list(received_data.items())
    # received_item is [(key,value), (key,value)]
    if len(received_item) != 2:
        raise FailPage("Invalid data")
    widgfield,action = received_item[0]
    if action == 'book' or action == 'free':
        widgfield,startday_string = received_item[1]
    else:
        startday_string = action
        key, action = received_item[1]

    if (action != 'book') and (action != 'free'):
        raise FailPage("Invalid data")

    if len(widgfield) != 3:
        raise FailPage("Invalid data")
    if (widgfield[1] != 'bookit'):
        raise FailPage("Invalid data")
    if widgfield[2] != 'get_field1':
        raise FailPage("Invalid data")
    string_sequence = widgfield[0].split('_')[-1]
    try:
        sequence = int(string_sequence)
    except:
        raise FailPage("Invalid data")
    if sequence < 2 or sequence > 21:
        raise FailPage("Invalid data")

    # so sequence is sorted
    # now startday
    try:
        startcomponents = [int(i) for i in startday_string.split('-')]
    except:
        raise FailPage("Invalid date")
    if len(startcomponents) != 3:
        raise FailPage("Invalid date")
    year,month,day = startcomponents

    today = datetime.utcnow().date()

    if not ((year == today.year) or (year == today.year + 1)  or (year == today.year - 1)):
        raise FailPage("Invalid date")
    try:
        startday = date(year, month, day)
    except:
        raise FailPage("Invalid date")

    return sun.Slot(startday, sequence), action





def book_session(skicall):
    "Books a session"

    call_data = skicall.call_data
    page_data = skicall.page_data

    slot, action = _slot_from_received_data(skicall.submit_dict['received_data'])
    
    if action == 'free':
        # A request to free a slot, not book it
        _free_session(call_data, slot)
        return

    startday = slot.startday

    # Got the slot, is it valid
    today = datetime.utcnow().date()
    midtoday = datetime(today.year, today.month, today.day, hour=12)
    midtomorrow =  midtoday + timedelta(days=1)
    middayafter =  midtoday + timedelta(days=2)
    now = datetime.utcnow()
    past = now - timedelta(hours=1)
    now_15 = now + timedelta(minutes=15)

    if slot.in_daylight():
        raise FailPage("Invalid date")
    starttime = slot.starttime
    # max start time is less than middayafter
    if starttime>middayafter:
        raise FailPage("Invalid date")

    if starttime < past:
        raise FailPage("Invalid date")

    # If sun has not risen today, max time is less than midtomorrow 
    h_rise, m_rise = sun.sunrise(today)
    if (now.hour < h_rise) and (starttime>midtomorrow):
        raise FailPage("Invalid date")

    # First slot of the night
    firstslot = sun.Slot(startday, 0)
    # Last slot of the night
    lastslot = sun.Slot(startday, 23)

    con = database_ops.open_database()
    try:
        sessions_enabled = database_ops.get_sessions(con)
        if sessions_enabled is None:
            raise FailPage("Database Error")

        if not sessions_enabled:
            raise FailPage("Sessions have been disabled.")

        # Apart from session starting in the next fifteen minutes
        # do not allow a user to book a session if they already have one booked
        if starttime > now_15:
            # List of current slots already booked by this user for this night
            user_sessions = database_ops.get_users_sessions(firstslot.starttime, lastslot.endtime, call_data['user_id'], con)
            if user_sessions is None:
                raise FailPage("Database access error")
            if user_sessions:
                # Check user has not already booked a session for this night
                raise FailPage("You already have a session booked for this night, only one per user is allowed.")

        status_id = database_ops.get_slot_status(slot, con)
        if not status_id:
            raise FailPage("Database access error")

        if status_id[0]:
            raise FailPage("Slot unavailable")

        # slot is ok, book it
        result = database_ops.book_slot(slot, call_data['user_id'], con)
        if result:
            con.commit()
    finally:
        database_ops.close_database(con)
    

def _free_session(call_data, slot):
    "Frees a session"

    con = database_ops.open_database()
    try:
        slot_status_id = database_ops.get_slot_status(slot, con)

        if slot_status_id is None:
            raise FailPage("Unable to get slot info from database")

        slot_status, slot_user_id = slot_status_id

        if (slot_status != 1) or (slot_user_id != call_data["user_id"]):
            raise FailPage("Slot not booked by this user.")

        # Delete the slot, which frees it
        result = database_ops.delete_slot(slot, con)
        if result:
            con.commit()
    finally:
        database_ops.close_database(con)
    


def json_refresh_sessions(skicall):
    "Fills in the members sessions index page via a JSON call"

    call_data = skicall.call_data
    page_data = skicall.page_data

    today = datetime.utcnow().date()
    now = datetime.utcnow()
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
            raise FailPage("Database Error")

        # List of current slots already booked by this user for night0
        user_sessions0 = database_ops.get_users_sessions(night0[0].starttime, night0[-1].endtime, call_data['user_id'], con)
        if user_sessions0 is None:
            raise FailPage("Database access error")

        # List of current slots already booked by this user for night1
        user_sessions1 = database_ops.get_users_sessions(night1[0].starttime, night1[-1].endtime, call_data['user_id'], con)
        if user_sessions1 is None:
            raise FailPage("Database access error")


        for seq in range(0,24):

            if (seq < start_seq) or (seq > end_seq):
                continue

            slot0 = "slot_0_" + str(seq)
            slot1 = "slot_1_" + str(seq)

            SLOT0 = night0[seq - start_seq]
            SLOT1 = night1[seq - start_seq]

            slot0_status_id = database_ops.get_slot_status(SLOT0, con)
            slot1_status_id = database_ops.get_slot_status(SLOT1, con)

            if (slot0_status_id is None) or (slot1_status_id is None):
                raise FailPage("Unable to get slot info from database")

            slot0_status, slot0_user_id = slot0_status_id
            slot1_status, slot1_user_id = slot1_status_id


            page_data[slot0, 'bookit', 'button_text'] = 'Book it'
            page_data[slot0, 'bookit', 'get_field2'] = "book"

            page_data[slot1, 'bookit', 'button_text'] = 'Book it'
            page_data[slot1, 'bookit', 'get_field2'] = "book"

            if sessions_enabled:
                # Default value is sessions are available
                page_data[slot0, 'bookit', 'hide'] = False
                page_data[slot0, 'section_class'] = "w3-panel w3-green"
                page_data[slot0, 'available', 'para_text'] = 'Available'
                page_data[slot1, 'bookit', 'hide'] = False
                page_data[slot1, 'section_class'] = "w3-panel w3-green"
                page_data[slot1, 'available', 'para_text'] = 'Available'
            else:
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Unavailable'
                page_data[slot1, 'bookit', 'hide'] = True
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'available', 'para_text'] = 'Unavailable'


            # night0

            if now_15 > SLOT0.endtime:
                # slot has passed, tests now_15 rather than now, so slot is considered
                # past when it only has 15 or less minutes to go
                # This test only done on night0, since night1 is for tomorrow
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'available', 'para_text'] = 'Past'
            elif seq < start0:
                # sun still up in this slot
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'available', 'para_text'] = 'Sun Up'
            elif seq >= end0:
                # sun rising in this slot
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'available', 'para_text'] = 'Sun Up'
            elif slot0_status:
                # slot unavailable or booked
                page_data[slot0, 'bookit', 'hide'] = True
                page_data[slot0, 'section_class'] = "w3-panel w3-grey"
                page_data[slot0, 'available', 'para_text'] = 'Unavailable'
                if slot0_status == 1:
                    if slot0_user_id == call_data["user_id"]:
                        page_data[slot0, 'bookit', 'hide'] = False
                        page_data[slot0, 'bookit', 'button_text'] = "Free it"
                        page_data[slot0, 'bookit', 'get_field2'] = "free"
                        page_data[slot0, 'section_class'] = "w3-panel w3-yellow"
                        page_data[slot0, 'available', 'para_text'] = 'Booked by you'
                    else:
                        page_data[slot0, 'section_class'] = "w3-panel w3-red"
                        page_data[slot0, 'available', 'para_text'] = 'Booked'
            elif now_15 > SLOT0.starttime:
                # From 15 minutes prior to an available slot starting, it is available
                # even if a user has already got a slot booked
                pass
            elif user_sessions0:
                # user already has a slot booked
                page_data[slot0, 'bookit', 'hide'] = True


            # night1
            if seq < start1:
                # sun still up in this slot
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'bookit', 'hide'] = True
                page_data[slot1, 'available', 'para_text'] = 'Sun Up'
            elif seq >= end1:
                # sun rising in this slot
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'bookit', 'hide'] = True
                page_data[slot1, 'available', 'para_text'] = 'Sun Up'
            elif slot1_status:
                # slot unavailable or booked
                page_data[slot1, 'bookit', 'hide'] = True
                page_data[slot1, 'section_class'] = "w3-panel w3-grey"
                page_data[slot1, 'available', 'para_text'] = 'Unavailable'
                if slot1_status == 1:
                    if slot1_user_id == call_data["user_id"]:
                        page_data[slot1, 'bookit', 'hide'] = False
                        page_data[slot1, 'bookit', 'button_text'] = "Free it"
                        page_data[slot1, 'bookit', 'get_field2'] = "free"
                        page_data[slot1, 'section_class'] = "w3-panel w3-yellow"
                        page_data[slot1, 'available', 'para_text'] = 'Booked by you'
                    else:
                        page_data[slot1, 'section_class'] = "w3-panel w3-red"
                        page_data[slot1, 'available', 'para_text'] = 'Booked'
            elif user_sessions1:
                # user already has a slot booked
                page_data[slot1, 'bookit', 'hide'] = True

    finally:
        database_ops.close_database(con)



# This 'livesession' is available to wrap a submit_data function for telescope control

def livesession(submit_data):
    "Used to decorate submit_data to check if the user has the current session booked"
    @wraps(submit_data)
    def submit_function(skicall):
        "This function raises FailPage if the current session is not valid, if it is, then returns submit_data"
        call_data = skicall.call_data
        if not call_data['loggedin']:
            raise FailPage("You must be logged in to control the telescope")
        user_id = call_data['user_id']
        # does this user own the current session
        if user_id == call_data["booked_user_id"]:
            # the current slot has been booked by the current logged in user,
            # check the door is open
            if redis_ops.get_door(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver")) != "OPEN":
               # booked user, but the door is not open
               raise FailPage("The door is not open.")
            # so continue with submit_data
            # and hence the control of the telescope
            return submit_data(skicall)
        elif call_data["booked_user_id"] is not None:
            # someone else has booked the telescope
            raise FailPage("This slot is booked, and control is only available to the user who has booked it.")
        elif (call_data['role'] == 'ADMIN') and call_data['test_mode']:
            # An admin who has set test_mode can control the telescope outside a 'booked' slot
            # regardless of door position
            return submit_data(skicall)
        else:
           raise FailPage("You do not have control in the current slot.")
        # should never get here
        return
    return submit_function


# This 'doorsession' is available to wrap a submit_data function for door control

def doorsession(submit_data):
    "Used to decorate submit_data to check if the user has the current session booked"
    @wraps(submit_data)
    def submit_function(skicall):
        "This function raises FailPage if the current session is not valid, if it is, then returns submit_data"
        call_data = skicall.call_data
        if not call_data['loggedin']:
            raise FailPage("You must be logged in to control the door and telescope")
        user_id = call_data['user_id']
        # does this user own the current session
        if user_id == call_data["booked_user_id"]:
            # the current slot has been booked by the current logged in user,
            # so continue with submit_data
            # and hence the control of the door
            return submit_data(skicall)
        elif call_data["booked_user_id"] is not None:
            # someone else has booked the telescope
            raise FailPage("This slot is booked, and control is only available to the user who has booked it.")
        elif (call_data['role'] == 'ADMIN') and call_data['test_mode']:
            # An authenticated admin who has set test_mode can control the door and telescope outside a 'booked' slot
            return submit_data(skicall)
        else:
           raise FailPage("You do not have control in the current slot.")
        # should never get here
        return
    return submit_function



