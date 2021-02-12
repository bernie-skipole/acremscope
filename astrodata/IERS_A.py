
import sys

from datetime import datetime

import redis

from astroplan import download_IERS_A

try:
    download_IERS_A()
except:
    message = "download_IERS_A() has failed"
else:
    message = "IERS Bulletin A has been downloaded"


try:
    rconn = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=5)
except Exception:
    print("Warning:redis connection failed")
else:
    try:
        # create a log entry to set in the redis server
        fullmessage = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") + " " + message
        rconn.rpush("remscope_various_log_info", fullmessage)
        # and limit number of messages to 50
        rconn.ltrim("remscope_various_log_info", -50, -1)
    except Exception:
        print("Saving log to redis has failed")

sys.exit(0)

