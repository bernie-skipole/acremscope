

import random

from datetime import datetime

from indi_mr import tools

try:
    import redis
except:
    _REDIS_AVAILABLE = False
else:
    _REDIS_AVAILABLE = True


from skipole import FailPage, GoTo, ValidateError, ServerError

from . import cfg


def open_redis(redis_db=0):
    "Returns a connection to the redis database"

    if not _REDIS_AVAILABLE:
        raise FailPage(message = "redis module not loaded")

    rconn = None

    # redis server settings from cfg.py
    redis_ip, redis_port, redis_auth = cfg.get_redis()

    if not redis_ip:
        raise FailPage("Redis service not available")

    # create a connection to the redis data logging server
    try:
        rconn = redis.StrictRedis(host=redis_ip, port=redis_port, db=redis_db, password=redis_auth, socket_timeout=5)
    except:
        raise FailPage("Redis service not available")

    if rconn is None:
        raise FailPage("Redis service not available")

    return rconn


def get_control_user(rconn=None):
    """Return user_id of the user who has current control of the telescope,
       or None if not found,
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return
    if rconn is None:
        return
    try:
        control_user_id = int(rconn.get('control_user_id').decode('utf-8'))
    except:
        return
    return control_user_id


def set_control_user(user_id, rconn=None):
    """Set the user who has current control of the telescope and resets chart parameters.
       Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if user_id is None:
        return False
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False
    if rconn is None:
        return False
    try:
        rconn.set('view', "100.0")
        rconn.set('flip', '')
        rconn.set('rot', "0.0")
        result = rconn.set('control_user_id', user_id)
    except:
        return False
    if result:
        return True
    return False


def test_mode(user_id, rconn=None):
    """Return True if this user has test mode, False otherwise,
       If given rconn should connect to redis_db 0"""
    if user_id is None:
        return False
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False
    if rconn is None:
        return False
    try:
        test_user_id = int(rconn.get('test_mode').decode('utf-8'))
    except:
        return False
    return bool(user_id == test_user_id)


def get_test_mode_user(rconn=None):
    """Return user_id of test mode, or None if not found,
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return
    if rconn is None:
        return
    try:
        test_user_id = int(rconn.get('test_mode').decode('utf-8'))
    except:
        return
    return test_user_id


def set_test_mode(user_id, rconn=None):
    """Set this user with test mode.
       Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if user_id is None:
        return False
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False
    if rconn is None:
        return False
    try:
        result = rconn.set('test_mode', user_id, ex=3600, nx=True)  # expires after one hour, can only be set if it does not exist
    except:
        return False
    if result:
        return True
    return False


def delete_test_mode(rconn=None):
    """Delete test mode.
       Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False
    if rconn is None:
        return False
    try:
        rconn.delete('test_mode')
    except:
        return False
    return True


def set_wanted_position(ra, dec, rconn=None):
    """Sets the  wanted Telescope RA, DEC  - given as two floats in degrees
       Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False

    if rconn is None:
        return False

    try:
        result_ra = rconn.set('wanted_ra', str(ra))
        result_dec = rconn.set('wanted_dec', str(dec))
    except Exception:
        return False
    if result_ra and result_dec:
        return True
    return False


def get_wanted_position(rconn=None):
    """Return wanted Telescope RA, DEC as two floats in degrees
       If given rconn should connect to redis_db 0
       On failure returns None"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return
    if rconn is None:
        return
    try:
        wanted_ra = float(rconn.get('wanted_ra').decode('utf-8'))
        wanted_dec = float(rconn.get('wanted_dec').decode('utf-8'))
    except:
        return
    return wanted_ra, wanted_dec


def set_target_name(target_name, rconn=None):
    """Sets the  wanted Telescope target_name
       Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False
    if rconn is None:
        return False
    try:
        result = rconn.set('target_name', target_name.lower())
    except Exception:
        return False
    if result:
        return True
    return False


def get_target_name(rconn=None):
    """Return wanted Telescope named target.
       If given rconn should connect to redis_db 0
       On failure, or no name returns empty string"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return ''
    if rconn is None:
        return ''
    try:
        target_name = rconn.get('target_name').decode('utf-8')
    except:
        return ''
    return target_name


def set_target_frame(target_frame, rconn=None):
    """Sets the target_frame of the item currently being tracked
       Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False
    if rconn is None:
        return False
    try:
        result = rconn.set('target_frame', target_frame.lower())
    except Exception:
        return False
    if result:
        return True
    return False


