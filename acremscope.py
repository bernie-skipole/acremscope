

"""
This script will be run by systemd on startup and will serve on port 8000
of a container.

The host server will use nginx to forward calls to this port 8000
"""

import os, sys, random

from skipole import WSGIApplication, FailPage, GoTo, ValidateError, ServerError, set_debug, use_submit_list, skis, PageData, SectionData

from indi_mr import redis_server

import indiredis

# the framework needs to know the location of the projectfiles directory holding this project

PROJECTFILES = os.path.dirname(os.path.realpath(__file__))
PROJECT = 'acremscope'

from acremscope_packages import sun, database_ops, redis_ops, cfg


# set PROJECTFILES into cfg, used to specify where astrodata and contents can be found
cfg.set_projectfiles(PROJECTFILES)

# redis server settings from cfg.py
redis_ip, redis_port, redis_auth = cfg.get_redis()

# set these into REDISSERVER tuple, with dbase 0, as used by indi_mr and indiredis
# uses the default indi_mr redis prefix
REDISSERVER = redis_server(host=redis_ip, port=redis_port, db=0, password=redis_auth)


# _IDENT_DATA is used as part of a key to store data within redis
_IDENT_DATA = random.randrange(1, 9999)

# These pages can be accessed by anyone, without the need to login
_UNPROTECTED_PAGES = [1,         # index
                      2,         # about
                      3,         # unavailable
                      10,        # url not found page
                      1010,      # w3.css page
                      1020,      # w3-theme-ski.css page
                      1030,      # ski.css page
                      1040,      # chart.css page
                      1050,      # planchart.css page
                      6001,      # Control index, for non-logged in page
                      6002,      # Refresh LED status
                      6003,      # Turn LED on
                      6004,      # Turn LED off
                      7001,      # Sensors index
                      7003,      # sensors refresh
                      4001,      # public sessions index
                      5001,      # logon page
                      5002,      # check login
                     10002,      # scope.svg
                     10003,      # logo.svg
                     10004,      # left.png
                     10005,      # right.png
                     10006,      # hleft.png
                     10007,      # hright.png
                     10008,      # file_not_found.png
                     10009,      # icon.svg image
                     12001,      # astro centre image
                     20001,      # weather - responder to weather page
                     20002,      # json update responder for weather page
                     30101,      # session planning
                     30102,      # session planning calculate
                     30103,      # detail ephemeris calculation over an hour interval
                     30104,      # back to session table display
                     30105,      # detail printout
                     30106,      # planetarium
                     30107,      # back to finder chart from planetarium
                     30111,      # request finder chart
                     30112,      # Change view
                     30113,      # rotate plus 20
                     30114,      # rotate minus 20
                     30115,      # flip horizontally
                     30116,      # flip vertically
                     30117,      # print finder chart
                     30120,      # up arrow
                     30121,      # left arrow
                     30122,      # right arrow
                     30123,      # down arrow
                     30124,      # up arrow json
                     30125,      # left arrow json
                     30126,      # right arrow json
                     30127,      # down arrow json
                     30130,      # plus zoom html
                     30131,      # minus zoom html
                     30132,      # plus zoom json
                     30133,      # minus zoom json
                     30134,      # change view json
                     30201,      # planets
                     30202,      # deatail_planet
                     30203,      # session_planets
                    ]

# These pages can be accessed by anyone who is logged in
_LOGGED_IN_PAGES = [4002,        # members sessions index
                    4003,        # book a session
                    4004,        # free a session
                    4005,        # json book a session
                    4006,        # json free a session
                    4007,        # shows booking terms
                    4008,        # shows booking terms via JSON
                    4009,        # hide booking terms via JSON
                    5003,        # logout
                    6005,        # indi
                    6101,        # logged in control
                    6102,        # refreshes logged in control page
                    6103,        # html door control
                    6104,        # altaz control
                   70001,        # telescope control   ####### 70000 range for telescope GOTO controls
                   70002,        # radec input
                   70003,        # name radec input
                   70004,        # plus_view
                   70005,        # minus_view
                   70006,        # flip_h
                   70007,        # flip_v
                   70008,        # rotate_plus
                   70009,        # rotate_minus
                   70010,        # up_arrow
                   70011,        # left_arrow
                   70012,        # right_arrow
                   70013,        # down_arrow
                   70020,        # goto
                   70021,        # display target or actual
                   70022         # chart interval refresh page
                    ]


