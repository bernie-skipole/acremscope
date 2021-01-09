##################################
#
# These functions populate the public control pages
#
##################################


from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import sun, database_ops, redis_ops, send_mqtt


def create_index(skicall):
    "Fills in the tests index page"
    skicall.page_data['output01', 'para_text'] = "LED : " + redis_ops.get_led(skicall.proj_data.get("rconn_0"))

def refresh_led_status(skicall):
    "Display sensor values, initially just the led status"
    skicall.page_data['output01', 'para_text'] = "LED : " + redis_ops.get_led(skicall.proj_data.get("rconn_0"))


def led_on(skicall):
    "Send a request to light led - equivalent to open the door"
    # Send the message via mqtt
    send_mqtt.request_led_on()
    skicall.page_data['status', 'para_text'] = "LED ON request sent"
    skicall.page_data['status', 'hide'] = False


def led_off(skicall):
    "Send a request to turn off led - equivalent to close the door"
    # Send the message via mqtt
    send_mqtt.request_led_off()
    skicall.page_data['status', 'para_text'] = "LED OFF request sent"
    skicall.page_data['status', 'hide'] = False