def get_target_frame(rconn=None):
    """Returns the target_frame of the item currently being tracked
       If given rconn should connect to redis_db 0
       On failure, or no name returns empty string"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return ''
    if rconn is None:
        return ''
    try:
        target_frame = rconn.get('target_frame').decode('utf-8')
    except:
        return ''
    return target_frame


def del_target_name(rconn=None):
    """Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False
    if rconn is None:
        return False
    try:
        rconn.delete('target_name')
    except:
        return False
    return True


def get_chart_parameters(rconn=None):
    """Return view, flip and rotate values of the control chart"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return (100.0, False, 0.0)
    if rconn is None:
        return (100.0, False, 0.0)
    try:
        view = rconn.get('view').decode('utf-8')
        flip = rconn.get('flip').decode('utf-8')
        rot = rconn.get('rot').decode('utf-8')
    except:
        return (100.0, False, 0.0)
    return float(view), bool(flip), float(rot)


def set_chart_parameters(view, flip, rot, rconn=None):
    """Set view, flip, rot
       Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False

    if rconn is None:
        return False

    try:
        result_view = rconn.set('view', str(view))
        if flip:
            result_flip = rconn.set('flip', 'true')
        else:
            result_flip = rconn.set('flip', '')
        result_rot = rconn.set('rot', str(rot))
    except Exception:
        return False
    if result_view and result_flip and result_rot:
        return True
    return False


def get_chart_actual(rconn=None):
    """Return True if the chart is showing actual view, False if target view"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False
    if rconn is None:
        return False
    try:
        actual = rconn.get('chart_actual').decode('utf-8')
    except:
        return False
    return bool(actual)


def set_chart_actual(actual, rconn=None):
    """Set actual value
       Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 0"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return False

    if rconn is None:
        return False

    try:
        if actual:
            result_actual = rconn.set('chart_actual', 'true')
        else:
            result_actual = rconn.set('chart_actual', '')
    except Exception:
        return False
    if result_actual:
        return True
    return False


def get_led(rconn, redisserver):
    """Return led status string. If given rconn should connect to redis_db 0"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return 'UNKNOWN'
    if rconn is None:
        return 'UNKNOWN'
    try:
        #led_status = rconn.get('led').decode('utf-8')
        led = tools.elements_dict(rconn, redisserver, "LED ON", "LED", "Rempi01 LED")
        # led should be a dictionary, key 'value' should be On or Off
        if not led:
            return "UNKNOWN"
        led_status = led.get("value", "UNKNOWN")
    except:
        return 'UNKNOWN'
    return led_status



def get_door(rconn, redisserver):
    """Return door status string. If given rconn should connect to redis_db 0"""
    # returns one of UNKNOWN, OPEN, CLOSED, OPENING, CLOSING
    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return 'UNKNOWN'
    if rconn is None:
        return 'UNKNOWN'
    door_name = cfg.door()
    try:
        door_status = tools.elements_dict(rconn, redisserver, "CLOSED", "DOOR_STATE", door_name)
        if door_status['value'] == "Ok":
            return "CLOSED"
        door_status = tools.elements_dict(rconn, redisserver, "OPEN", "DOOR_STATE", door_name)
        if door_status['value'] == "Ok":
            return "OPEN"
        door_status = tools.elements_dict(rconn, redisserver, "OPENING", "DOOR_STATE", door_name)
        if door_status['value'] == "Ok":
            return "OPENING"
        door_status = tools.elements_dict(rconn, redisserver, "CLOSING", "DOOR_STATE", door_name)
        if door_status['value'] == "Ok":
            return "CLOSING"
    except:
        return 'UNKNOWN'
    return 'UNKNOWN'


def get_temperatures(rconn, redisserver):
    """Return temperature log. If given rconn should connect to redis_db 0"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            raise FailPage("Unable to access redis temperature variable")
    if rconn is None:
        raise FailPage("Unable to access redis temperature variable")
    # get data from redis
    try:
        elementlogs = tools.logs(rconn, redisserver, 48, 'elementattributes', "TEMPERATURE", "ATMOSPHERE", "Rempi01 Temperature")
        if not elementlogs:
            return []
        dataset = [] # needs to be a list of lists of [day, time, temperature]
        for t,data in elementlogs:
            if ("formatted_number" not in data) or ("timestamp" not in data):
                continue
            number = float(data["formatted_number"]) - 273.15
            numberstring = "%.2f" % number
            daytime = data["timestamp"].split("T")
            dataset.append([daytime[0], daytime[1], numberstring])
    except:
        raise FailPage("Unable to access redis temperature variable")
    return dataset


