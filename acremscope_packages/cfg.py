# Sets config items

# Edit this dictionary to store service parameters

# astronomy centre is 53:42:40N 2:09:16W

import csv, os

_CONFIG = { 
            'latitude' : 53.7111,
            'longitude' : -2.1544,
            'elevation' : 316,
            'mqtt_ip' : '10.105.192.1',
            #'mqtt_ip' : 'localhost',
            'mqtt_port' : 1883,
            'mqtt_username' : '',
            'mqtt_password' : '',
            'redis_ip' : 'localhost',
            'redis_port' : 6379,
            'redis_auth' : '',
            #'postgresql_ip' : '10.105.192.252',
            'postgresql_ip' : 'localhost',
            'postgresql_dbname' : 'astrodb',
            'postgresql_username' : 'astro',
            'postgresql_password' : 'xxSgham',
          }


_PLANETS = {"mercury":  0.23,
            "venus":   -4.14,
            "mars":     0.71,
            "jupiter": -2.20,
            "saturn":   0.46,
            "uranus":   5.68,
            "neptune":  7.78,
            "pluto":   14.00}

def set_projectfiles(projectfiles):
    global _CONFIG
    _CONFIG['astrodata_directory'] = os.path.join(projectfiles, 'astrodata')
    _CONFIG['servedfiles_directory'] = os.path.join(projectfiles, 'astrodata', 'served')
    _CONFIG['planetdb'] = os.path.join(projectfiles, 'astrodata', 'planet.db')
    _CONFIG['constellation_lines'] = os.path.join(projectfiles, 'astrodata', 'lines.csv')
    _CONFIG['star_catalogs'] = os.path.join(projectfiles, 'astrodata', 'gsc1.2')
    

def planetmags():
    "Returns dictionary of planet magnitudes"
    return _PLANETS


_CONSTELLATION_LINES = []

def _read_constellation_lines():
    "Reads the constellation lines and places them into _CONSTELLATION_LINES"
    global _CONSTELLATION_LINES
    with open(_CONFIG['constellation_lines'], newline='') as f:
        reader = csv.reader(f)
        _CONSTELLATION_LINES = list(reader)

def get_constellation_lines():
    "Returns a list of constellation lines"
    if not _CONSTELLATION_LINES:
        _read_constellation_lines()
    return _CONSTELLATION_LINES


def get_mqtt():
    "Returns tuple of mqtt server ip, port, username, password"
    return (_CONFIG['mqtt_ip'], _CONFIG['mqtt_port'], _CONFIG['mqtt_username'], _CONFIG['mqtt_password'])

def get_postgresql():
    "Returns tuple of postgresql ip, dbname, username, password"
    return (_CONFIG['postgresql_ip'], _CONFIG['postgresql_dbname'], _CONFIG['postgresql_username'], _CONFIG['postgresql_password'])

def get_redis():
    "Returns tuple of redis ip, port, auth"
    return (_CONFIG['redis_ip'], _CONFIG['redis_port'], _CONFIG['redis_auth'])

def get_astrodata_directory():
    "Returns the directory of support files"
    return _CONFIG['astrodata_directory']

def get_star_catalogs_directory():
    "Returns the directory of support files"
    return _CONFIG['star_catalogs']

def get_servedfiles_directory():
    "Returns the directory where served files are kept"
    return _CONFIG['servedfiles_directory']

def get_planetdb():
    "Returns the path to the database file which stores planet positions"
    return _CONFIG['planetdb']


def observatory():
    "Returns the observatory longitude, latitude, elevation"
    return _CONFIG['longitude'], _CONFIG['latitude'], _CONFIG['elevation']



