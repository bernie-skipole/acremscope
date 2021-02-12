
##################################
#
# These functions populate the telescope control page
#
##################################

from datetime import datetime, timezone, timedelta
from collections import namedtuple
from struct import pack, unpack

Chart = namedtuple('Chart', ['view', 'flip', 'rot'])

Position = namedtuple('Position', ['ra', 'dec'])

#### may have to set a better 'parking position'

_PARKED = (0.0, 180.0)  # altitude, azimuth

import astropy.units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, name_resolve, solar_system_ephemeris, get_body, Angle
from astropy.time import Time
from astroquery.mpc import MPC
from astroquery.exceptions import InvalidQueryError


from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import redis_ops

from ..cfg import observatory, get_planetdb, planetmags
from ..sun import night_slots, Slot
from ..stars import get_stars, radec_to_xy, xy_constellation_lines, get_planets, get_named_object

from .sessions import livesession, doorsession

from . import remscope

# These are mean apparant visual magnitudes, except for pluto, which is a rough guesstimate

_PLANETS = planetmags()


def get_parked_radec():
    "Returns Position object of the parked position"
    # now work out ra dec
    alt,az = _PARKED
    solar_system_ephemeris.set('jpl')
    longitude, latitude, elevation = observatory()
    astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)
    altazcoord = SkyCoord(alt=alt*u.deg, az=az*u.deg, obstime = Time(datetime.utcnow(), format='datetime', scale='utc'), location = astro_centre, frame = 'altaz')
    # transform to ra, dec
    sc = altazcoord.transform_to('icrs')
    return Position(sc.ra.degree, sc.dec.degree)


def get_wanted_position(rconn_0, rconn):
    """Reads Redis to get requested Telescope position"""
    radec = redis_ops.get_wanted_position(rconn_0, rconn)
    if radec is not None:
        wanted_position = Position(*radec)
    else:
        wanted_position = get_parked_radec()
        redis_ops.set_wanted_position(wanted_position.ra, wanted_position.dec, rconn_0, rconn)
    return wanted_position


def get_chart(rconn_0):
    """Read redis to get chart parameters"""
    return Chart(*redis_ops.get_chart_parameters(rconn_0))


# livesession allows the booked in user to access the controls, but only
# if the door is open
@livesession
def control_template(skicall):
    "Fills in the control template page"
    if not remscope.is_telescope_connected(skicall):
        raise FailPage("Telescope not connected")
    # remove target name from redis
    redis_ops.del_target_name(skicall.proj_data.get("rconn_0"))
    # draw the control page chart
    _draw_chart(skicall)

# doorsession allows the booked in user to access the controls, including the door control
# as this can be done via indi, this is the appropriate decorator 
@doorsession
def indi_template(skicall):
    "Fills in the indi template page"
    # currently does nothing
    return