# These pages can be accessed by ADMIN or MEMBERS who are logged in (Not guests)
_MEMBERS_PAGES =   [
                    3402,        # new guest password
                    3403,        # new guest password json
                    3404,        # add guest
                    3405,        # submit_add_guest
                    3406,        # confirm delete guest
                    3407,        # submit delete guest
                    3408,        # confirm_delete_guest_json
                    8001,        # user settings index
                    8002,        # new password
                    8003,        # new email
                    8004,        # confirm de-register oneself
                    8005         # de-register oneself
                    ]

# Any other pages, the user must be both logged in and have admin role

# Lists requests for JSON pages
_JSON_PAGES = [8004,            # de-regiser yourself
               4005,            # json_book_session
               4006,            # json_free_session
               3065,            # json_confirm_delete_user
               3075,            # json_confirm_delete_member
               3403,            # new guest password json
               3408,            # confirm_delete_guest_json
               6002,            # refreshes public control page
               6102,            # refreshes logged in control page
               7011,            # event log json
              20002,            # json update responder for weather page
              30113,            # rotate plus 20
              30114,
              30115,
              30116,
              30124,            # up arrow json
              30125,            # left arrow json
              30126,            # right arrow json
              30127,            # down arrow json
              30132,            # plus zoom json
              30133,            # minus zoom json
              30134,            # set view json
                            ##### logged in control
              70002,        # radec input
              70003,        # name radec input
              70004,        # plus_view
              70005,        # minus_view
              70006,        # flip_h
              70007,        # flip_v
              70008,        # rotate_plus
              70009,        # rotate_minus
              70010,        # up_arrow
              70011,        # left_arrow
              70012,        # right_arrow
              70013,        # down_arrow
              70020,        # goto
              70021,        # display target or actual
              70022         # chart interval refresh page
              ]
# This list is required to ensure code knows a JSON call has been requested

# Any other pages, the user must be both logged in and have admin role


def make_proj_data():
    """create a redis connection and sets of redis prefixes to keys
       to be used as proj_data"""
    rconn = redis_ops.open_redis(redis_db=0)
    return {'rconn': rconn,
            'rconn_0':"remscope_various_",  # should match prefix-key used in cron jobs which do any logging to redis
            'rconn_1':"remscope_logged_in_",
            'rconn_2':"remscope_authenticated_",
            'rconn_3':"remscope_pintrycounts_",
            'rconn_4':"remscope_sessions_",
            'projectfiles':PROJECTFILES,
            'redisserver':REDISSERVER}


