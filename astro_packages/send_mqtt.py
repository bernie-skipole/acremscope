
####################################################
#
# Consists of the sendmqtt function which allows the server to send
# an mqtt message
#
####################################################


from datetime import datetime, timedelta


_mqtt_mod = True
try:
    import paho.mqtt.publish as publish
except:
    _mqtt_mod = False


from . import cfg


def sendmqtt(payload, subtopic=None):
    "Sends a payload, return True on success, False failure"

    if not _mqtt_mod:
        return False

    # send message via mqtt
    mqtt_ip, mqtt_port, mqtt_username, mqtt_password = cfg.get_mqtt()
    if not mqtt_ip:
        return False
    # If a username/password is set on the mqtt server
    if mqtt_username:
        if mqtt_password:
            auth = {'username':mqtt_username, 'password':mqtt_password}
        else:
            auth = {'username':mqtt_username}
    else:
        auth = None

    if subtopic:
        topic = "From_WebServer/" + subtopic
    else:
        topic = "From_WebServer"

    try:
        publish.single(topic = topic, payload = payload, hostname = mqtt_ip, port = mqtt_port, auth=auth)
    except:
        return False
    return True


def goto(packedstring):
    """Sends packedstring as a telescope goto command

       where packed string is created in module members.control"""
    sendmqtt(payload = packedstring, subtopic="Telescope/goto")


def altazgoto(packedstring):
    """Sends packedstring as a telescope goto command

       where packed string is created in module members.control"""
    sendmqtt(payload = packedstring, subtopic="Telescope/altaz")


def request_door_close():
    "Request door close"
    sendmqtt(payload = "CLOSE", subtopic="Outputs/door")

def request_door_halt():
    "Request door halt"
    sendmqtt(payload = "HALT", subtopic="Outputs/door")

def request_door_open():
    "Request door open"
    sendmqtt(payload = "OPEN", subtopic="Outputs/door")

def request_led_off():
    "Request led off"
    sendmqtt(payload = "OFF", subtopic="Outputs/led")

def request_led_on():
    "Request led on"
    sendmqtt(payload = "ON", subtopic="Outputs/led")



