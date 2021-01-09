
import os, sys, sqlite3, math

from datetime import datetime, timedelta, timezone

import astropy.units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, name_resolve, solar_system_ephemeris, get_body, Angle
from astropy.time import Time
from astroquery.mpc import MPC
from astroquery.exceptions import InvalidQueryError

from .cfg import observatory, get_planetdb, get_constellation_lines, get_star_catalogs_directory, planetmags

from .sun import night_slots, Slot

# get directory containing the star catalog databases
starcatalogs = get_star_catalogs_directory()

# dictionary of planet names and magnitudes
_PLANETS = planetmags()

# These catalogs all consist of a single table 'stars' with columns MAG, RA, DEC
# each column being a 'REAL' value

# database cat6.db has stars to magnitude 6
_CAT6 = os.path.join(starcatalogs, "CAT6.db")

# database cat9.db has stars to magnitude 9
_CAT9 = os.path.join(starcatalogs, "CAT9.db")

# These are a set of catalogs containing stars down to magnitude 14
_CAT14_P90 = os.path.join(starcatalogs, "CAT14_P90.db")  # covers declination 50 to 90
_CAT14_P60 = os.path.join(starcatalogs, "CAT14_P60.db")  # covers declination 20 to 60
_CAT14_P30 = os.path.join(starcatalogs, "CAT14_P30.db")  # covers declination -10 to 30
_CAT14_M90 = os.path.join(starcatalogs, "CAT14_M90.db")  # covers declination -50 to -90
_CAT14_M60 = os.path.join(starcatalogs, "CAT14_M60.db")  # covers declination -20 to -60
_CAT14_M30 = os.path.join(starcatalogs, "CAT14_M30.db")  # covers declination 10 to -30


# given a view, query databases

def get_stars(ra, dec, view):
    """ finds stars, around the given ra, dec within view degrees.
        Return stars, scale, offset where scale and offset are used to calculate the svg circle diameter of a given magnitude
        such that diameter = scale * magnitude + offset
        stars is a set of [(d,ra,dec),...]
        where d is the diameter to be plotted"""
    # the views dictionary is a global dictionary defined below
    for v in views:
        if view>v:
            # call the query function
            # the q function is views[v][0]
            # and magnitude limit is views[v][1]
            scale = 0.0505*views[v][1] -1.2726          # these map scale/offset to the cutoff magnitude of the chart
            offset = 0.3667*views[v][1] + 3.6543        # constants found by emperical observation of what looks nice
            # call the query function
            return views[v][0]( ra, dec, view, scale, offset, views[v][1])


# query functions, each calls a different database catalogue (or set of catalogs)

