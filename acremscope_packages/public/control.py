##################################
#
# These functions populate the public control pages
#
##################################


from skipole import FailPage, GoTo, ValidateError, ServerError

from indi_mr import tools

from .. import sun, database_ops, redis_ops


def create_index(skicall):
    "Fills in the tests index page"
    skicall.page_data['output01', 'para_text'] = "LED : " + redis_ops.get_led(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"))

def refresh_led_status(skicall):
    "Display sensor values, initially just the led status"
    skicall.page_data['output01', 'para_text'] = "LED : " + redis_ops.get_led(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"))


# tools.newswitchvector(rconn, redisserver, name, device, values, timestamp=None):
# Sends a newSwitchVector request, returns the xml string sent, or None on failure.
# Values should be a dictionary of element name:state where state is On or Off.


def led_on(skicall):
    "Send a request to light led"
    tools.newswitchvector(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"),
                          "LED", "Rempi01 LED", {"LED ON":"On", "LED OFF":"Off"})
    skicall.page_data['status', 'para_text'] = "LED ON request sent"
    skicall.page_data['status', 'hide'] = False


def led_off(skicall):
    "Send a request to turn off led"
    tools.newswitchvector(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("redisserver"),
                          "LED", "Rempi01 LED", {"LED ON":"Off", "LED OFF":"On"})
    skicall.page_data['status', 'para_text'] = "LED OFF request sent"
    skicall.page_data['status', 'hide'] = False


