# sends indi data via mqtt


from indi_mr import driverstomqtt, mqtt_server

# define the host/port where the MQTT server is listenning, this function returns a named tuple.
mqtt_host = mqtt_server(host='10.105.192.1', port=1883)

# blocking call which runs the service, communicating between drivers and mqtt
driverstomqtt([ # "/home/bernard/www/drivers/leddriver.py",
               #"/home/bernard/www/drivers/networkmonitor.py",
               "/home/bernard/www/drivers/temperaturedriver.py",
               "/home/bernard/www/drivers/doordriver.py",
               "indi_simulator_telescope",
               "indi_simulator_ccd"], 'indi_drivers01', mqtt_host)

