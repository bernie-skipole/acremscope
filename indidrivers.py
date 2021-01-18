# Runs indi drivers, storing data to redis

from indi_mr import driverstoredis, redis_server

redis_host = redis_server(host='localhost', port=6379)

# blocking call which runs the service, communicating between the drivers and redis

driverstoredis(["indi_simulator_telescope", "indi_simulator_ccd"], redis_host, blob_folder='/home/bernard/www/astrodata/served')