def last_temperature(rconn, redisserver):
    """Return last date and temperature. If given rconn should connect to redis_db 0

       String returned is of the form %Y-%m-%d %H:%M temperature, if unable to get
       the temperature, an empty string is returned"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return ''
    if rconn is None:
        return ''
    # get data from redis
    try:
        element_att = tools.elements_dict(rconn, redisserver, "TEMPERATURE", "ATMOSPHERE", "Rempi01 Temperature")
        # element_att should be a dictionary
        if not element_att:
            return ''
        temperature_value = element_att.get("formatted_number")
        if temperature_value is None:
            return ''
        # Convert from Kelvin to Centigrade
        temperature = float(temperature_value) - 273.15
        temperature_string = "%.2f" % temperature
        timestamp_value = element_att.get("timestamp")
        if timestamp_value is None:
            return ''
        temperature_date, temperature_time =  timestamp_value.split("T")
    except:
        return ''
    return f"{temperature_date} {temperature_time} {temperature_string}"


############################################################
#
# The following deals with cookies and user logged in status
#
############################################################


def logged_in(cookie_string, rconn=None):
    """Check for a valid cookie, if logged in, return user_id
       If not, return None. If rconn is None, a new connection will be created.
       If given rconn should connect to redis_db 1"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=1)
        except:
            return

    if rconn is None:
        return

    if (not cookie_string) or (cookie_string == "noaccess"):
        return
    try:
        if not rconn.exists(cookie_string):
            return
        user_info = rconn.lrange(cookie_string, 0, -1)
        # user_info is a list of binary values
        # user_info[0] is user id
        # user_info[1] is a random number, added to input pin form and checked on submission
        # user_info[2] is a random number between 1 and 6, sets which pair of PIN numbers to request
        user_id = int(user_info[0].decode('utf-8'))
        # and update expire after two hours
        rconn.expire(cookie_string, 7200)
    except:
        return
    return user_id


def set_cookie(cookie_string, user_id, rconn=None):
    """Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 1"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=1)
        except:
            return False

    if rconn is None:
        return False

    if (not  user_id) or (not cookie_string):
        return False

    # with cookie string as key, set value as a list of [user_id, random_number]
    try:
        if rconn.exists(cookie_string):
            # cookie already delete it
            rconn.delete(cookie_string)
            # and return False, as this should not happen
            return False
        # set the cookie into the database
        rconn.rpush(cookie_string, str(user_id), str(random.randint(10000000, 99999999)), str(random.randint(1,6)))
        rconn.expire(cookie_string, 7200)
    except:
        return False
    return True



def del_cookie(cookie_string, rconn=None):
    """Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 1"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=1)
        except:
            return False

    if rconn is None:
        return False

    if not cookie_string:
        return False
    try:
        rconn.delete(cookie_string)
    except:
        return False
    return True


def set_rnd(cookie_string, rconn=None):
    """Sets a random number against the cookie, return the random number on success,
       None on failure,
       if rconn is None, it is created.
       If given rconn should connect to redis_db 1"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=1)
        except:
            return

    if rconn is None:
        return

    if not cookie_string:
        return

    rnd = random.randint(10000000, 99999999)

    # with cookie string as key, set a random_number
    try:
        if not rconn.exists(cookie_string):
            return
        # set the random number into the database
        rconn.lset(cookie_string, 1, str(rnd))
    except:
        return
    return rnd


def get_rnd(cookie_string, rconn=None):
    """Gets the saved random number from the cookie, return the random number on success,
       None on failure.
       Once called, it creates a new random number to store in the database,
       so the number returned is then lost from the database.
       If rconn is None, it is created.
       If given rconn should connect to redis_db 1"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=1)
        except:
            return

    if rconn is None:
        return

    if not cookie_string:
        return

    # with cookie string as key, get and set a random_number
    try:
        if not rconn.exists(cookie_string):
            return
        user_info = rconn.lrange(cookie_string, 0, -1)
        # user_info is a list of binary values
        # user_info[0] is user id
        # user_info[1] is a random number
        # user_info[2] is a random number between 1 and 6, sets which pair of PIN numbers to request
        rnd = int(user_info[1].decode('utf-8'))
        # after obtaining rnd, insert a new one
        newrnd = random.randint(10000000, 99999999)
        rconn.lset(cookie_string, 1, str(newrnd))
    except:
        return
    return rnd


