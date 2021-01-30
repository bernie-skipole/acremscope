##################################
#
# These functions populate the logged in control pages
#
##################################

from datetime import datetime, timedelta

from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import sun, database_ops, redis_ops, send_mqtt

from indi_mr import tools

from .sessions import doorsession


def create_index(skicall):
    "Fills in the remscope index page, also used to refresh the page by JSON"

    # door is one of UNKNOWN, OPEN, CLOSED, OPENING, CLOSING
    door = redis_ops.get_door(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"))
    skicall.page_data['door_status', 'para_text'] = "Door : " + door
    if (door == 'UNKNOWN') or (door == 'CLOSED') or (door == "OPENING"):
        skicall.page_data['door', 'button_text'] = 'Open Door'
        skicall.page_data['door', 'action'] = 'open'
    else:
        skicall.page_data['door', 'button_text'] = 'Close Door'
        skicall.page_data['door', 'action'] = 'close'

    skicall.page_data['utc', 'para_text'] = datetime.utcnow().strftime("UTC Time : %H:%M")

    user_id = skicall.call_data['user_id']

    booked = database_ops.get_users_next_session(datetime.utcnow(), user_id)

    # does this user own the current session
    if user_id == skicall.call_data["booked_user_id"]:
        # the current slot has been booked by the current logged in user,
        skicall.page_data['booked', 'para_text'] = "Your session is live. You now have control."
    elif booked:
        skicall.page_data['booked', 'para_text'] = "Your next booked session starts at UTC : " + booked.strftime("%Y-%m-%d %H:%M")
    else:
        skicall.page_data['booked', 'para_text'] = "You do not have any sessions booked."


    if skicall.call_data["test_mode"]:
        skicall.page_data['test_warning', 'para_text'] = """WARNING: You are operating in Test Mode - Telescope commands will be sent regardless of the door status, or daylight situation. This could be damaging, please ensure you are in control of the test environment.
Note: A time slot booked by a user will override Test Mode, to avoid this you should operate within time slots which you have previously disabled."""
    elif skicall.call_data["role"] == 'ADMIN':
        skicall.page_data['test_warning', 'para_text'] = """The robotic telescope can be controlled by members during their valid booked session, or by Administrators who have enabled 'Test' mode.
Test Mode can be set by following the 'Admin' link on the left navigation panel.
Only one Admin user can enable Test Mode at a time.
Note: A time slot booked by a user will override Test Mode, to avoid this you should operate within time slots which you have previously disabled."""
    else:
        skicall.page_data['test_warning', 'para_text'] = ""


@doorsession
def door_control(skicall):
    "A door control is requested, sends command and fills in the template page"

    call_data = skicall.call_data
    page_data = skicall.page_data

    if ('door', 'action') not in call_data:
        return

    if call_data['door', 'action'] == 'open':
        tools.newswitchvector(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"),
                          "DOME_SHUTTER", "Roll off door", {"SHUTTER_OPEN":"On", "SHUTTER_CLOSE":"Off"})
        page_data['door_status', 'para_text'] = "An Open door command has been sent."
    else:
        tools.newswitchvector(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"),
                          "DOME_SHUTTER", "Roll off door", {"SHUTTER_OPEN":"Off", "SHUTTER_CLOSE":"On"})
        page_data['door_status', 'para_text'] = "A Close door command has been sent."

    page_data['door', 'button_text'] = 'Waiting'
    skicall.page_data['door', 'action'] = 'noaction'

    if skicall.call_data["test_mode"]:
        skicall.page_data['test_warning', 'para_text'] = """WARNING: You are operating in Test Mode - Telescope commands will be sent regardless of the door status, or daylight situation. This could be damaging, please ensure you are in control of the test environment.
Note: A time slot booked by a user will override Test Mode, to avoid this you should operate within time slots which you have previously disabled."""
    else:
        skicall.page_data['test_warning', 'para_text'] = ""





