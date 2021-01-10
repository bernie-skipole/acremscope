

###############################################
#
# This script is used to create an sqlite database
# and calculate planet positions
#
################################################



import os, sys, sqlite3, datetime, math


try:
    import astropy.units as u
    from astropy.coordinates import SkyCoord, EarthLocation, AltAz, name_resolve, solar_system_ephemeris, get_body, Angle
    from astropy.time import Time
except:
    sys.exit(1)

solar_system_ephemeris.set('jpl')

THIS_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

# The path to the file of the database to be created
PLANETDB = os.path.join(THIS_DIRECTORY, "planet.db")

LONGITUDE = -2.1544
LATITUDE = 53.7111
ELEVATION = 316



def create_database():
    "Create planet.db"
    # connect to database
    try:
        con = sqlite3.connect(PLANETDB, detect_types=sqlite3.PARSE_DECLTYPES)
        con.execute("PRAGMA foreign_keys = 1")
    except:
        return 1, "Unable to open new database file %s. Please check permissions." % (PLANETDB,)

    try:
        # make table of planet positions, with datetime, planet name as primary key
        con.execute("""CREATE TABLE POSITIONS(DATEANDTIME timestamp,
                                              NAME TEXT NOT NULL,
                                              RA REAL,
                                              DEC REAL,
                                              ALT REAL,
                                              AZ REAL,
                                              PRIMARY KEY(DATEANDTIME,NAME))""")
        con.commit()
    except:
        return 2, "Unable to create table in the new database file %s." % (PLANETDB,)

    finally:
        con.close()

    return 0, "database created"


def delete_old():
    "Delete old entries"
    # connect to database
    try:
        con = sqlite3.connect(PLANETDB, detect_types=sqlite3.PARSE_DECLTYPES)
        con.execute("PRAGMA foreign_keys = 1")
        c = con.cursor()
    except:
        return 5

    # delete planets older than two hours ago
    twohoursago = datetime.datetime.utcnow() - datetime.timedelta(hours=2)
    try:
        c.execute('DELETE FROM POSITIONS WHERE DATEANDTIME<?', (twohoursago,))
        con.commit()
        print("Rows deleted: %s" % (con.total_changes,))
    except:
        return 6

    finally:
        con.close()

    return 0



def make_ten_days(astro_centre):
    "For each planet, create the positions over ten days"

    # connect to database
    try:
        con = sqlite3.connect(PLANETDB, detect_types=sqlite3.PARSE_DECLTYPES)
        con.execute("PRAGMA foreign_keys = 1")
    except:
        return 3

    planets = ("mercury", "venus", "moon", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto")

    todaydate = datetime.datetime.utcnow().date()
    # set an initial time at 0 am today
    dt = datetime.datetime(todaydate.year, todaydate.month, todaydate.day, hour=0)
    oneday = datetime.timedelta(days=1)

    try:
        for day in range(10):
            for planet in planets:
                status = make_day(astro_centre, dt, planet, con)
                if status:
                    return status
            dt += oneday
        con.commit()
        print("Rows added: %s" % (con.total_changes,))
    except:
        return 4

    finally:
        con.close()

    return 0


def make_day(astro_centre, dt, planet, con):
    "For the given planet, create the position at hourly intervals over the day"
    c = con.cursor()

    for hr in range(24):
        ptime = dt + datetime.timedelta(hours=hr, minutes=30)
        # so ptime is the position time, check if it exists in the database

        item = (ptime, planet)

        c.execute('SELECT * FROM POSITIONS WHERE DATEANDTIME=? AND NAME=?', item)
        result=c.fetchone()
        if result is not None:
            # This position is already created, so skip making it again
            continue
        # so for the given ptime, and planet, create a position
        make_position(astro_centre, ptime, planet, con)
        

def make_position(astro_centre, ptime, planet, con):
    "Use astropy to get the position, and then insert the data"
    
    time = Time(ptime, format='datetime', scale='utc')
    target = get_body(planet, time, astro_centre)
    # altitude and azimuth
    target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
    # insert these into the database
    c = con.cursor()
    c.execute("INSERT INTO POSITIONS VALUES (?, ?, ?, ?, ?, ?)", (ptime,
                                                                  planet,
                                                                  target.ra.degree,
                                                                  target.dec.degree,
                                                                  target_altaz.alt.degree,
                                                                  target_altaz.az.degree))





def _ra_dec_conversion(ra, dec):
    """Given ra and dec in degrees, convert to (rahr, ramin, rasec, decsign, decdeg, decmin, decsec)
       where decsign is a string, either '+' or '-'"""
    # get ra, dec in hms, dms
    rahr = math.floor(ra / 15.0)
    if not rahr:
        ra_remainder = ra
    else:
        ra_remainder = math.fmod(ra, rahr*15.0)
    if not ra_remainder:
        ramin = 0
        rasec = 0.0
    else:
        ramin = math.floor(ra_remainder * 4)
        ra_remainder = math.fmod(ra_remainder, 1.0/4.0)
        if not ra_remainder:
            rasec = 0.0
        else:
            rasec = ra_remainder * 240

    if "{:2.1f}".format(rasec) == "60.0":
        rasec = 0
        ramin += 1
    if ramin == 60:
        ramin = 0
        rahr += 1
    if rahr == 24:
        rahr = 0

    absdeg = math.fabs(dec)
    decdeg = math.floor(absdeg)
    if not decdeg:
        dec_remainder = absdeg
    else:
        dec_remainder = math.fmod(absdeg, decdeg)
    if not dec_remainder:
        decmin = 0
        decsec = 0.0
    else:
        decmin = math.floor(dec_remainder * 60)
        dec_remainder = math.fmod(dec_remainder, 1.0/60.0)
        if not dec_remainder:
            decsec = 0.0
        else:
            decsec = dec_remainder * 3600

    if "{:2.1f}".format(decsec) == "60.0":
        decsec = 0
        decmin += 1
    if decmin == 60:
        decmin = 0
        decdeg += 1

    if dec >= 0.0:
        decsign = '+'
    else:
        decsign = '-'
    return (rahr, ramin, rasec, decsign, decdeg, decmin, decsec)



if __name__ == "__main__":

    if not os.path.isfile(PLANETDB):
        status, message = create_database()
        print(message)
        if status:
            sys.exit(status)
    else:
        # it does exist, delete old entries
        status = delete_old()
        if status:
            sys.exit(status)

    astro_centre = EarthLocation.from_geodetic(LONGITUDE, LATITUDE, ELEVATION)

    # make ten days of planet positions and set into the database
    status = make_ten_days(astro_centre)
    if status:
        sys.exit(status)