def start_call(called_ident, skicall):
    "When a call is initially received this function is called."

    if called_ident is None:
        # Force url not found if no called_ident
        return

    # set initial call_data values
    skicall.call_data = { "project":skicall.project,
                          "pagedata": PageData(),
                          "called_ident":called_ident,
                          "authenticated":False,
                          "loggedin":False,
                          "booked_user_id":None,       # The booked user of the current session if any
                          "role":"",
                          "json_requested":False,
                          "projectfiles":skicall.proj_data["projectfiles"],
                          "path":skicall.path,
                          "stored_values":{},
                          "set_values":{},
                          "test_mode":False }           # test_mode is True if this user is admin and has set it


    call_data = skicall.call_data


    ####### get planning parameters from ident_data #######

    if skicall.ident_data and ('X' in skicall.ident_data):
        # get stored values from redis and populate skicall.call_data['stored_values']
        _get_stored_values(skicall, skicall.ident_data)


    ####### If the user is logged in, populate call_data

    user = None
    if skicall.received_cookies:
        cookie_name = skicall.project + '2'
        if cookie_name in skicall.received_cookies:
            cookie_string = skicall.received_cookies[cookie_name]
            # so a recognised cookie has arrived, check redis to see if the user has logged in
            user_id = redis_ops.logged_in(cookie_string, skicall.proj_data.get("rconn_1"), skicall.proj_data.get("rconn"))
            if user_id:
                user = database_ops.get_user_from_id(user_id)
                # user is (username, role, email, member) on None on failure
                if user:
                    call_data['loggedin'] = True
                    call_data['user_id'] =  user_id
                    call_data['username'] = user[0]
                    call_data['role'] = user[1]
                    call_data['email'] = user[2]
                    call_data['member'] = user[3]
                    call_data['cookie'] = cookie_string
                    if user[1] != 'ADMIN':
                        call_data['authenticated'] = False
                    else:
                        # Is this user authenticated
                        call_data['authenticated'] = redis_ops.is_authenticated(cookie_string, skicall.proj_data.get("rconn_2"), skicall.proj_data.get("rconn"))

    ### Check the page being called
    page_num = called_ident[1]

    if page_num in _JSON_PAGES:
        call_data['json_requested'] = True

    ####### unprotected pages

    if page_num in _UNPROTECTED_PAGES:
        # Go straight to the page
        return called_ident

    # if user not logged in, cannot choose any other page
    if user is None:
        # stop user from calling any other page - divert to home or page not found
        if skicall.caller_ident and call_data['json_requested']:
            # divert to the home page
            skicall.page_data["JSONtoHTML"] = 'home'
            return "general_json"
        # otherwise divert to page not found
        return

    ###### So user is logged in, and call_data is populated


    # control_user_id records who is controlling the telescope chart, if someone
    # new comes along, either a new session booked user or a test user, then this
    # person is set to be the control_user_id and the chart is reset. But in
    # subsequent calls, as this person already is the control_user_id, there is no need
    # to reset the chart.


    rconn_0 = skicall.proj_data.get("rconn_0")
    rconn = skicall.proj_data.get("rconn")

    # get user who is currently controlling the telescope, if any
    control_user_id = redis_ops.get_control_user(rconn_0, rconn)
    test_mode_user_id = redis_ops.get_test_mode_user(rconn_0, rconn)
    # is the current slot live, and if so who owns it?
    slot_status = database_ops.get_slot_status(sun.Slot.now())
    if (slot_status is None) and (test_mode_user_id == user_id):
        # no current slot, but this user has test mode
        call_data["test_mode"] = True
        if control_user_id != user_id:
            # This sets the control user, and resets the chart view
            redis_ops.set_control_user(user_id, rconn_0, rconn)
    elif slot_status is not None:
        # there is a current slot, which may or may not be booked
        status, booked_user_id = slot_status
        if status == 1:
            # slot is booked (0 is not booked, 2 is disabled)
            call_data["booked_user_id"] = booked_user_id
            # so is this booked user the control user?
            if control_user_id != booked_user_id:
                # This sets the control user, and resets the chart view
                redis_ops.set_control_user(booked_user_id, rconn_0, rconn)
            # A booked user disables test mode
            if test_mode_user_id is not None:
                redis_ops.delete_test_mode(rconn_0, rconn)
        elif test_mode_user_id == user_id:
            # no current booking, but this user has test mode
            call_data["test_mode"] = True
            if control_user_id != user_id:
                # This sets the control user, and resets the chart view
                redis_ops.set_control_user(user_id, rconn_0, rconn)

    # If access is required to any of these pages, can now go to page
    if page_num in _LOGGED_IN_PAGES:
        return called_ident


    ###### For these pages the user must be a member or admin (not a guest)
    if call_data['role'] == 'GUEST':
        # stop user from calling any other page - divert to home or page not found
        if skicall.caller_ident and call_data['json_requested']:
            # divert to the home page
            skicall.page_data["JSONtoHTML"] = 'home'
            return "general_json"
        # otherwise divert to page not found
        return

    if page_num in _MEMBERS_PAGES:
        return called_ident


    ###### So for any remaining page the user must have ADMIN role and be authenticated
    
    # if not admin, cannot proceed
    if call_data['role'] != 'ADMIN':
        # stop user from calling any other page - divert to home or page not found
        if skicall.caller_ident and call_data['json_requested']:
            # divert to the home page
            skicall.page_data["JSONtoHTML"] = 'home'
            return "general_json"
        # otherwise divert to page not found
        return

    ### All admin pages require the caller page to set caller_ident
    ### So if no caller ident redirect to home page
    if not skicall.caller_ident:
        return 'home'

    # So user is an ADMIN, is he authenticated?
    if not call_data['authenticated']:
        # unauthenticated admin allowed to call 'check_login' page to become authenticated
        if page_num == 5021:
            return called_ident
        # Unauthenticated - jump to PIN page
        if call_data['json_requested']:
            # divert to the PIN page
            skicall.page_data["JSONtoHTML"] = 'input_pin'
            return "general_json"
        return 'input_pin'

    # So user is both a logged in Admin user, and authenticated,

    # An authenticated user should never call pages to become authenticated, as he is already there
    if (page_num == 5021) or (page_num == 5515):
        return 'home'

    # can go to any remaining page
    return called_ident


