
###############################################
#
# This script is used to to send INDI client
# requests to send a getProperties command and
# to close the dome door at 10:45 each morning.
# This is to supplement automatic daylight closing
# of the door.  Note: it should also park the
# telescope in future
#
################################################



import sys, time

from datetime import datetime


from indi_mr import redis_server, tools



def get_door(rconn, redisserver):
    """Return door status string."""
    # returns one of UNKNOWN, OPEN, CLOSED, OPENING, CLOSING
    try:
        door_status = tools.elements_dict(rconn, redisserver, "CLOSED", "DOOR_STATE", "Roll off door")
        if door_status['value'] == "Ok":
            return "CLOSED"
        door_status = tools.elements_dict(rconn, redisserver, "OPEN", "DOOR_STATE", "Roll off door")
        if door_status['value'] == "Ok":
            return "OPEN"
        door_status = tools.elements_dict(rconn, redisserver, "OPENING", "DOOR_STATE", "Roll off door")
        if door_status['value'] == "Ok":
            return "OPENING"
        door_status = tools.elements_dict(rconn, redisserver, "CLOSING", "DOOR_STATE", "Roll off door")
        if door_status['value'] == "Ok":
            return "CLOSING"
    except:
        return 'UNKNOWN'
    return 'UNKNOWN'


if __name__  == "__main__":

    redisserver = redis_server(host='localhost', port=6379)

    try:
        rconn = tools.open_redis(redisserver)
        result = tools.getProperties(rconn, redisserver)
        if result is None:
            message = "Failed to send getProperties command"
        else:
            # give getProperties time to respond
            time.sleep(10)
            # send door close command
            result = tools.newswitchvector(rconn, redisserver,
                                  "DOME_SHUTTER", "Roll off door", {"SHUTTER_OPEN":"Off", "SHUTTER_CLOSE":"On"})
            if result is None:
                message = "Failed to send close door command"
            else:
                time.sleep(60)
                # wait a minute, then check door is closed
                # future possibility - send alert emails if it has not
                door_status = get_door(rconn, redisserver)
                message = f"Auto request to close door sent. Door status: {door_status}"

    except Exception:
        print("Warning:clientrequests.py failed")
    else:
        try:
            # create a log entry to set in the redis server
            fullmessage = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") + " " + message
            rconn.rpush("log_info", fullmessage)
            # and limit number of messages to 50
            rconn.ltrim("log_info", -50, -1)
        except Exception:
            print("Saving log to redis has failed")

    sys.exit(0)