def _draw_chart(skicall, tstamp=None):
    """Function to draw the chart"""

    if tstamp is None:
        tstamp = datetime.utcnow()

    actual = redis_ops.get_chart_actual(skicall.proj_data.get("rconn_0"))
    # True if the chart showing actual positions rather than target position

    page_data = skicall.page_data

    wanted_position = get_wanted_position(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    status,actual_position, altaztuple = remscope.get_actual_position(skicall)

    if status:
        # Set actual scope position
        act_ra = Angle(actual_position.ra*u.deg).to_string(unit=u.hour, sep=':')
        act_dec = Angle(actual_position.dec*u.deg).to_string(unit=u.degree, sep=':')
        skicall.page_data['scopeposition', 'para_text'] = f"""
RA: {act_ra}
DEC: {act_dec}
"""

    chart = get_chart(skicall.proj_data.get("rconn_0"))

    if actual:
        page_data['interval']=3
        ra = actual_position.ra
        dec = actual_position.dec
    else:
        # do not refresh
        skicall.page_data['interval']=0
        ra = wanted_position.ra
        dec = wanted_position.dec

    try:
        view = chart.view
    except:
        raise FailPage("Invalid view")

    # set the transform on the widget
    page_data['starchart', 'transform'] = _transform(chart.flip, chart.rot)

    if view>10.0:
        page_data['starchart', 'lines'] = list(xy_constellation_lines(ra, dec, view))

    stars, scale, const = get_stars(ra, dec, view)

    # the planets database are created at 30 minutes past the hour, so get the planets for this hour
    planets = get_planets(tstamp, dec, view, scale, const)

    # convert stars ra, dec, to xy positions on the chart
    stars = list(radec_to_xy(stars, ra, dec, view))

    if planets:
        planets = list(radec_to_xy(planets, ra, dec, view))
        stars.extend(planets)
    if stars:
        page_data['starchart', 'stars'] = stars

    if actual:
        page_data['display_target', 'button_text'] = "Display target"
        if status:
            page_data['status', 'para_text'] = "Current Telescope Altitude: {:3.3f}   Azimuth: {:3.3f}".format(*altaztuple)
        else:
            page_data['status', 'para_text'] = "Communications lost. Telescope position unknown!"
    else:
        page_data['display_target', 'button_text'] = "Display actual"
        target_name = redis_ops.get_target_name(skicall.proj_data.get("rconn_0"))
        if target_name:
            page_data['status', 'para_text'] = "Target : " + target_name + " Field of view: {:3.2f}\xb0".format(view)
        else:
            page_data['status', 'para_text'] = "Target : RA {:1.3f}\xb0 Dec: {:1.3f}\xb0 FOV: {:3.2f}\xb0".format(wanted_position.ra, wanted_position.dec, view)

    # Set input fields, these always show the wanted positions
    w_ra = Angle(wanted_position.ra*u.deg).hms
    w_dec = Angle(wanted_position.dec*u.deg).signed_dms

    page_data['ra_hr', 'input_text'] = str(int(w_ra.h))
    page_data['ra_min', 'input_text'] = str(int(w_ra.m))
    page_data['ra_sec', 'input_text'] = str(w_ra.s)
    if w_dec.sign >=0:
        page_data['dec_sign', 'input_text'] = '+'
    else:
        page_data['dec_sign', 'input_text'] = '-'
    page_data['dec_deg', 'input_text'] = str(int(w_dec.d))
    page_data['dec_min', 'input_text'] = str(int(w_dec.m))
    page_data['dec_sec', 'input_text'] = str(w_dec.s)


@livesession
def refresh_chart(skicall):
    """Function to refresh the chart by json page interval call, if this is for the target, only the alt az values
       are changed, however if it is for the actual position, the whole chart is redone"""

    actual = redis_ops.get_chart_actual(skicall.proj_data.get("rconn_0"))
    # True if the chart showing actual positions rather than target position

    page_data = skicall.page_data

    if actual:
        status,actual_position, altaztuple = remscope.get_actual_position(skicall)
        chart = get_chart(skicall.proj_data.get("rconn_0"))
        ra = actual_position.ra
        dec = actual_position.dec
        try:
            view = chart.view
        except:
            raise FailPage("Invalid view")
        # set the transform on the widget
        page_data['starchart', 'transform'] = _transform(chart.flip, chart.rot)
        if view>10.0:
            page_data['starchart', 'lines'] = list(xy_constellation_lines(ra, dec, view))
        stars, scale, const = get_stars(ra, dec, view)
        # the planets database are created at 30 minutes past the hour, so get the planets for this hour
        planets = get_planets(datetime.utcnow(), dec, view, scale, const)
        # convert stars ra, dec, to xy positions on the chart
        stars = list(radec_to_xy(stars, ra, dec, view))
        if planets:
            planets = list(radec_to_xy(planets, ra, dec, view))
            stars.extend(planets)
        if stars:
            page_data['starchart', 'stars'] = stars
        if status:
            act_ra = Angle(ra*u.deg).to_string(unit=u.hour, sep=':')
            act_dec = Angle(dec*u.deg).to_string(unit=u.degree, sep=':')
            skicall.page_data['scopeposition', 'para_text'] = f"""
RA: {act_ra}
DEC: {act_dec}
"""
            page_data['status', 'para_text'] = "Current Telescope Altitude: {:3.3f}   Azimuth: {:3.3f}".format(*altaztuple)
        else:
            page_data['status', 'para_text'] = "Communications lost. Telescope position unknown!"
    else:
        wanted_position = get_wanted_position(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
        target_name = redis_ops.get_target_name(skicall.proj_data.get("rconn_0"))
        if target_name:
            page_data['status', 'para_text'] = "Target : " + target_name
        else:
            page_data['status', 'para_text'] = "Target : RA {:1.3f}\xb0 Dec: {:1.3f}\xb0".format(wanted_position.ra, wanted_position.dec)
    # and finally, do a scope getproperties, so for the next refresh things are up to date
    remscope.telescopegetproperties(skicall)

    skicall.page_data['scopestatus', 'para_text'] = f"Telescope Tracking : {remscope.get_track_state(skicall)}"



@livesession
def newradec(skicall):
    """Checks target ra, dec are valid and draws chart"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    # If an ra dec value has been input, then clear any
    # name from the name input field, and from redis
    page_data['name', 'input_text'] = ''
    redis_ops.del_target_name(skicall.proj_data.get("rconn_0"))

    try:

        ra_hr = call_data['ra_hr','input_text']
        rahr = int(ra_hr)
        if (rahr > 24) or (rahr < 0):
            raise FailPage("Invalid coordinates (RA hour out of range)")
        elif rahr == 24:
            ra_hr = "0"
        else:
            ra_hr = str(rahr)

        ra_min = call_data['ra_min','input_text']
        ramin = int(ra_min)
        if (ramin > 59) or (ramin < 0):
            raise FailPage("Invalid coordinates (RA min out of range)")
        else:
            ra_min = str(ramin)

        ra_sec = call_data['ra_sec','input_text']
        rasec = float(ra_sec)
        if (rasec >= 60.0) or (rasec < 0.0):
            raise FailPage("Invalid coordinates (RA sec out of range)")
        else:
            ra_sec = "{:.3f}".format(rasec)

        if call_data['dec_sign','input_text'] == '-':
            dec_sign = '-'
        else:
            dec_sign = '+'

        dec_deg = call_data['dec_deg','input_text']
        decdeg = int(dec_deg)
        if (decdeg > 90) or (decdeg < 0):
            raise FailPage("Invalid coordinates (dec degrees out of range)")
        else:
            dec_deg = str(decdeg)

        dec_min = call_data['dec_min','input_text']
        decmin = int(dec_min)
        if (decmin > 59) or (decmin < 0):
            raise FailPage("Invalid coordinates (dec minutes out of range)")
        else:
            dec_min = str(decmin)

        dec_sec = call_data['dec_sec','input_text']
        decsec = float(dec_sec)
        if (decsec >= 60.0) or (decsec < 0.0):
            failflag = True
            dec_sec = ''
        else:
            dec_sec = "{:.3f}".format(decsec)
    except:
        raise FailPage("Invalid coordinates (dec seconds out of range)")

    ra = Angle(ra_hr+'h'+ra_min+'m'+ra_sec+'s').degree

    if dec_sign == '-':
        dec = Angle('-'+dec_deg+'d'+dec_min+'m'+dec_sec+'s').degree
    else:
        dec = Angle(dec_deg+'d'+dec_min+'m'+dec_sec+'s').degree

    # set these wanted coordinates into redis
    redis_ops.set_wanted_position(ra, dec, skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    # chart should show target
    redis_ops.set_chart_actual(False, skicall.proj_data.get("rconn_0"))
    # now draw the chart
    _draw_chart(skicall)


@livesession
def namedradec(skicall):
    """Checks given name and draws the chart"""

    call_data = skicall.call_data
    if call_data['name','input_text']:
        target_name = call_data['name','input_text']
    else:
        raise FailPage("Invalid name")

    # from stars
    # get_named_object(target_name, tstamp, astro_centre=None)
    # Return eq_coord, altaz_coord for the tstamp

    targettime = datetime.utcnow()
    try:
        eq_coord, altaz_coord = get_named_object(target_name, targettime)
    except:
        raise FailPage("Unable to resolve the target name")

    # set the target name into redis
    redis_ops.set_target_name(target_name, skicall.proj_data.get("rconn_0"))
    redis_ops.set_wanted_position(eq_coord.ra.degree, eq_coord.dec.degree, skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    # chart should show wanted target
    redis_ops.set_chart_actual(False, skicall.proj_data.get("rconn_0"))
    # now draw the chart
    _draw_chart(skicall, tstamp=targettime)


@livesession
def plus_view(skicall):
    "reduce the view by 10%, hence magnify, and call _draw_chart"
    try:
        view, flip, rot = redis_ops.get_chart_parameters(skicall.proj_data.get("rconn_0"))
    except:
        view = 100.0
        flip = False
        rot = 0
    view = view * 0.9
    if view < 0.1:
        view = 0.1
    if view > 270.0:
        view = 270.0
    redis_ops.set_chart_parameters(view, flip, rot, skicall.proj_data.get("rconn_0"))
    # now draw the chart
    _draw_chart(skicall)


@livesession
def minus_view(skicall):
    "increase the field of view by 10%, hence reduce magnification, and call _draw_chart"
    try:
        view, flip, rot = redis_ops.get_chart_parameters(skicall.proj_data.get("rconn_0"))
    except:
        view = 100.0
        flip = False
        rot = 0
    view = view * 1.1
    if view < 0.1:
        view = 0.1
    if view > 270.0:
        view = 270.0    
    redis_ops.set_chart_parameters(view, flip, rot, skicall.proj_data.get("rconn_0"))
    # now draw the chart
    _draw_chart(skicall)


@livesession
def flip_v(skicall):
    """Flips the chart vertically - this is done with a horizontal flip plus 180 degree rotation"""

    try:
        view, flip, rot = redis_ops.get_chart_parameters(skicall.proj_data.get("rconn_0"))
    except:
        view = 100.0
        flip = False
        rot = 0

    # Do the actual flipping
    if flip:
        flipv = False
    else:
        flipv = True

    rot += 180
    if rot >= 360:
        rot -= 360

    # save the new chart parameters
    redis_ops.set_chart_parameters(view, flipv, rot, skicall.proj_data.get("rconn_0"))
    # and send a transform string to the chart
    skicall.page_data['starchart', 'transform'] = _transform(flipv, rot)


@livesession
def flip_h(skicall):
    """Flips the chart horizontally"""

    try:
        view, flip, rot = redis_ops.get_chart_parameters(skicall.proj_data.get("rconn_0"))
    except:
        view = 100.0
        flip = False
        rot = 0

    # Do the actual flipping
    if flip:
        fliph = False
    else:
        fliph = True

    # save the new chart parameters
    redis_ops.set_chart_parameters(view, fliph, rot, skicall.proj_data.get("rconn_0"))
    # and send a transform string to the chart
    skicall.page_data['starchart', 'transform'] = _transform(fliph, rot)


@livesession
def rotate_plus(skicall):
    """Rotates the chart by 30 degrees"""

    try:
        view, flip, rot = redis_ops.get_chart_parameters(skicall.proj_data.get("rconn_0"))
    except:
        view = 100.0
        flip = False
        rot = 0

    if flip:
        # Do the actual rotating
        rot -= 30
        if rot < 0:
            rot += 360
    else:
        # Do the actual rotating
        rot += 30
        if rot >= 360:
            rot -= 360

    # save the new chart parameters
    redis_ops.set_chart_parameters(view, flip, rot, skicall.proj_data.get("rconn_0"))
    # and send a transform string to the chart
    skicall.page_data['starchart', 'transform'] = _transform(flip, rot)


@livesession
def rotate_minus(skicall):
    """Rotates the chart by -30 degrees"""

    try:
        view, flip, rot = redis_ops.get_chart_parameters(skicall.proj_data.get("rconn_0"))
    except:
        view = 100.0
        flip = False
        rot = 0

    if flip:
        # Do the actual rotating
        rot += 30
        if rot >= 360:
            rot -= 360
    else:
        # Do the actual rotating
        rot -= 30
        if rot < 0:
            rot += 360

    # save the new chart parameters
    redis_ops.set_chart_parameters(view, flip, rot, skicall.proj_data.get("rconn_0"))
    # and send a transform string to the chart
    skicall.page_data['starchart', 'transform'] = _transform(flip, rot)


def _transform(flip, rot):
    "Returns transform_string"
    # set the widget transform attribute
    if flip:
        transform = "translate(510 10) scale(-1, 1)"
    else:
        transform = "translate(10 10)"

    if rot:
        transform += " rotate(" + str(rot) + ",250,250)"
    return transform


@livesession
def up_arrow(skicall):
    "Moves the chart up a bit"

    # clear any name from the name input field
    skicall.page_data['name', 'input_text'] = ''
    redis_ops.del_target_name(skicall.proj_data.get("rconn_0"))

    # The chart is the 'wanted_position'
    wanted_position = get_wanted_position(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    chart = get_chart(skicall.proj_data.get("rconn_0"))
    view = chart.view
    if view > 100.0:
        separation = 10.0
    else:
        separation = view/10.0

    rot = chart.rot
    if rot == 360:
        rot = 0

    newtarget, backangle = _new_ra_dac(wanted_position.ra, wanted_position.dec, rot, separation)
    # rotate the diagram
    newrot = backangle - 180

    if newrot > 360:
        newrot = newrot-360
    if newrot < 0:
        newrot = newrot+360

    # set these wanted coordinates into redis
    ra = newtarget.ra.degree
    dec = newtarget.dec.degree
    redis_ops.set_wanted_position(ra, dec, skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))

    # save the new chart parameters
    redis_ops.set_chart_parameters(view, chart.flip, newrot, skicall.proj_data.get("rconn_0"))

    # chart should show target
    redis_ops.set_chart_actual(False, skicall.proj_data.get("rconn_0"))

    # now draw the chart
    _draw_chart(skicall)


@livesession
def left_arrow(skicall):
    "Moves the chart left a bit"

    # clear any name from the name input field
    skicall.page_data['name', 'input_text'] = ''
    redis_ops.del_target_name(skicall.proj_data.get("rconn_0"))

    # The chart is the 'wanted_position'
    wanted_position = get_wanted_position(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    chart = get_chart(skicall.proj_data.get("rconn_0"))
    view = chart.view
    if view > 100.0:
        separation = 10.0
    else:
        separation = view/10.0

    rot = chart.rot
    if rot == 360:
        rot = 0

    if chart.flip:
        newtarget, backangle = _new_ra_dac(wanted_position.ra, wanted_position.dec, rot-90, separation)
        # rotate the diagram
        newrot = backangle-90
    else:
        newtarget, backangle = _new_ra_dac(wanted_position.ra, wanted_position.dec, rot+90, separation)
        # rotate the diagram
        newrot = backangle+90

    if newrot > 360:
        newrot = newrot-360
    if newrot < 0:
        newrot = newrot+360

    # set these wanted coordinates into redis
    ra = newtarget.ra.degree
    dec = newtarget.dec.degree
    redis_ops.set_wanted_position(ra, dec, skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))

    # save the new chart parameters
    redis_ops.set_chart_parameters(view, chart.flip, newrot, skicall.proj_data.get("rconn_0"))

    # chart should show target
    redis_ops.set_chart_actual(False, skicall.proj_data.get("rconn_0"))

    # now draw the chart
    _draw_chart(skicall)


@livesession
def right_arrow(skicall):
    "Moves the chart right a bit"

    # clear any name from the name input field
    skicall.page_data['name', 'input_text'] = ''
    redis_ops.del_target_name(skicall.proj_data.get("rconn_0"))

    # The chart is the 'wanted_position'
    wanted_position = get_wanted_position(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    chart = get_chart(skicall.proj_data.get("rconn_0"))
    view = chart.view
    if view > 100.0:
        separation = 10.0
    else:
        separation = view/10.0

    rot = chart.rot
    if rot == 360:
        rot = 0

    if chart.flip:
        newtarget, backangle = _new_ra_dac(wanted_position.ra, wanted_position.dec, rot+90, separation)
        # rotate the diagram
        newrot = backangle+90
    else:
        newtarget, backangle = _new_ra_dac(wanted_position.ra, wanted_position.dec, rot-90, separation)
        # rotate the diagram
        newrot = backangle-90

    if newrot > 360:
        newrot = newrot-360
    if newrot < 0:
        newrot = newrot+360

    # set these wanted coordinates into redis
    ra = newtarget.ra.degree
    dec = newtarget.dec.degree
    redis_ops.set_wanted_position(ra, dec, skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))

    # save the new chart parameters
    redis_ops.set_chart_parameters(view, chart.flip, newrot, skicall.proj_data.get("rconn_0"))

    # chart should show target
    redis_ops.set_chart_actual(False, skicall.proj_data.get("rconn_0"))

    # now draw the chart
    _draw_chart(skicall)


@livesession
def down_arrow(skicall):
    "Moves the chart down a bit"

    # clear any name from the name input field
    skicall.page_data['name', 'input_text'] = ''
    redis_ops.del_target_name(skicall.proj_data.get("rconn_0"))

    # The chart is the 'wanted_position'
    wanted_position = get_wanted_position(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    chart = get_chart(skicall.proj_data.get("rconn_0"))
    view = chart.view
    if view > 100.0:
        separation = 10.0
    else:
        separation = view/10.0

    rot = chart.rot
    if rot == 360:
        rot = 0

    newtarget, newrot = _new_ra_dac(wanted_position.ra, wanted_position.dec, rot+180, separation)

    if newrot > 360:
        newrot = newrot-360
    if newrot < 0:
        newrot = newrot+360

    # set these wanted coordinates into redis
    ra = newtarget.ra.degree
    dec = newtarget.dec.degree
    redis_ops.set_wanted_position(ra, dec, skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))

    # save the new chart parameters
    redis_ops.set_chart_parameters(view, chart.flip, newrot, skicall.proj_data.get("rconn_0"))

    # chart should show target
    redis_ops.set_chart_actual(False, skicall.proj_data.get("rconn_0"))

    # now draw the chart
    _draw_chart(skicall)



def _new_ra_dac(ra, dec, position_angle, separation):
    "Returns new SkyCoord and position angle back to initial ra, dec given ra,dec, position_angle and separation"

    if position_angle>=360:
        position_angle = position_angle-360
    if position_angle<0:
        position_angle = position_angle+360

    try:
        target = SkyCoord(ra*u.deg, dec*u.deg, frame='icrs')
    except Exception:
        raise FailPage("Unable to determine astropy.coordinates.SkyCoord")

    position_angle = position_angle * u.deg
    separation = separation * u.deg
    newskycoord = target.directional_offset_by(position_angle, separation)

    backpositionangle = newskycoord.position_angle(target)

    return newskycoord, int(backpositionangle.deg)


@livesession
def display_target(skicall):
    """toggles the redis flag to indicate the chart display"""
    mode = redis_ops.get_chart_actual(skicall.proj_data.get("rconn_0"))
    # save the chart display mode
    if mode:
        redis_ops.set_chart_actual(False, skicall.proj_data.get("rconn_0"))
    else:
        redis_ops.set_chart_actual(True, skicall.proj_data.get("rconn_0"))
    # now draw the chart
    _draw_chart(skicall)



@livesession
def telescope_status(skicall):
    "Get the wanted ra and dec, and convert to alt, az, send to telescope"
    wanted_position = get_wanted_position(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    try:
        target_ra = wanted_position.ra
        target_dec = wanted_position.dec
        target_name = redis_ops.get_target_name(skicall.proj_data.get("rconn_0"))
    except:
        raise FailPage("Invalid target")

    result = remscope.set_target(skicall, target_ra, target_dec, target_name)
    if result is None:
        raise FailPage("Invalid target data")

    target_altaz, target_pg = result

    skicall.page_data['scopestatus', 'para_text'] = """Command sent: Goto
RA: {}
DEC: {}
ALT: {:1.3f}\xb0
AZ: {:1.3f}\xb0""".format(target_pg.ra.to_string(unit=u.hour, sep=':'),
                          target_pg.dec.to_string(unit=u.degree, sep=':'),
                          target_altaz.alt.degree,
                          target_altaz.az.degree)

    # chart should show actual
    redis_ops.set_chart_actual(True, skicall.proj_data.get("rconn_0"))

    # now draw the chart
    _draw_chart(skicall, tstamp=datetime.utcnow())


@livesession
def altaz_template(skicall):
    "Fills in the template page of the altaz control"
    # remove target name from redis
    redis_ops.del_target_name(skicall.proj_data.get("rconn_0"))
    # This page consists of two input fields


@livesession
def altaz_goto(skicall):
    "Fills in the template page of the altaz control"
    # remove target name from redis


    call_data = skicall.call_data
    page_data = skicall.page_data

    if call_data['altaz','input_text1']:
        altitude = call_data['altaz','input_text1']
    else:
        raise FailPage("Invalid altitude")

    if call_data['altaz','input_text2']:
        azimuth = call_data['altaz','input_text2']
    else:
        raise FailPage("Invalid azimuth")

    try:
        altitude = float(altitude)
        azimuth = float(azimuth)
    except:
        raise FailPage("Invalid coordinates")

    if altitude>90.0 or altitude<-90.0:
        raise FailPage("Invalid altitude")
    if azimuth>360.0 or azimuth<0.0:
        raise FailPage("Invalid azimuth")

    try:
        if not remscope.altaz_goto(skicall, altitude, azimuth):
            raise FailPage("Failed to send coordinates")
    except:
        raise FailPage("Failed to send coordinates")

    skicall.page_data['scopestatus', 'para_text'] = """
Command sent: Goto
ALT: {:1.3f}\xb0
AZ: {:1.3f}\xb0""".format(altitude, azimuth)