@use_submit_list
def submit_data(skicall):
    """This function is called when a Responder wishes to submit data for processing in some manner
       For two or more submit_list values, the decorator ensures the matching function is called instead"""

    raise FailPage("submit_list string not recognised")


_HEADER_TEXT = {    2: "About this web site build.",
                 2001: "Home Page",
                 3351: "Web Settings",
                 3501: "Setup Page",
                 3510: "Add User Page",
                 3520: "Server Settings Page",
                 3540: "Edit Users Page",
                 3610: "Edit User Page",
                 3620: "Set administrator PIN",
                 3701: "Sessions Control",
                 3702: "Choose a session",
                 3703: "Confirm free session",
                 3720: "Book a session",
                 3910: "Add a guest user",
                 4501: "Sessions Page",
                 4502: "Book Session Page",
                 5501: "Login Page",
                 5510: "Logged In",
                 5520: "PIN Required",
                 5530: "Authenticated",
                 5540: "PIN Fail",
                 6501: "Control Page",   # public control
                 6601: "Control Page",   # logged in control
                 6605: "INDI Client",
                 7501: "Sensors Page",
                 7502: "Temperature Logs",
                 8501: "Your Settings Page",
                 8601: "New PIN",
                11101: "WEBCAM",
                11150: "Time Lapse",
                21001: "Weather Station",
                30151: "Session Planning",
                30153: "Target Ephemeris",
                30154: "Target Ephemeris",
                30156: "Planetarium",
                30161: "Finder chart",
                30251: "Planet Positions",
                75002: "Telescope Alt Az control"
               }


def end_call(page_ident, page_type, skicall):
    """This function is called at the end of a call prior to filling the returned page with page_data."""

    global _IDENT_DATA

    call_data = skicall.call_data
    page_data = skicall.page_data

    # if skicall.call_data['set_values'] contains some data, then store it in redis
    # and set the key as an ident_data
    ident_data_key = _set_stored_values(skicall)
    if ident_data_key:
        page_data['ident_data'] = ident_data_key

    if page_type != "TemplatePage":
        return

    page_num = page_ident[1]

    # pages with no header or navigation
    if page_num in [
                    30155,                 # detail planning printout
                    30162,                 # finder chart printout
                    75001                  # telescope control template
                    ]:
        return

    page_data['header','headtitle','tag_text'] = database_ops.get_text('header_text')

    if 'header_text' in call_data:
        page_data['header', 'headpara', 'para_text'] = call_data['header_text']
    elif page_num in _HEADER_TEXT:
        page_data['header', 'headpara', 'para_text'] = _HEADER_TEXT[page_num]
    else:
        page_data['header', 'headpara', 'para_text'] = "Error: Header text not set in end_call" 


    ### Left navigation buttons ###

    nav_buttons = [['home','Home', True, ''],
                   ['weather','Weather Station', True, ''],
                   ['sensors','Sensors', True, '']
                   ]


    if ('loggedin' not in call_data) or (not call_data['loggedin']):
        # user is not logged in
        nav_buttons.append( ['control','Control', True, ''])      # goes to public control page, LED only, not telescopecontrol
        nav_buttons.append( ['sessions','Sessions', True, ''])
        nav_buttons.append( ['planning','Planning', True, ''])
        if page_num != 5501:
            # If not already at the login page, then add a Login option to nav buttons
            nav_buttons.append( ['login','Login', True, ''])
        page_data['navigation', 'navbuttons', 'nav_links'] = nav_buttons
        return

    ## User is logged in, could be GUEST, MEMBER or ADMIN ##

    if call_data['role'] not in ['GUEST', 'MEMBER', 'ADMIN']:
        # something wrong
        return

    page_data['header', 'user', 'para_text']  = "Logged in : " + call_data['username']
    page_data['header', 'user', 'show']  = True

    # show the header logout button
    page_data['header', 'navlogout', 'show'] = True

    # links for logged in users
    nav_buttons.append( ['telescope','Control', True, ''])
    nav_buttons.append( ['members_sessions_index','Book Session', True, ''])
    nav_buttons.append( ['planning','Planning', True, ''])

    if call_data['role'] == 'GUEST':
        # and guests have no further options
        page_data['navigation', 'navbuttons', 'nav_links'] = nav_buttons
        return
    
    # Your Settings option
    nav_buttons.append( ['usersettings','Your Settings', True, ''])

    # "Add Guest" button if member has guests enabled
    if call_data['role'] == 'MEMBER':
        number = database_ops.number_of_guests(call_data['user_id'])
        if number:
            nav_buttons.append( ['addguest','Add Guest', True, ''])
        # and no further options
        page_data['navigation', 'navbuttons', 'nav_links'] = nav_buttons
        return

    # remaining settings for admin users only
    nav_buttons.append( ['addguest','Add Guest', True, ''])
    nav_buttons.append( ['setup','Admin', True, ''])
    page_data['navigation', 'navbuttons', 'nav_links'] = nav_buttons
    return