def get_pair(cookie_string, rconn=None):
    """Gets the saved pair random number from the cookie, return it on success,
       None on failure.
       If rconn is None, it is created.
       If given rconn should connect to redis_db 1"""
    if rconn is None:
        try:
            rconn = open_redis(redis_db=1)
        except:
            return

    if rconn is None:
        return

    if not cookie_string:
        return

    # with cookie string as key, get the pair number
    try:
        if not rconn.exists(cookie_string):
            return
        user_info = rconn.lrange(cookie_string, 0, -1)
        # user_info is a list of binary values
        # user_info[0] is user id
        # user_info[1] is a random number
        # user_info[2] is a random number between 1 and 6, sets which pair of PIN numbers to request
        pair = int(user_info[2].decode('utf-8'))
    except:
        return
    return pair


def is_authenticated(cookie_string, rconn=None):
    """Check for a valid cookie, if logged in, return True
       If not, return False. If rconn is None, a new connection will be created.
       If given rconn should connect to redis_db 2"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=2)
        except:
            return False

    if rconn is None:
        return False

    if (not cookie_string) or (cookie_string == "noaccess"):
        return False
    try:
        if rconn.exists(cookie_string):
            # key exists, and update expire after ten minutes
            rconn.expire(cookie_string, 600)
        else:
            return False
    except:
        return False
    return True


def set_authenticated(cookie_string, user_id, rconn=None):
    """Sets cookie into redis db2 as key, with [user_id,...] as value
       If successfull return True, if not return False.
       If rconn is None, a new connection will be created.
       If given rconn should connect to redis_db 2"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=2)
        except:
            return False

    if rconn is None:
        return False

    if (not  user_id) or (not cookie_string):
        return False
    try:
        if rconn.exists(cookie_string):
            # already authenticated, delete it
            rconn.delete(cookie_string)
            # and return False, as this should not happen
            return False
        # set the cookie into the database
        rconn.rpush(cookie_string, str(user_id))
        rconn.expire(cookie_string, 600)
    except:
        return False
    return True


##################################################
#
# count of pin failures for a user, stored in db 3
#
##################################################



def increment_try(user_id, rconn=None):
    """creates an incrementing count against the user_id
       which expires after one hour
       If rconn is None, a new connection will be created.
       If given rconn should connect to redis_db 3"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=3)
        except:
            return

    if rconn is None:
        return

    str_user_id = str(user_id)

    # increment and reset expire
    tries = rconn.incr(str_user_id)
    rconn.expire(str_user_id, 3600)
    return int(tries)


def get_tries(user_id, rconn=None):
    """Gets the count against the user_id
       If rconn is None, a new connection will be created.
       If given rconn should connect to redis_db 3"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=3)
        except:
            return

    if rconn is None:
        return

    str_user_id = str(user_id)

    if not rconn.exists(str_user_id):
        # No count, equivalent to 0
        return 0

    tries = rconn.get(str_user_id)
    return int(tries)


