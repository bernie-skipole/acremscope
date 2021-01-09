########################################
#
# These functions edit sessions
#
########################################


from datetime import date, timedelta, datetime

from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import sun, database_ops


def fill_edit_sessions(skicall):
    """Populates the edit sessions page, this is the page shown when an administrator chooses
       sessions from the setup page"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    sessions = database_ops.get_sessions()
    if sessions is None:
        raise FailPage("Database Error")

    if sessions:
        # sessions are enabled
        page_data['enabletext', 'para_text'] = "Sessions Enabled."
        page_data['enable', 'button_text'] = "Disable Sessions"
        page_data['enable', 'link_ident'] = "disable_sessions"
    else:
        page_data['enabletext', 'para_text'] = "Sessions Disabled."
        page_data['enable', 'button_text'] = "Enable Sessions"
        page_data['enable', 'link_ident'] = "enable_sessions"

    today = datetime.utcnow().date()
    now = datetime.utcnow()

    rise_hour, rise_min = sun.sunrisetoday()

    if now.hour < rise_hour:
        # show timeslots from yesterday
        fromdate = today - timedelta(days=1)
    else:
        fromdate = today

    nextday = fromdate + timedelta(days=1)
    postday = nextday + timedelta(days=1)

    page_data['today', 'button_text'] = fromdate.strftime("%A %B %d, %Y")
    page_data['today', 'get_field1'] = fromdate.isoformat()

    page_data['tomorrow', 'button_text'] = nextday.strftime("%A %B %d, %Y")
    page_data['tomorrow', 'get_field1'] = nextday.isoformat()

    page_data['dayafter', 'button_text'] = postday.strftime("%A %B %d, %Y")
    page_data['dayafter', 'get_field1'] = postday.isoformat()


def enable_sessions(skicall):
    "Enable sessions"

    if not database_ops.set_sessions(True):
        raise FailPage("Database Error")


def disable_sessions(skicall):
    "Disable sessions"

    if not database_ops.set_sessions(False):
        raise FailPage("Database Error")


def _get_startday(startday_string, call_data):
    """Given a start day string, return date object startday
       and also put firstday, today, lastday into call_data"""

    # get today
    # get lastday, where lastday is the latest time at which slots can be administered
    # currently today plus six days
    # and firstday, where firstday is the earliest time at which slots can be administered
    # currently yesterday

    if 'today' in call_data:
        today = call_data['today']
    else:
        today = datetime.utcnow().date()
        call_data['today'] = today

    if 'firstday' in call_data:
        firstday = call_data['firstday']
    else:
        firstday = today - timedelta(days=1)
        call_data['firstday'] = firstday

    if 'lastday' in call_data:
        lastday = call_data['lastday']
    else:
        lastday = today + timedelta(days=6)
        call_data['lastday'] = lastday

    try:
        startcomponents = [int(i) for i in startday_string.split('-')]
    except:
        raise FailPage("Invalid date")
    if len(startcomponents) != 3:
        raise FailPage("Invalid date")
    year,month,day = startcomponents
    if not ((year == today.year) or (year == today.year + 1)  or (year == today.year - 1)):
        raise FailPage("Invalid date")
    try:
        startday = date(year, month, day)
    except:
        raise FailPage("Invalid date")

    if startday > lastday:
        raise FailPage("Cannot set sessions that far ahead")
    if startday < firstday:
        raise FailPage("Cannot set sessions for the past")

    return startday


def _get_slot(string_sequence, call_data):
    "Given a string sequence, return the slot"
    try:
        sequence = int(string_sequence)
    except:
        raise FailPage("Invalid data")
    if sequence < 2 or sequence > 21:
        raise FailPage("Invalid data")
    slot = sun.Slot(call_data['startday'], sequence)
    if slot.in_daylight():
        raise FailPage("Invalid data")
    return slot


def list_slots(skicall):
    "Lists slots for the night, for admin users"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day being edited, either from get_fields
    # or previously calculated and set into call_data['startday']

    if 'startday' in call_data:
        startday = call_data['startday']
    else:
        # from get fields
        if call_data['today', 'get_field1']:
            startday = _get_startday(call_data['today', 'get_field1'], call_data)
        elif call_data['tomorrow', 'get_field1']:
            startday = _get_startday(call_data['tomorrow', 'get_field1'], call_data)
        elif call_data['dayafter', 'get_field1']:
            startday = _get_startday(call_data['dayafter', 'get_field1'], call_data)
        else:
            raise FailPage("Invalid date")

    call_data['set_values']["session_date_ident"] = startday.isoformat().replace('-','_')

    endday = startday + timedelta(days=1)

    now = datetime.utcnow()
    now_15 = now + timedelta(minutes=15)

    page_data['evenning', 'para_text'] = "Evenning of " + startday.strftime("%A %B %d, %Y")
    page_data['morning', 'para_text'] = "Morning of " + endday.strftime("%A %B %d, %Y")

    slots = sun.night_slots(startday)
    contents = []

    #     contents: col 0 is the text to place in the first column,
    #               col 1, 2, 3, 4 are the get field contents of links 1,2,3 and 4
    #               col 5 - True if the first button and link is to be shown, False if not
    #               col 6 - True if the second button and link is to be shown, False if not
    #               col 7 - True if the third button and link is to be shown, False if not
    #               col 8 - True if the fourth button and link is to be shown, False if not

    # col0_classes is a list of classes for the text column
    col0_classes = []

    con = database_ops.open_database()
    try:

        sessions_enabled = database_ops.get_sessions(con)

        for slot in slots:

            but1 = False
            but2 = False
            but3 = False
            but4 = False

            column_text = str(slot)
            status, user_id = database_ops.get_slot_status(slot, con)

            if now_15 > slot.endtime:
                # slot has passed, tests now_15 rather than now, so slot is considered
                # past when it only has 15 or less minutes to go, cannot be booked, enabled or disabled
                col0_classes.append('w3-grey')
                column_text = column_text + " Past"
            elif not status:
                if sessions_enabled:
                    # session available, but can be booked or disabled
                    col0_classes.append('w3-green')
                    but3 = True
                    but4 = True
                else:
                    # session disabled
                    col0_classes.append('w3-grey')
            elif status == 1:
                # session booked
                col0_classes.append('w3-red')
                # can be freed
                but1 = True
                # get the username
                user = database_ops.get_user_from_id(user_id, con)
                if user is not None:
                    username, role, email, member = user
                    column_text = column_text + " Booked by: " + username
                    if member:
                        if role == 'MEMBER':
                            column_text = column_text + " Member: " + member
                        elif role == 'GUEST':
                            column_text = column_text + " Guest: " + member
                        elif role == 'ADMIN':
                            column_text = column_text + " Admin: " + member
            else:
                # session disabled
                col0_classes.append('w3-grey')
                if sessions_enabled:
                    # can enable it
                    but2 = True

            str_seq = str(slot.sequence)

            row = [column_text, 
                   str_seq,
                   str_seq,
                   str_seq,
                   str_seq,
                   but1,
                   but2,
                   but3,
                   but4 ]

            contents.append(row)

    finally:
        database_ops.close_database(con)

    page_data['slots', 'contents'] = contents
    page_data['slots', 'col0_classes'] = col0_classes

    # previous and next buttons
    if startday <= call_data['firstday']:
        page_data['previous', 'show'] = False
    if startday >= call_data['lastday']:
        page_data['next', 'show'] = False


def next_day(skicall):
    "Choose the next day to edit"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    new_startday = _get_startday(startday_string, call_data) + timedelta(days=1)
    if new_startday > call_data['lastday']:
        raise FailPage("Cannot set sessions that far ahead")
    call_data["startday"] = new_startday
    # and list the slots
    list_slots(skicall)


def prev_day(skicall):
    "Choose the previous day to edit"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    new_startday = _get_startday(startday_string, call_data) - timedelta(days=1)
    if new_startday < call_data['firstday']:
        raise FailPage("Cannot set sessions for the past")
    call_data["startday"] = new_startday
    # and list the slots
    list_slots(skicall)


def disable_slot(skicall):
    "Disable a slot"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)
    slot = _get_slot(call_data['slots','btn_col3'], call_data)
    sessions = database_ops.get_sessions()
    if sessions is None:
        raise FailPage("Database Error")
    if not sessions:
        raise FailPage("Cannot disable the session")
    database_ops.disable_slot(slot)
    # and list the slots
    list_slots(skicall)


def enable_slot(skicall):
    "Enables a slot"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)
    slot = _get_slot(call_data['slots','btn_col2'], call_data)

    con = database_ops.open_database()
    try:
        sessions = database_ops.get_sessions(con)
        if sessions is None:
            raise FailPage("Database Error")
        if not sessions:
            raise FailPage("Cannot enable the session")
        slot_status_id = database_ops.get_slot_status(slot, con)
        if slot_status_id is None:
            raise FailPage("Unable to get slot info from database")
        slot_status, slot_user_id = slot_status_id
        if (slot_status != 2):
            raise FailPage("Slot must be disabled to enable it.")
        # Delete the slot, which enables it
        result = database_ops.delete_slot(slot, con)
        if result:
            con.commit()
    finally:
        database_ops.close_database(con)
    # and list the slots
    list_slots(skicall)


def confirm_free_slot(skicall):
    "Fills in confirm button get field"
    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)
    slot = _get_slot(call_data['slots','btn_col1'], call_data)
    con = database_ops.open_database()
    try:
        slot_status_id = database_ops.get_slot_status(slot, con)
        if slot_status_id is None:
            raise FailPage("Unable to get slot info from database")
        slot_status, slot_user_id = slot_status_id
        if (slot_status != 1):
            raise FailPage("Slot must be booked to free it.")
        # get username, membership number and email address
        user = database_ops.get_user_from_id(slot_user_id, con)
        if user is None:
            raise FailPage("Unable to get user info from database")
        username, role, email, member = user 
    finally:
        database_ops.close_database(con)

    page_data['timeslot', 'para_text'] = slot.starttime.strftime("%A %B %d, %Y") + "\n" + str(slot)
    page_data['user', 'para_text'] = """Username: %s