def _get_stored_values(skicall, key_string):
    """Given a key_string, get stored values and insert them
       in a dictionary under skicall.call_data['stored_values']"""

    stored_values = skicall.call_data['stored_values']

    value_list = redis_ops.get_session_value(key_string, skicall.proj_data.get("rconn_4"), skicall.proj_data.get("rconn"))
    if value_list:
        if value_list[0]:
            stored_values['starchart'] = value_list[0]
        if value_list[1]:
            stored_values['planning_date'] = value_list[1]
        if value_list[2]:
            stored_values['session_date'] = value_list[2]
        if value_list[3]:
            stored_values['target_name'] = value_list[3]
        if value_list[4]:
            stored_values['target_date'] = value_list[4]
        if value_list[5]:
            stored_values['target_time'] = value_list[5]
        if value_list[6]:
            stored_values['target_ra'] = value_list[6]
        if value_list[7]:
            stored_values['target_dec'] = value_list[7]
        if value_list[8]:
            stored_values['target_alt'] = value_list[8]
        if value_list[9]:
            stored_values['target_az'] = value_list[9]
        if value_list[10]:
            stored_values['view'] = value_list[10]
        if value_list[11]:
            stored_values['back'] = value_list[11]
        if value_list[12]:      # value_list is either 'true' or empty string
            stored_values['flip'] = True
        else:
            stored_values['flip'] = False
        if value_list[13]:
            stored_values['rot'] = int(value_list[13])
        else:
            stored_values['rot'] = 0




def _set_stored_values(skicall):
    "If items have been set into skicall.call_data['set_values'], store them in redis and return the key"

    global _IDENT_DATA

    if 'set_values' not in skicall.call_data:
        return
    if not skicall.call_data['set_values']:
        return

    set_values = skicall.call_data['set_values']

    # generate a key, being a combination of incrementing _IDENT_DATA and a random number
    _IDENT_DATA += 1
    if _IDENT_DATA > 9999:
        _IDENT_DATA = 1
    ident_data_key = str(_IDENT_DATA) + "X" + str(random.randrange(10000, 99999))

    # create value_list to store in redis, up to 20 string items
    value_list = ['']*20
    if 'starchart_ident' in set_values:
        value_list[0] = set_values['starchart_ident']
    if 'planning_date_ident' in set_values:                       # Date from which planning tables are created, 
        value_list[1] = set_values['planning_date_ident']         # often different from finder date, i.e. the evenning before the early hours
    if 'session_date_ident' in set_values:
        value_list[2] = set_values['session_date_ident']
    if 'target_name_ident' in set_values:
        value_list[3] = set_values['target_name_ident']
    if 'target_date_ident' in set_values:
        value_list[4] = set_values['target_date_ident']
    if 'target_time_ident' in set_values:
        value_list[5] = set_values['target_time_ident']
    if 'target_ra_ident' in set_values:
        value_list[6] = set_values['target_ra_ident']
    if 'target_dec_ident' in set_values:
        value_list[7] = set_values['target_dec_ident']
    if 'target_alt_ident' in set_values:
        value_list[8] = set_values['target_alt_ident']
    if 'target_az_ident' in set_values:
        value_list[9] = set_values['target_az_ident']
    if 'view_ident' in set_values:
        value_list[10] = set_values['view_ident']
    if 'back_ident' in set_values:
        value_list[11] = set_values['back_ident']
    if ('flip_ident' in set_values) and set_values['flip_ident']:
        value_list[12] = 'true'
    else:
        value_list[12] = ''
    if 'rot_ident' in set_values:
        value_list[13] = str(set_values['rot_ident'])
    else:
        value_list[13] = '0'

     
    # and store these values in redis, under the ident_data_key
    redis_ops.set_session_value(ident_data_key, value_list, skicall.proj_data.get("rconn_4"), skicall.proj_data.get("rconn"))
    return ident_data_key



