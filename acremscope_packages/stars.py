
import os, sys, sqlite3, math

from datetime import datetime, timedelta, timezone

from astropy import units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, name_resolve, solar_system_ephemeris, get_body, Angle, PrecessedGeocentric, ICRS
from astropy.time import Time
from astroquery.mpc import MPC
from astroquery.exceptions import InvalidQueryError
from astropy_healpix import HEALPix
import numpy as np

from .cfg import observatory, get_planetdb, get_constellation_lines, get_star_catalogs_directory, planetmags

from .sun import night_slots, Slot

# get directory containing the star catalog databases
starcatalogs = get_star_catalogs_directory()

# dictionary of planet names and magnitudes
_PLANETS = planetmags()

# Each database has a single table 'stars" with columns (HP INTEGER, GSC_ID TEXT, RA REAL, DEC REAL, MAG REAL)
# where HP is a healpix id

# database HP48.db has stars to magnitude 6, organised in 48 healpix pixels
_HP48 = os.path.join(starcatalogs, "HP48.db")

# database HP192.db has stars to magnitude 9, organised in 192 healpix pixels
_HP192 = os.path.join(starcatalogs, "HP192.db")

# database HP768.db has all stars, organised in 768 healpix pixels
_HP768 = os.path.join(starcatalogs, "HP768.db")

# HEALPix object with nside 2 and 48 pixels
_hp48 = HEALPix(nside=np.int64(2), order='nested', frame=ICRS())

# HEALPix object with nside 4 and 192 pixels
_hp192 = HEALPix(nside=np.int64(4), order='nested', frame=ICRS())

