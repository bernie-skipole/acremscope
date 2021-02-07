# stores indi data to redis


from indi_mr import redis_server, driverstoredis

# define the hosts/ports where servers are listenning, these functions return named tuples.

redis_host = redis_server(host='localhost', port=6379)

# blocking call which runs the service, communicating between the drivers and redis
driverstoredis(["indi_simulator_telescope", "/home/bernard/git/acremscope/drivers/doordriver.py"], redis_host, blob_folder='/home/bernard/indiblobs')