def q1( ra, dec, view, mag_scale, mag_offset, mag_limit):
    "Gets ALL stars in the _CAT6 database which are brighter than the mag_limit"
    try:
        con = sqlite3.connect(_CAT6, detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()
        cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where MAG < {mag_limit}" )
        result = cur.fetchall()
    finally:
        con.close()
    return result, mag_scale, mag_offset



def q2( ra, dec, view, mag_scale, mag_offset, mag_limit):
    """Get stars from the _CAT9 database limited by Declination + or - view / 2 and  brighter than the mag_limit"""
    max_dec = dec + view/2.0
    min_dec = dec - view/2.0
    try:
        con = sqlite3.connect(_CAT9, detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()
        cur = con.cursor()
        cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where MAG < {mag_limit} and DEC between {min_dec} and {max_dec}" )
        result = cur.fetchall()
    finally:
        con.close()
    return result, mag_scale, mag_offset


def q3(ra, dec, view, mag_scale, mag_offset, mag_limit):
    """Get stars from one of the CAT14_? databases limited by magnitude"""
    max_dec = dec + view/2.0
    min_dec = dec - view/2.0
    if max_dec>=90 or min_dec<=-90:
        # around the poles, must look at all ra values
        qstring = f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where MAG < {mag_limit} and DEC between {min_dec} and {max_dec}"
    else:
        # ra span is wider than the dec span, as ra is not just an addition of view degrees
        if max_dec>88 or min_dec<-88:
            # close to the poles, so look at wide ra values
            max_ra = ra + 90
            min_ra = ra - 90
        elif max_dec>80 or min_dec<-80:
            # close to the poles, so look at wide ra values
            max_ra = ra + 45
            min_ra = ra - 45
        else:
            # make ra + or - view rather than view/2
            max_ra = ra + view
            min_ra = ra - view
        if max_ra > 360.0:
            max_ra = max_ra - 360
            qstring = f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where MAG < {mag_limit} and DEC between {min_dec} and {max_dec} and (ra > {min_ra} or ra < {max_ra})"
        elif min_ra < 0.0:
            min_ra = min_ra + 360
            qstring = f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where MAG < {mag_limit} and DEC between {min_dec} and {max_dec} and (ra > {min_ra} or ra < {max_ra})"
        else:
            qstring = f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where MAG < {mag_limit} and DEC between {min_dec} and {max_dec} and ra BETWEEN {min_ra} AND {max_ra}"
    # decide which database
    if dec>55:
        dbase = _CAT14_P90 # covers 50 to 90
    elif dec>25:
        dbase = _CAT14_P60 # covers 20 to 60
    elif dec>0:
        dbase = _CAT14_P30 # covers -10 to 30
    elif dec>-25:
        dbase = _CAT14_M30 # covers -30 to 10
    elif dec>-55:
        dbase = _CAT14_M60 # covers -60 to -20
    else:
        dbase = _CAT14_M90 # covers -90 to -50
    # connect to the database
    try:
        con = sqlite3.connect(dbase, detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()
        cur.execute(qstring)
        result = cur.fetchall()
    finally:
        con.close()
    return result, mag_scale, mag_offset


def q4(ra, dec, view, mag_scale, mag_offset, mag_limit):
    """Get stars from one of the CAT14_? databases not limited by magnitude"""
    max_dec = dec + view/2.0
    min_dec = dec - view/2.0
    if max_dec>=90 or min_dec<=-90:
        # around the poles, must look at all ra values
        qstring = f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where MAG < {mag_limit} and DEC between {min_dec} and {max_dec}"
    else:
        # ra span is wider than the dec span, as ra is not just an addition of view degrees
        if max_dec>88 or min_dec<-88:
            # close to the poles, so look at wide ra values
            max_ra = ra + 90
            min_ra = ra - 90
        elif max_dec>80 or min_dec<-80:
            # close to the poles, so look at wide ra values
            max_ra = ra + 45
            min_ra = ra - 45
        else:
            # make ra + or - view rather than view/2
            max_ra = ra + view
            min_ra = ra - view
        if max_ra > 360.0:
            max_ra = max_ra - 360
            qstring = f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where DEC between {min_dec} and {max_dec} and (ra > {min_ra} or ra < {max_ra})"
        elif min_ra < 0.0:
            min_ra = min_ra + 360
            qstring = f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where DEC between {min_dec} and {max_dec} and (ra > {min_ra} or ra < {max_ra})"
        else:
            qstring = f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where DEC between {min_dec} and {max_dec} and ra BETWEEN {min_ra} AND {max_ra}"
    # decide which database
    if dec>55:
        dbase = _CAT14_P90 # covers 50 to 90
    elif dec>25:
        dbase = _CAT14_P60 # covers 20 to 60
    elif dec>0:
        dbase = _CAT14_P30 # covers -10 to 30
    elif dec>-25:
        dbase = _CAT14_M30 # covers -30 to 10
    elif dec>-55:
        dbase = _CAT14_M60 # covers -60 to -20
    else:
        dbase = _CAT14_M90 # covers -90 to -50
    # connect to the database
    try:
        con = sqlite3.connect(dbase, detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()
        cur.execute(qstring)
        result = cur.fetchall()
    finally:
        con.close()
    return result, mag_scale, mag_offset



# global dictionary views, used to define which query function to call
# given the view in degrees, and the magnitude limit the
# chart will show with that view


       # degrees         query    magnitude
       # of view       function   limit


views = {   110 :      ( q1,    4.0 ),
             60 :      ( q1,    5.0 ),
             40 :      ( q1,    6.0 ),
             25 :      ( q2,    7.0 ),
             15 :      ( q2,    8.0 ),
              5 :      ( q2,    9.0 ),
              3 :      ( q3,   10.0 ),
              2 :      ( q3,   11.0 ),
            1.5 :      ( q3,   12.0 ),
            1.0 :      ( q3,   13.0 ),
            0.7 :      ( q3,   13.5 ),
            0.6 :      ( q3,   13.9 ),
            0.5 :      ( q3,   14.3 ),
            0.4 :      ( q3,   14.6 ),
            0.3 :      ( q3,   14.8 ),
              0 :      ( q4,   15.0 )
        }



def radec_to_xy(stars, ra, dec, view):
    "Generator converting each star position to an x, y position for the star chart"

    # limit centre of the chart
    ra0_deg = float(ra)
    if (ra0_deg < 0.0) or (ra0_deg > 360.0):
        ra0_deg = 0.0
    ra0 = math.radians(ra0_deg)

    dec0_deg = float(dec)
    if dec0_deg > 90.0:
        dec0_deg = 90.0
    if dec0_deg < -90.0:
        dec0_deg = -90.0
    dec0 = math.radians(dec0_deg)

    view_deg = float(view)

    # avoid division by zero
    if view_deg < 0.000001:
        view_deg = 0.00001

    # avoid extra wide angle
    if view_deg > 270.0:
        view_deg = 270.0

    max_dec = dec0_deg + view_deg / 2.0
    if max_dec > 90.0:
        max_dec = 90.0

    min_dec = dec0_deg - view_deg / 2.0
    if min_dec < -90.0:
        min_dec = -90.0

    scale = 500 / math.radians(view_deg)

    cosdec0 = math.cos(dec0)
    sindec0 = math.sin(dec0)

    # stereographic algorithm
    # taken from www.projectpluto.com/project.htm

    for star in stars:

        ra_deg = float(star[1])
        dec_deg = float(star[2])

        if (ra_deg < 0.0) or (ra_deg > 360.0):
            # something wrong, do not plot this star
            continue

        # don't calculate star position if its declination is outside required view
        # unfortunately ra is more complicated
        if dec_deg > max_dec:
            continue
        if dec_deg < min_dec:
            continue


        ra_rad = math.radians(ra_deg)
        dec_rad = math.radians(dec_deg)
        delta_ra = ra_rad - ra0
        sindec = math.sin(dec_rad)
        cosdec = math.cos(dec_rad)
        cosdelta_ra = math.cos(delta_ra)

        x1 = cosdec * math.sin(delta_ra);
        y1 = sindec * cosdec0 - cosdec * cosdelta_ra * sindec0
        z1 = sindec * sindec0 + cosdec * cosdec0 * cosdelta_ra
        if z1 < -0.9:
           d = 20.0 * math.sqrt(( 1.0 - 0.81) / ( 1.00001 - z1 * z1))
        else:
           d = 2.0 / (z1 + 1.0)
        x = x1 * d * scale
        y = y1 * d * scale

        if x*x + y*y > 62500:
            # star position is outside the circle
            continue
        yield (star[0], x, y)



def xy_constellation_lines(ra, dec, view):
    "Generator returning lines as x,y values rather than ra, dec values"
    lines = get_constellation_lines()
    if not lines:
        return

    # limit centre of the chart
    ra0_deg = float(ra)
    if (ra0_deg < 0.0) or (ra0_deg > 360.0):
        ra0_deg = 0.0
    ra0 = math.radians(ra0_deg)

    dec0_deg = float(dec)
    if dec0_deg > 90.0:
        dec0_deg = 90.0
    if dec0_deg < -90.0:
        dec0_deg = -90.0
    dec0 = math.radians(dec0_deg)

    view_deg = float(view)

    # avoid division by zero
    if view_deg < 0.000001:
        view_deg = 0.00001

    # avoid extra wide angle
    if view_deg > 270.0:
        view_deg = 270.0

    max_dec = dec0_deg + view_deg / 2.0
    if max_dec > 90.0:
        max_dec = 90.0

    min_dec = dec0_deg - view_deg / 2.0
    if min_dec < -90.0:
        min_dec = -90.0

    scale = 500 / math.radians(view_deg)

    cosdec0 = math.cos(dec0)
    sindec0 = math.sin(dec0)

    for line in lines:

        start_ra_deg = float(line[0])
        start_dec_deg = float(line[1])
        end_ra_deg = float(line[2])
        end_dec_deg = float(line[3])

        if (start_ra_deg < 0.0) or (start_ra_deg > 360.0) or (end_ra_deg < 0.0) or (end_ra_deg > 360.0):
            # something wrong, do not plot this line
            continue

        # don't draw line if either start or end declination is outside required view
        # unfortunately ra is more complicated
        if start_dec_deg > max_dec:
            continue
        if start_dec_deg < min_dec:
            continue
        if end_dec_deg > max_dec:
            continue
        if end_dec_deg < min_dec:
            continue

        # start of line
        ra_rad = math.radians(start_ra_deg)
        dec_rad = math.radians(start_dec_deg)
        delta_ra = ra_rad - ra0
        sindec = math.sin(dec_rad)
        cosdec = math.cos(dec_rad)
        cosdelta_ra = math.cos(delta_ra)

        x1 = cosdec * math.sin(delta_ra);
        y1 = sindec * cosdec0 - cosdec * cosdelta_ra * sindec0
        z1 = sindec * sindec0 + cosdec * cosdec0 * cosdelta_ra
        if z1 < -0.9:
           d = 20.0 * math.sqrt(( 1.0 - 0.81) / ( 1.00001 - z1 * z1))
        else:
           d = 2.0 / (z1 + 1.0)
        x1 = x1 * d * scale
        y1 = y1 * d * scale

        if x1*x1 + y1*y1 > 62500:
            # line start position is outside the circle
            continue

        # end of line
        ra_rad = math.radians(end_ra_deg)
        dec_rad = math.radians(end_dec_deg)
        delta_ra = ra_rad - ra0
        sindec = math.sin(dec_rad)
        cosdec = math.cos(dec_rad)
        cosdelta_ra = math.cos(delta_ra)

        x2 = cosdec * math.sin(delta_ra);
        y2 = sindec * cosdec0 - cosdec * cosdelta_ra * sindec0
        z2 = sindec * sindec0 + cosdec * cosdec0 * cosdelta_ra
        if z2 < -0.9:
           d = 20.0 * math.sqrt(( 1.0 - 0.81) / ( 1.00001 - z2 * z2))
        else:
           d = 2.0 / (z2 + 1.0)
        x2 = x2 * d * scale
        y2 = y2 * d * scale

        if x2*x2 + y2*y2 > 62500:
            # line end position is outside the circle
            continue

        yield (x1,y1,x2,y2)


def get_planets(thisdate_time, dec, view, scale, const):
    """Get planet positions for the given datetime for drawing on the chart

       Reads the planet positions from the database, which are set at hourly intervals
       (on the half hour mark) and interpolates the planet position for the requested time"""
    global _PLANETS
    # dec is the declination of the centre of the chart, and 
    # view is the diameter of the chart, so defines the maximum and minimum declination to draw
    # if any planet is outside this declination range, it is not required for the chart

    planets = []
    max_dec = dec + view/2.0
    min_dec = dec - view/2.0

    # The database holds planet positions for 30 minutes past the hour, so get the nearest time position
    dateandtime = datetime(thisdate_time.year, thisdate_time.month, thisdate_time.day, thisdate_time.hour) + timedelta(minutes=30)

    # get halfhour time before the requested time (dateminus)
    # and halfhour time after the requested time (dateplus)

    if dateandtime > thisdate_time:
        dateplus = dateandtime
        dateminus = dateandtime - timedelta(hours=1)
    else:
        dateminus = dateandtime
        dateplus = dateandtime + timedelta(hours=1)

    # thisdate_time lies between dateminus and dateplus

    # seconds from dateminus
    secfromdateminus = thisdate_time - dateminus

    secs = secfromdateminus.total_seconds()

    # for an interval of 60 minutes, which is 3600 seconds
    # position = position_at_dateminus + (position_at_dateplus - position_at_dateminus) * secs/3600

    # database connection
    con = None
    try:
        con = sqlite3.connect(get_planetdb(), detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()

        for name,mag in _PLANETS.items():
            # get the svg diameter of the planet
            d = scale*mag + const
            if d>9:
                # set a maximum diameter
                d = 9
            if d<0.1:
                # however, if less than .1, don't bother
                continue
            # For dateminus and dateplus, read the database
            cur.execute('SELECT RA,DEC FROM POSITIONS WHERE DATEANDTIME=? AND NAME=?', (dateminus, name))
            planet_minus = cur.fetchone()
            if not planet_minus:
                continue
            cur.execute('SELECT RA,DEC FROM POSITIONS WHERE DATEANDTIME=? AND NAME=?', (dateplus, name))
            planet_plus = cur.fetchone()
            if not planet_plus:
                continue

            dec_m = planet_minus[1]
            dec_p = planet_plus[1]

            # interpolate actual declination
            declination = dec_m + (dec_p - dec_m) * secs/3600
            # don't bother if outside the max and min dec range - will not appear on the chart
            if declination > max_dec:
                continue
            if declination < min_dec:
                continue

            # interpolation of ra is more complicated due to the 0-360 discontinuity
            ra_m = planet_minus[0]
            ra_p = planet_plus[0]

            span = ra_p - ra_m

            if abs(span)<180:
                # The discontinuity is not spanned, so all ok
                ra = ra_m + span * secs/3600
                planets.append((d, ra, declination))
                continue

            # The span crosses the 360 to 0 boundary
            if span > 0:
                # for example ra_p = 359
                #             ra_m = 1
                #             span = 358
                # so make ra_p a negative number ( ra_p - 360), example, ra_p becomes -1 
                # and interpolation becomes 1 + (-1-1)*sec/3600  giving a value between 1 (when sec is 0) and -1 (when sec is 3600)
                ra_p = ra_p-360
            else:
                # for example ra_p = 1
                #             ra_m = 359
                #             span = -358
                # so make ra_m a negative number ( ra_m - 360), example, ra_m becomes -1
                # and interpolation becomes -1 + (1 - (-1))*sec/3600  giving a value between -1 (when sec is 0) and 1 (when sec is 3600)
                ra_m = ra_m-360

            ra = ra_m + (ra_p - ra_m) * secs/3600
            # if ra is negative, make final ra positive again by ra + 360
            if ra<0:
                ra += 360
            planets.append((d, ra, declination))

    except:
        return []
    finally:
        if con:
            con.close()

    if not planets:
        return []

    return planets
  
  

def get_named_object(target_name, thetime, astro_centre=None):
    """Return ra, dec, alt, az in degrees for the given thetime (a datetime object)
       return None if not found"""

    solar_system_ephemeris.set('jpl')

    if astro_centre is None:
        # longitude, latitude, elevation of the astronomy centre
        longitude, latitude, elevation = observatory()
        astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    time = Time(thetime, format='datetime', scale='utc')

    target_name_lower = target_name.lower()

    if target_name_lower in ('moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'):
        target = get_body(target_name_lower, time, astro_centre)
        target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
        return  target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree

    # not a planet, see if it is something like M45 or star name

    try:
        target = SkyCoord.from_name(target_name)
    except name_resolve.NameResolveError:
        # failed to find name, maybe a minor planet
        pass
    else:
        target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
        return  target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree

    try:
        eph = MPC.get_ephemeris(target_name, start=time, number=1)
        target = SkyCoord(eph['RA'][0]*u.degree, eph['Dec'][0]*u.degree, frame='icrs')
        target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
    except InvalidQueryError:
        return

    return  target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree




def get_named_object_slots(target_name, thedate, astro_centre=None):
    """Return a list of lists of [ datetime, ra, dec, alt, az] in degrees for the given thedate (a datetime or date object)
       return None if not found, where each list is the position at the mid time of each night slot of thedate"""

    solar_system_ephemeris.set('jpl')

    if astro_centre is None:
        # longitude, latitude, elevation of the astronomy centre
        longitude, latitude, elevation = observatory()
        astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    slots = night_slots(thedate)
    midtimes = [ slot.midtime for slot in slots ]

    result_list = []

    # Test if planet
    target_name_lower = target_name.lower()

    if target_name_lower in ('moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'):
        # Its a planet
        for mt in midtimes:
            time = Time(mt, format='datetime', scale='utc')
            target = get_body(target_name_lower, time, astro_centre)
            target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
            result_list.append([mt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree])
        return result_list

    # Test if a fixed object, such as M45 - RA, DEC's will be constant, though alt, az will change
    try:
        target = SkyCoord.from_name(target_name)
    except name_resolve.NameResolveError:
        # failed to find name, maybe a minor planet
        pass
    else:
        for mt in midtimes:
            time = Time(mt, format='datetime', scale='utc')
            target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
            result_list.append([mt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree])
        return result_list

    # Test if minor planet/comet
    time = Time(midtimes[0], format='datetime', scale='utc')
    try:
        eph = MPC.get_ephemeris(target_name, step="1hour", start=time, number=len(midtimes))
        for idx, mt in enumerate(midtimes):
            target = SkyCoord(eph['RA'][idx]*u.degree, eph['Dec'][idx]*u.degree, frame='icrs')
            target_altaz = target.transform_to(AltAz(obstime = mt, location = astro_centre))
            result_list.append([mt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree])
    except InvalidQueryError:
        return

    return result_list



def get_unnamed_object_slots(target_ra, target_dec, thedate, astro_centre=None):
    """Return a list of lists of [ datetime, ra, dec, alt, az] in degrees for the given thedate (a datetime or date object)
       return None if not found, where each list is the position at the mid time of each night slot of thedate"""

    solar_system_ephemeris.set('jpl')

    if astro_centre is None:
        # longitude, latitude, elevation of the astronomy centre
        longitude, latitude, elevation = observatory()
        astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    slots = night_slots(thedate)
    midtimes = [ slot.midtime for slot in slots ]

    result_list = []

    # RA, DEC's will be constant, though alt, az will change
    try:
        if isinstance(target_ra, float) or isinstance(target_ra, int):
             target_ra = target_ra*u.deg
        if isinstance(target_dec, float) or isinstance(target_dec, int):
             target_dec = target_dec*u.deg
        target = SkyCoord(target_ra, target_dec, frame='icrs')
        for mt in midtimes:
            time = Time(mt, format='datetime', scale='utc')
            target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
            result_list.append([mt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree])
    except Exception:
        return

    return result_list



def get_named_object_intervals(target_name, start, step, number, astro_centre=None):
    """Return a list of lists of [ datetime, ra, dec, alt, az] in degrees starting at the given start (a datetime object)
       each interval is step (a timedelta object), and number is the number of rows to return
       return None if not found.
       Note, step resolution is either whole seconds, minutes or hours, so 1 minute 30 second will be applied as one minute"""

    solar_system_ephemeris.set('jpl')

    if astro_centre is None:
        # longitude, latitude, elevation of the astronomy centre
        longitude, latitude, elevation = observatory()
        astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    times = []
    for dt in range(number):
        times.append(start)
        start = start + step

    result_list = []

    # Test if planet
    target_name_lower = target_name.lower()

    if target_name_lower in ('moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'):
        # Its a planet
        for dt in times:
            time = Time(dt, format='datetime', scale='utc')
            target = get_body(target_name_lower, time, astro_centre)
            target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
            result_list.append([dt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree])
        return result_list

    # Test if a fixed object, such as M45 - RA, DEC's will be constant, though alt, az will change
    try:
        target = SkyCoord.from_name(target_name)
    except name_resolve.NameResolveError:
        # failed to find name, maybe a minor planet
        pass
    else:
        for dt in times:
            time = Time(dt, format='datetime', scale='utc')
            target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
            result_list.append([dt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree])
        return result_list

    # Test if minor planet/comet
    time = Time(times[0], format='datetime', scale='utc')
    
    seconds = step.total_seconds()
    if seconds < 60:
        stepstring = str(seconds) + "second"
    elif seconds <3600:
        stepstring = str(seconds//60) + "minute"
    else:
        stepstring = str(seconds//3600) + "hour"

    try:
        eph = MPC.get_ephemeris(target_name, step=stepstring, start=time, number=number)
        for idx, dt in enumerate(times):
            target = SkyCoord(eph['RA'][idx]*u.degree, eph['Dec'][idx]*u.degree, frame='icrs')
            target_altaz = target.transform_to(AltAz(obstime = dt, location = astro_centre))
            result_list.append([dt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree])
    except InvalidQueryError:
        return

    return result_list


def get_unnamed_object_intervals(target_ra, target_dec, start, step, number, astro_centre=None):
    """Return a list of lists of [ datetime, ra, dec, alt, az] in degrees starting at the given start (a datetime object)
       each interval is step (a timedelta object), and number is the number of rows to return
       return None if not found."""

    solar_system_ephemeris.set('jpl')

    if astro_centre is None:
        # longitude, latitude, elevation of the astronomy centre
        longitude, latitude, elevation = observatory()
        astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    times = []
    for dt in range(number):
        times.append(start)
        start = start + step

    result_list = []

    # RA, DEC's will be constant, though alt, az will change
    try:
        if isinstance(target_ra, float) or isinstance(target_ra, int):
             target_ra = target_ra*u.deg
        if isinstance(target_dec, float) or isinstance(target_dec, int):
             target_dec = target_dec*u.deg
        target = SkyCoord(target_ra, target_dec, frame='icrs')
        for dt in times:
            time = Time(dt, format='datetime', scale='utc')
            target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
            result_list.append([dt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree])
    except Exception:
        return

    return result_list