def clear_tries(user_id, rconn=None):
    """Clears the count to zero against the user_id
       If rconn is None, a new connection will be created.
       If given rconn should connect to redis_db 3"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=3)
        except:
            return

    if rconn is None:
        return

    str_user_id = str(user_id)

    rconn.set(str_user_id, 0)
    return



################################################
#
# Two timed random numbers, stored in db 0
#
################################################

def two_min_numbers(rndset, rconn=None):
    """returns two random numbers
       one valid for the current two minute time slot, one valid for the previous
       two minute time slot.  Four sets of such random numbers are available
       specified by argument rndset which should be 0 to 3
       If given rconn should connect to redis_db 0"""

    # limit rndset to 0 to 3
    if rndset not in (0,1,2,3):
        return None, None

    # call timed_random_numbers with timeslot of two minutes in seconds
    return timed_random_numbers(rndset, 120, rconn)



def timed_random_numbers(rndset, timeslot, rconn=None):
    """returns two random numbers
       one valid for the current time slot, one valid for the previous
       time slot.  Multiple sets of such random numbers are available
       specified by argument rndset which should be an integer.
       If given rconn should connect to redis_db 0"""

    if rconn is None:
        try:
            rconn = open_redis(redis_db=0)
        except:
            return None, None

    if rconn is None:
        return None, None

    key = "rndset_" + str(rndset)
    now = rconn.time()[0]     # time in seconds

    try:

        if not rconn.exists(key):
            rnd1 = random.randint(10000000, 99999999)
            rnd2 = random.randint(10000000, 99999999)
            rconn.rpush(key, str(now), str(rnd1), str(rnd2))
            return rnd1, rnd2

        start, rnd1, rnd2 = rconn.lrange(key, 0, -1)
        start = int(start.decode('utf-8'))
        rnd1 = int(rnd1.decode('utf-8'))
        rnd2 = int(rnd2.decode('utf-8'))

        if now < start + timeslot:
            # now is within timeslot of start time, so current random numbers are valid
            return rnd1, rnd2

        elif now < start + timeslot + timeslot:
            # now is within twice the timeslot of start time, so rnd1 has expired. but rnd2 is valid
            # set rnd2 equal to rnd1 and create new rnd1
            rnd2 = rnd1
            rnd1 = random.randint(10000000, 99999999)
            rconn.delete(key)
            rconn.rpush(key, str(now), str(rnd1), str(rnd2))
            return rnd1, rnd2

        else:
            # now is greater than twice timeslot after start time, ro rnd1 and rnd2 are invalid, create new ones
            rnd1 = random.randint(10000000, 99999999)
            rnd2 = random.randint(10000000, 99999999)
            rconn.delete(key)
            rconn.rpush(key, str(now), str(rnd1), str(rnd2))
            return rnd1, rnd2
    except:
        pass

    return None, None


######################################################################
#
# dbase 4 for temporary session values, lifetime 7200 (two hours)
#
# each key contains a list of strings, note the string '_'
# should not be used as it has a special meaning
#
######################################################################



def set_session_value(key_string, value_list, rconn=None):
    """Return True on success, False on failure, if rconn is None, it is created.
       If given rconn should connect to redis_db 4

       Given a key_string, saves a value_list
       with an expirey time of 7200 seconds (2 hours)
       The items are saved as strings.
       empty values are stored as '_'"""

    if not key_string:
        return False
    if not value_list:
        return False

    if rconn is None:
        try:
            rconn = open_redis(redis_db=4)
        except:
            return False

    if rconn is None:
        return False

    # dbsize() returns the number of keys in the database
    numberofkeys = rconn.dbsize()
    # If the database is getting bigger, reduce the expire time of keys to reduce it
    if numberofkeys > 2000:
        return False
    elif numberofkeys > 1500:
        exptime = 900  # 15 minutes
    elif numberofkeys > 1000:
        exptime = 1800  # 30 minutes
    elif numberofkeys > 500:
        exptime = 3600  # one hour
    else:
        exptime = 7200  # two hours

    # Create a 'values' list, with '' replaced by '_'
    values = []
    for val in value_list:
        str_val = str(val)
        if not str_val:
            str_val = '_'
        values.append(str_val)

    try:
        if rconn.exists(key_string):
            # key_string already exists, delete it
            rconn.delete(key_string)
        # set the key and list of values into the database
        rconn.rpush(key_string, *values)
        rconn.expire(key_string, exptime)
    except:
        return False
    return True



def get_session_value(key_string, rconn=None):
    """If rconn is None, a new connection will be created.
       If given rconn should connect to redis_db 4
       If key_string is not found, return None"""

    if not key_string:
        return

    if rconn is None:
        try:
            rconn = open_redis(redis_db=4)
        except:
            return

    if rconn is None:
        return

    if not rconn.exists(key_string):
        # no value exists
        return

    binvalues = rconn.lrange(key_string, 0, -1)
    # binvalues is a list of binary values
    values = []
    for bval in binvalues:
        val = bval.decode('utf-8')
        if val == '_':
            str_val = ''
        else:
            str_val = val
        values.append(str_val)

    return values


######################### log information to redis,

def log_info(rconn, messagetime=None, topic = '', message=''):
    """Log the given message to the redis connection rconn, return True on success, False on failure.
       messagetime is a datetime object or not given, if not given a current timestamp will be created
       topic is optional, if given the resultant log will be topic : message"""
    if not message:
        return False
    if rconn is None:
        return False
    if messagetime is None:
        messagetime = datetime.utcnow()
    if topic:
        topicmessage = " " + topic + " : " + message
    else:
        topicmessage = " " + message
    try:
        # create a log entry to set in the redis server
        fullmessage = messagetime.strftime("%Y-%m-%d %H:%M:%S") + topicmessage
        rconn.rpush("log_info", fullmessage)
        # and limit number of messages to 50
        rconn.ltrim("log_info", -50, -1)
    except:
        return False
    return True


def get_log_info(rconn):
    """Return info log as a list of log strings, newest first. rconn should connect to redis_db 0. On failure, returns empty list"""
    if rconn is None:
        return []
    # get data from redis
    try:
        logset = rconn.lrange("log_info", 0, -1)
    except:
        return []
    if logset:
        loglines = [ item.decode('utf-8') for item in logset ]
    else:
        return []
    loglines.reverse()
    return loglines