Member: %s
Email: %s

Please confirm you wish to free this session.""" % (username, member, email)
    page_data['confirm', 'get_field1'] = str(slot.sequence)
    call_data['set_values']["session_date_ident"] = call_data["startday"].isoformat().replace('-','_')


def this_day(skicall):
    "Choose the day to edit"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)
    # and list the slots
    list_slots(skicall)



def free_slot(skicall):
    "Frees a slot"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)
    slot = _get_slot(call_data['confirm','get_field1'], call_data)
    con = database_ops.open_database()
    try:
        slot_status_id = database_ops.get_slot_status(slot, con)

        if slot_status_id is None:
            raise FailPage("Unable to get slot info from database")

        slot_status, slot_user_id = slot_status_id

        if slot_status == 2:
            raise FailPage("Cannot free a diisabled slot.")
        elif slot_status != 1:
            raise FailPage("This slot has not been booked.")

        # Delete the slot, which frees it
        result = database_ops.delete_slot(slot, con)
        if result:
            con.commit()
    finally:
        database_ops.close_database(con)

    # and list the slots
    list_slots(skicall)


def confirm_book_slot(skicall):
    "Checks slot can be booked, and gives user search info"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)
    slot = _get_slot(call_data['slots','btn_col4'], call_data)
    slot_status_id = database_ops.get_slot_status(slot)
    if slot_status_id is None:
        raise FailPage("Unable to get slot info from database")
    slot_status, slot_user_id = slot_status_id
    if (slot_status != 0):
        raise FailPage("Slot must be free to book it.")

    page_data['timeslot', 'para_text'] = slot.starttime.strftime("%A %B %d, %Y") + "\n" + str(slot)

    show_book_users_page(page_data, slot)

    call_data['set_values']["session_date_ident"] = call_data["startday"].isoformat().replace('-','_')



def show_book_users_page(page_data, slot, offset=0, names=True):
    """Fills in  table ordered by name or membership number"""

    #  users,contents: 
    #  col 0 and 1 are the text strings to place in the first two columns,
    #  col 2 is the get field contents of the button link

    contents = []
    rows = 10
    getrows = rows+5
    seq = str(slot.sequence)
    _seq = '_' + str(slot.sequence)

    # table can be ordered by name or membership number

    page_data['order', 'get_field1'] = seq

    if names:
        page_data['order', 'button_text'] = 'membership number'
        page_data['order', 'link_ident'] = 'book_members'
        page_data['next', 'link_ident'] = 'users'
        page_data['previous', 'link_ident'] = 'users'
    else:
        page_data['order', 'button_text'] = 'username'
        page_data['order', 'link_ident'] = 'book_users'
        page_data['next', 'link_ident'] = 'members'
        page_data['previous', 'link_ident'] = 'members'

    # get_users returns user_id, username, role, membership number

    if not offset:
        u_list = database_ops.get_users(limit=getrows, names=names)
        if len(u_list) == getrows:
            u_list = u_list[:-5]
            page_data['next', 'get_field1'] = rows
            page_data['next', 'get_field2'] = seq
        else:
            page_data['next', 'show'] = False
        for u in u_list:
            user_row = [u[1], u[3], str(u[0]) + _seq ]
            contents.append(user_row)
        page_data['users', 'contents'] = contents
        # no previous button
        page_data['previous', 'show'] = False
        return
    # so an offset is given
    u_list = database_ops.get_users(limit=getrows, offset=offset, names=names)
    if len(u_list) == getrows:
        u_list = u_list[:-5]
        page_data['next', 'get_field1'] = offset + rows
        page_data['next', 'get_field2'] = seq
    else:
        page_data['next', 'show'] = False
    str_offset = str(offset)
    for u in u_list:
        user_row = [u[1], u[3], str(u[0]) + _seq]
        contents.append(user_row)
    page_data['users', 'contents'] = contents
    # set previous button
    if offset == 0:
        page_data['previous', 'show'] = False
    elif offset < rows:
        page_data['previous', 'get_field1'] = 0
        page_data['previous', 'get_field2'] = seq
    else:
        page_data['previous', 'get_field1'] = offset - rows
        page_data['previous', 'get_field2'] = seq


def book_users(skicall):
    "Fills in editusers index page, populates table ordered by name"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Called by responder ??
    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)
    slot = _get_slot(call_data['order', 'get_field1'], call_data)
    slot_status_id = database_ops.get_slot_status(slot)
    if slot_status_id is None:
        raise FailPage("Unable to get slot info from database")
    slot_status, slot_user_id = slot_status_id
    if (slot_status != 0):
        raise FailPage("Slot must be free to book it.")

    page_data['timeslot', 'para_text'] = slot.starttime.strftime("%A %B %d, %Y") + "\n" + str(slot)

    show_book_users_page(page_data, slot, offset=0, names=True)

    call_data['set_values']["session_date_ident"] = call_data["startday"].isoformat().replace('-','_')


def book_members(skicall):
    "Fills in editusers index page, populates table ordered by membership number"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Called by responder ??
    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)
    slot = _get_slot(call_data['order', 'get_field1'], call_data)
    slot_status_id = database_ops.get_slot_status(slot)
    if slot_status_id is None:
        raise FailPage("Unable to get slot info from database")
    slot_status, slot_user_id = slot_status_id
    if (slot_status != 0):
        raise FailPage("Slot must be free to book it.")

    page_data['timeslot', 'para_text'] = slot.starttime.strftime("%A %B %d, %Y") + "\n" + str(slot)

    show_book_users_page(page_data, slot, offset=0, names=False)

    call_data['set_values']["session_date_ident"] = call_data["startday"].isoformat().replace('-','_')


def book_slot(skicall):
    "books the slot"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)

    user_seq = call_data['users','contents'].split('_')
    if len(user_seq) != 2:
        raise FailPage("Invalid data sent")
    try:
        user_id = int(user_seq[0])
    except:
        raise FailPage("Invalid data sent")
    slot =  _get_slot(user_seq[1], call_data)
    con = database_ops.open_database()
    try:
        sessions_enabled = database_ops.get_sessions(con)
        if sessions_enabled is None:
            raise FailPage("Database Error")

        if not sessions_enabled:
            raise FailPage("Sessions have been disabled.")

        slot_status_id = database_ops.get_slot_status(slot, con)

        if slot_status_id is None:
            raise FailPage("Unable to get slot info from database")

        slot_status, slot_user_id = slot_status_id

        if slot_status:
            raise FailPage("Slot unavailable")

        # get user
        user = database_ops.get_user_from_id(user_id, con)
        if user is None:
            raise FailPage("User not recognised")

        # slot and user are ok, book it
        result = database_ops.book_slot(slot, user_id, con)
        if result:
            con.commit()
    finally:
        database_ops.close_database(con)

    # and list the slots
    list_slots(skicall)

    
def next_users(skicall):
    "Populates table ordered by username, gets next page of users"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)

    if (('next', 'get_field2') in call_data) and call_data['next', 'get_field2']:
        seq = call_data['next', 'get_field2']
    elif (('previous', 'get_field2') in call_data) and call_data['previous', 'get_field2']:
        seq = call_data['previous', 'get_field2']
    else:
        raise FailPage("Invalid data")

    slot = _get_slot(seq, call_data)

    if (('next', 'get_field1') in call_data) and call_data['next', 'get_field1']:
        try:
            offset = int(call_data['next', 'get_field1'])
        except:
            offset = 0
    elif (('previous', 'get_field1') in call_data) and call_data['previous', 'get_field1']:
        try:
            offset = int(call_data['previous', 'get_field1'])
        except:
            offset = 0
    else:
        offset = 0

    page_data['timeslot', 'para_text'] = slot.starttime.strftime("%A %B %d, %Y") + "\n" + str(slot)
    show_book_users_page(page_data, slot, offset=offset, names=True)
    call_data['set_values']["session_date_ident"] = call_data["startday"].isoformat().replace('-','_')


def next_members(skicall):
    "Populates table ordered by membership number, gets next page of members"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Get the day, sent by ident_data
    if call_data['stored_values']['session_date']:
        startday_string = call_data['stored_values']['session_date'].replace('_','-')
    else:
        raise FailPage("Invalid date")
    call_data["startday"] = _get_startday(startday_string, call_data)

    if (('next', 'get_field2') in call_data) and call_data['next', 'get_field2']:
        seq = call_data['next', 'get_field2']
    elif (('previous', 'get_field2') in call_data) and call_data['previous', 'get_field2']:
        seq = call_data['previous', 'get_field2']
    else:
        raise FailPage("Invalid data")

    slot = _get_slot(seq, call_data)

    if (('next', 'get_field1') in call_data) and call_data['next', 'get_field1']:
        try:
            offset = int(call_data['next', 'get_field1'])
        except:
            offset = 0
    elif (('previous', 'get_field1') in call_data) and call_data['previous', 'get_field1']:
        try:
            offset = int(call_data['previous', 'get_field1'])
        except:
            offset = 0
    else:
        offset = 0

    page_data['timeslot', 'para_text'] = slot.starttime.strftime("%A %B %d, %Y") + "\n" + str(slot)
    show_book_users_page(page_data, slot, offset=offset, names=False)
    call_data['set_values']["session_date_ident"] = call_data["startday"].isoformat().replace('-','_')