def _check_cookies(received_cookies, proj_data):
    """If this function returns None, the call proceeds unhindered to the INDI subapplication.
       If it returns an ident tuple then the call is routed to that ident page instead."""

    global PROJECT

    # page to divert to, showing message session unavailable
    divert = 3

    if not received_cookies:
        # no received cookie, therefore cannot access indi client
        return divert

    cookie_name = PROJECT + '2'
    if cookie_name not in received_cookies:
        # no cookie received with the valid cookie name, so divert
        return divert

    cookie_string = received_cookies[cookie_name]
    # so a recognised cookie has arrived, check redis to see if the user has logged in
    user_id = redis_ops.logged_in(cookie_string, proj_data.get("rconn_1"), proj_data.get("rconn"))
    if not user_id:
        # cookie_string not saved in redis, unknown user, so divert
        return divert

    user = database_ops.get_user_from_id(user_id)
    # user is (username, role, email, member) on None on failure
    if not user:
        # user_id not recognised user on the database, perhaps been deleted
        # so divert
        return divert

    # only admin users have access to the indi client
    # is this user an admin user
    if user[1] != 'ADMIN':
        # not an admin user
        return divert

    # is the current slot live, and if so who owns it?
    slot_status = database_ops.get_slot_status(sun.Slot.now())

    if slot_status is None:
        # exception occurred when trying to get slot from database
        return divert

    # there is a current slot, which may or may not be booked
    status, booked_user_id = slot_status
    if status == 1:
        # slot is booked (0 is not booked, 2 is disabled)
        if user_id == booked_user_id:
            # this is the user who has booked the slot, proceed to indi
            return

        if booked_user_id:
            # someone else has booked the telescope
            return divert

    # if slot not booked, has the user enabled test mode

    test_mode_user_id = redis_ops.get_test_mode_user(proj_data.get("rconn_0"), proj_data.get("rconn"))
    if test_mode_user_id != user_id:
        # does not have test mode enabled
        return divert

    # This user has test mode, and is enabled, final check, is he authenticated?
    if redis_ops.is_authenticated(cookie_string, proj_data.get("rconn_2"), proj_data.get("rconn")):
        # yes, so he can connect to indi
        return
    
    # no - divert
    return divert



# create the wsgi application
application = WSGIApplication(project=PROJECT,
                              projectfiles=PROJECTFILES,
                              proj_data=make_proj_data(),
                              start_call=start_call,
                              submit_data=submit_data,
                              end_call=end_call,
                              url="/acremscope")

# add the skis library of javascript and css files
skis_application = skis.makeapp()
application.add_project(skis_application, url='/acremscope/lib')

# add the indiredis client
indi_application = indiredis.make_wsgi_app(REDISSERVER, blob_folder=cfg.get_servedfiles_directory())
application.add_project(indi_application, url='/acremscope/indi', check_cookies=_check_cookies)


if __name__ == "__main__":

    ###################### Remove for deployment ##################################
    #                                                                              #
    #set_debug(True)                                                               #
    #from skipole import skiadmin                                                  #
    #skiadmin_application = skiadmin.makeapp(editedprojname=PROJECT)               #
    #application.add_project(skiadmin_application, url='/acremscope/skiadmin')     #
    #                                                                              #
    ###############################################################################

    # Using the waitress server
    import waitress

    # serve the application
    waitress.serve(application, host="0.0.0.0", port=8000)