# HEALPix object with nside 8 and 768 pixels
_hp768 = HEALPix(nside=np.int64(8), order='nested', frame=ICRS())


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
    "Gets stars in the _HP48 database which are brighter than the mag_limit"
    radius = view/2.0
    hp_to_search = tuple(_hp48.cone_search_skycoord(SkyCoord(ra=ra*u.deg, dec=dec*u.deg), radius=radius * u.deg))
    try:
        con = sqlite3.connect(_HP48, detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()
        if len(hp_to_search) > 1:
            cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where HP in {hp_to_search} and MAG < {mag_limit}" )
        else:
            cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where HP = {hp_to_search[0]} and MAG < {mag_limit}" )
        result = cur.fetchall()
    finally:
        con.close()
    return result, mag_scale, mag_offset



def q2( ra, dec, view, mag_scale, mag_offset, mag_limit):
    """Get stars from the _HP192 database brighter than the mag_limit"""
    radius = view/2.0
    hp_to_search = tuple(_hp192.cone_search_skycoord(SkyCoord(ra=ra*u.deg, dec=dec*u.deg), radius=radius * u.deg))
    try:
        con = sqlite3.connect(_HP192, detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()
        if len(hp_to_search) > 1:
            cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where HP in {hp_to_search} and MAG < {mag_limit}" )
        else:
            cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where HP = {hp_to_search[0]} and MAG < {mag_limit}" )
        result = cur.fetchall()
    finally:
        con.close()
    return result, mag_scale, mag_offset


def q3(ra, dec, view, mag_scale, mag_offset, mag_limit):
    """Get stars from the _HP768 database limited by magnitude"""
    radius = view/2.0
    hp_to_search = tuple(_hp768.cone_search_skycoord(SkyCoord(ra=ra*u.deg, dec=dec*u.deg), radius=radius * u.deg))
    try:
        con = sqlite3.connect(_HP768, detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()
        if len(hp_to_search) > 1:
            cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where HP in {hp_to_search} and MAG < {mag_limit}" )
        else:
            cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where HP = {hp_to_search[0]} and MAG < {mag_limit}" )
        result = cur.fetchall()
    finally:
        con.close()
    return result, mag_scale, mag_offset



def q4(ra, dec, view, mag_scale, mag_offset, mag_limit):
    """Get stars from the _HP768 database not limited by magnitude"""
    radius = view/2.0
    hp_to_search = tuple(_hp768.cone_search_skycoord(SkyCoord(ra=ra*u.deg, dec=dec*u.deg), radius=radius * u.deg))
    try:
        con = sqlite3.connect(_HP768, detect_types=sqlite3.PARSE_DECLTYPES)
        cur = con.cursor()
        if len(hp_to_search) > 1:
            cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where HP in {hp_to_search} and MAG < {mag_limit}" )
        else:
            cur.execute( f"select {mag_scale}*MAG + {mag_offset}, RA, DEC from stars where HP = {hp_to_search[0]} and MAG < {mag_limit}" )
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
  
  

def get_named_object(target_name, tstamp, astro_centre=None):
    """Return eq_coord, altaz_coord
       where these are SkyCoord objects
       tstamp is a datetime or Time object
       return None if not found"""

    if not target_name:
        return

    solar_system_ephemeris.set('jpl')

    if astro_centre is None:
        # longitude, latitude, elevation of the astronomy centre
        longitude, latitude, elevation = observatory()
        astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    if not isinstance(tstamp, Time):
        tstamp = Time(tstamp, format='datetime', scale='utc')

    target_name_lower = target_name.lower()

    if target_name_lower in ('moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'):
        target = get_body(target_name_lower, tstamp, astro_centre)
        # target in GCRS geocentric frame
        target_altaz = target.transform_to(AltAz(obstime = tstamp, location = astro_centre))
        return  target, target_altaz

    # not a planet, see if it is something like M45 or star name, this obtains an icrs framed object
    try:
        target = SkyCoord.from_name(target_name)
    except name_resolve.NameResolveError:
        # failed to find name, maybe a minor planet
        pass
    else:
        target_altaz = target.transform_to(AltAz(obstime = tstamp, location = astro_centre))
        return  target, target_altaz

    # minor planet location
    try:
        eph = MPC.get_ephemeris(target_name, location=astro_centre, start=tstamp, number=1)
        # eph is a table of a single line, set this into a SkyCoord object
        target = SkyCoord(eph['RA'][0]*u.deg, eph['Dec'][0]*u.deg, obstime = tstamp, location = astro_centre, frame='gcrs')
        # target in GCRS geocentric frame
        target_altaz = target.transform_to(AltAz(obstime = tstamp, location = astro_centre))
    except InvalidQueryError:
        return

    return  target, target_altaz




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
            # target in GCRS frame
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
    """Return a list of lists of [ datetime, ra(icrs), dec(icrs), alt, az, ra(pg), dec(pg)] starting at the given start (a datetime object)
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
            # target in GCRS frame
            target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
            target_pg = target.transform_to(PrecessedGeocentric(obstime = time, equinox = time))
            result_list.append([dt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree, target_pg.ra.degree, target_pg.dec.degree])
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
            target_pg = target.transform_to(PrecessedGeocentric(obstime = time, equinox = time))
            result_list.append([dt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree, target_pg.ra.degree, target_pg.dec.degree])
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
            target_pg = target.transform_to(PrecessedGeocentric(obstime = dt, equinox = dt))
            result_list.append([dt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree, target_pg.ra.degree, target_pg.dec.degree])
    except InvalidQueryError:
        return

    return result_list


def get_unnamed_object_intervals(target_ra, target_dec, start, step, number, astro_centre=None):
    """Return a list of lists of [ datetime, ra(icrs), dec(icrs), alt, az, ra(pg), dec(pg)] starting at the given start (a datetime object)
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

    try:
        if isinstance(target_ra, float) or isinstance(target_ra, int):
             target_ra = target_ra*u.deg
        if isinstance(target_dec, float) or isinstance(target_dec, int):
             target_dec = target_dec*u.deg
        target = SkyCoord(target_ra, target_dec, frame='icrs')
        for dt in times:
            time = Time(dt, format='datetime', scale='utc')
            target_altaz = target.transform_to(AltAz(obstime = time, location = astro_centre))
            target_pg = target.transform_to(PrecessedGeocentric(obstime = time, equinox = time))
            result_list.append([dt, target.ra.degree, target.dec.degree, target_altaz.alt.degree, target_altaz.az.degree, target_pg.ra.degree, target_pg.dec.degree])
    except Exception:
        return

    return result_list


def chartpositions(stars, ra, dec, view):
    "Convert each star position to an x, y position for the star chart"

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

    starlist = list([float(star[0]), float(star[1]), float(star[2])] for star in stars)
    stararray = np.array(starlist)
    test1 = np.logical_or( (stararray[:,1] < 0.0), (stararray[:,1] > 360.0) )
    test2 = np.logical_or( (stararray[:,2] > max_dec), (stararray[:,2] < min_dec) )
    test = np.logical_or(test1, test2)
    stararray = np.delete(stararray, test, axis=0)

    ra_rad = np.radians(stararray[:, 1])    # ra in radians
    dec_rad = np.radians(stararray[:, 2])   # dec in radians

    delta_ra = ra_rad - ra0   # ra in radians, with ra0 subtracted from each element

    sindec = np.sin(dec_rad)
    cosdec = np.cos(dec_rad)
    cosdelta_ra = np.cos(delta_ra)

    x1 = cosdec * np.sin(delta_ra);
    y1 = sindec * cosdec0 - cosdec * cosdelta_ra * sindec0
    z1 = sindec * sindec0 + cosdec * cosdec0 * cosdelta_ra

    d = np.where(z1 < -0.9, 20.0 * np.sqrt(0.19 / ( 1.00001 - z1 * z1)), 2.0 / (z1 + 1.0))
    x = x1 * d * scale
    y = y1 * d * scale

    stackarray = np.column_stack((stararray[:, 0],x,y))
    stackarray = np.delete(stackarray, np.where((x*x + y*y)>62500), axis=0)
    return stackarray.tolist()



