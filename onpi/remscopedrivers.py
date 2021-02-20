# sends indi data via mqtt


from indi_mr import driverstomqtt, mqtt_server

# define the host/port where the MQTT server is listenning, this function returns a named tuple.
mqtt_host = mqtt_server(host='localhost', port=1883)

# blocking call which runs the service, communicating between drivers and mqtt
driverstomqtt([ "/home/bernard/www/drivers/leddriver.py",
                "/home/bernard/www/drivers/networkmonitor.py",
                "/home/bernard/www/drivers/temperaturedriver.py",
                "/home/bernard/www/drivers/doordriver.py"], 'pi_01', mqtt_host)

