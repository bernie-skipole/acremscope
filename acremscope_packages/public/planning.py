##################################
#
# This function creates the session planning pages
#
##################################


import os, sys, sqlite3, math, json

from datetime import date, datetime, timedelta
from collections import namedtuple

from skipole import FailPage, GoTo, ValidateError, ServerError, PageData, SectionData

# target for finder chart, note dec_sign is a string '+' or '-'
Target = namedtuple('Target', ['target_name', 'planning_date', 'target_datetime', 'str_date', 'str_time', 'ra', 'dec', 'alt', 'az',
                               'ra_hr', 'ra_min', 'ra_sec', 'dec_sign', 'dec_deg', 'dec_min', 'dec_sec', 'view', 'flip', 'rot'])



import astropy.units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz, name_resolve, solar_system_ephemeris, get_body, Angle, PrecessedGeocentric
from astropy.time import Time

from ..cfg import observatory, get_planetdb, planetmags, get_astrodata_directory
from ..sun import Slot
from ..stars import get_stars, radec_to_xy, xy_constellation_lines, get_planets, get_named_object_slots, get_unnamed_object_slots, get_named_object_intervals, get_unnamed_object_intervals

# These are mean apparant visual magnitudes, except for pluto, which is a rough guesstimate

_PLANETS = planetmags()

SIG_WEATHER = ["Clear night", "Sunny day", "Partly cloudy (night)", "Partly cloudy (day)",
               "Not used", "Mist", "Fog", "Cloudy", "Overcast", "Light rain shower (night)",
               "Light rain shower (day)", "Drizzle", "Light rain", "Heavy rain shower (night)",
               "Heavy rain shower (day)", "Heavy rain", "Sleet shower (night)", "Sleet shower (day)",
               "Sleet", "Hail shower (night)", "Hail shower (day)", "Hail", "Light snow shower (night)",
               "Light snow shower (day)", "Light snow", "Heavy snow shower (night)", "Heavy snow shower (day)",
               "Heavy snow", "Thunder shower (night)", "Thunder shower (day)", "Thunder"]



def target_from_store(skicall):
    "Returns Target tuple from store, if not found, returns None"

    stored_values = skicall.call_data['stored_values']

    if not stored_values:
        return

    if not stored_values.get('target_date'):
        # name, ra, alt may all be missing, but there will always be a date
        return

    if 'target_name' in stored_values:
        target_name = stored_values['target_name']
    else:
        target_name = 'none'

    # planning_date is the start of tabulated data, not necessarily the target date, which
    # could be in the early hours of the next day

    try:
        planning_date_str = stored_values['planning_date']
        if (not planning_date_str) or (planning_date_str == "none"):
            planning_date = None
        else:
            pyearstring,pmonthstring,pdaystring = planning_date_str.split('-')
            pyear = int(pyearstring)
            pmonth = int(pmonthstring)
            pday = int(pdaystring)
            planning_date = date(pyear, pmonth, pday)
    except:
        raise FailPage("Invalid date and time")


    str_date = stored_values['target_date']
    str_time = stored_values['target_time']
    if (not str_time) or (str_time == "none"):
        str_time = "23:0:0" # should never be used, but avoid after midnight which could imply the following day
    try:
        yearstring,monthstring,daystring = str_date.split('-')
        year = int(yearstring)
        month = int(monthstring)
        day = int(daystring)
        hourstring, minstring, secstring = str_time.split(':')
        # secstring will always be '00' as target is only calculated at minute intervals
        hour = int(hourstring)
        minute = int(minstring)
        target_datetime = datetime(year, month, day, hour, minute)
    except:
        raise FailPage("Invalid date and time")

    ra = stored_values.get('target_ra', 'none')
    dec = stored_values.get('target_dec', 'none')
    alt = stored_values.get('target_alt', 'none')
    az = stored_values.get('target_az', 'none')

    if ra == "none":
        ra_hr = ""
        ra_min = ""
        ra_sec = ""
    else:
        astropyra = Angle(ra).hms
        ra_hr = str(int(astropyra.h))
        ra_min = str(int(astropyra.m))
        ra_sec = "{:2.1f}".format(astropyra.s)

    if dec == "none":
        dec_sign = "+"
        dec_deg = ""
        dec_min = ""
        dec_sec = ""
    else:
        astropydec = Angle(dec).signed_dms
        if astropydec.sign > 0:
            dec_sign = '+'
        else:
            dec_sign = '-'
        dec_deg = str(int(astropydec.d))
        dec_min = str(int(astropydec.m))
        dec_sec = "{:2.1f}".format(astropydec.s)

    if ('view' in stored_values) and stored_values['view']:
        view = stored_values['view']
    else:
        view = "100.0"

    flip = stored_values['flip']
    rot = stored_values['rot']

    return Target(target_name, planning_date, target_datetime, str_date, str_time, ra, dec, alt, az,
                  ra_hr, ra_min, ra_sec, dec_sign, dec_deg, dec_min, dec_sec, view, flip, rot)


def set_target_from_store(skicall):
    "Copy stored values, to the set stored values"

    stored_values = skicall.call_data['stored_values']

    if not stored_values:
        return

    if not stored_values['target_date']:
        # name, ra, alt may all be missing, but there will always be a date
        return

    set_values = skicall.call_data['set_values']

    set_values['target_name_ident'] = stored_values['target_name']
    set_values['planning_date_ident'] = stored_values['planning_date']
    set_values['target_date_ident'] = stored_values['target_date']
    set_values['target_time_ident'] = stored_values['target_time']
    set_values['target_ra_ident'] = stored_values['target_ra']
    set_values['target_dec_ident'] = stored_values['target_dec']
    set_values['target_alt_ident'] = stored_values['target_alt']
    set_values['target_az_ident'] = stored_values['target_az']
    set_values['view_ident'] = stored_values['view']
    set_values['flip_ident'] = stored_values['flip']
    set_values['rot_ident'] = stored_values['rot']



def create_planning_page(skicall):
    """Fills in the planning page"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    # set date input field to be a datepicker
    page_data['add_jscript'] = """
$( "#dateradec" ).datepicker({dateFormat: "yy-mm-dd"});
$( "#datename" ).datepicker({dateFormat: "yy-mm-dd"});"""

    target = target_from_store(skicall)


    if ('ra_hr','input_text') in call_data:
        page_data['ra_hr','input_text'] = call_data['ra_hr','input_text']
    elif target and target.ra_hr:
        page_data['ra_hr','input_text'] = target.ra_hr

    if ('ra_min','input_text') in call_data:
        page_data['ra_min','input_text'] = call_data['ra_min','input_text']
    elif target and target.ra_min:
        page_data['ra_min','input_text'] = target.ra_min

    if ('ra_sec','input_text') in call_data:
        page_data['ra_sec','input_text'] = call_data['ra_sec','input_text']
    elif target and target.ra_sec:
        page_data['ra_sec','input_text'] = target.ra_sec

    if ('dec_sign','input_text') in call_data:
        page_data['dec_sign','input_text'] = call_data['dec_sign','input_text']
    elif target and target.dec_sign:
        page_data['dec_sign','input_text'] = target.dec_sign

    if ('dec_deg','input_text') in call_data:
        page_data['dec_deg','input_text'] = call_data['dec_deg','input_text']
    elif target and target.dec_deg:
        page_data['dec_deg','input_text'] = target.dec_deg

    if ('dec_min','input_text') in call_data:
        page_data['dec_min','input_text'] = call_data['dec_min','input_text']
    elif target and target.dec_min:
        page_data['dec_min','input_text'] = target.dec_min

    if ('dec_sec','input_text') in call_data:
        page_data['dec_sec','input_text'] = call_data['dec_sec','input_text']
    elif target and target.dec_sec:
        page_data['dec_sec','input_text'] = target.dec_sec

    if ('name','input_text') in call_data:
        page_data['name','input_text'] = call_data['name','input_text']
    elif target and (target.target_name != "none"):
        page_data['name','input_text'] = target.target_name

    if ('plandate') in call_data:
        page_data['dateradec', 'input_text'] = call_data['plandate']
        page_data['datename', 'input_text'] = call_data['plandate']
    elif target:
        # requires python 3.7
        #if date.fromisoformat(target.str_date) < datetime.utcnow().date():
        #    page_data['dateradec', 'input_text'] = datetime.utcnow().date().isoformat()
        #    page_data['datename', 'input_text'] = datetime.utcnow().date().isoformat()
        #else:
        #    page_data['dateradec', 'input_text'] = target.str_date
        #    page_data['datename', 'input_text'] = target.str_date
        page_data['dateradec', 'input_text'] = target.planning_date.isoformat()
        page_data['datename', 'input_text'] = target.planning_date.isoformat()
    else:
        page_data['dateradec', 'input_text'] = datetime.utcnow().date().isoformat()
        page_data['datename', 'input_text'] = datetime.utcnow().date().isoformat()


def check_target(skicall):
    """Checks target ra, dec or name are valid strings"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    if call_data['dateradec','input_text']:
        call_data['plandate'] = call_data['dateradec','input_text']
    elif call_data['datename','input_text']:
        call_data['plandate'] = call_data['datename','input_text']
    else:
        call_data['plandate'] = datetime.utcnow().date().isoformat()

    failflag = False
    failmessage = "Invalid target"
    if call_data['ra_hr','input_text']:
        ra_hr = call_data['ra_hr','input_text']
        try:
            rahr = int(ra_hr)
            if (rahr > 24) or (rahr < 0):
                failflag = True
                ra_hr = ''
            elif rahr == 24:
                rahr = 0
                ra_hr = "0"
            else:
                ra_hr = str(rahr)
        except:
            failflag = True
            ra_hr = ''
        call_data['ra_hr','input_text'] = ra_hr

    if call_data['ra_min','input_text']:
        ra_min = call_data['ra_min','input_text']
        try:
            ramin = int(ra_min)
            if (ramin > 59) or (ramin < 0):
                failflag = True
                ra_min = ''
            else:
                ra_min = str(ramin)
        except:
            failflag = True
            ra_min = ''
        call_data['ra_min','input_text'] = ra_min

    if call_data['ra_sec','input_text']:
        ra_sec = call_data['ra_sec','input_text']
        try:
            rasec = float(ra_sec)
            if (rasec >= 60.0) or (rasec < 0.0):
                failflag = True
                ra_sec = ''
            else:
                ra_sec = "{:2.1f}".format(rasec)
        except:
            failflag = True
            ra_sec = ''
        call_data['ra_sec','input_text'] = ra_sec

    if call_data['dec_sign','input_text'] != '-':
        call_data['dec_sign','input_text'] = '+'

    if call_data['dec_deg','input_text']:
        dec_deg = call_data['dec_deg','input_text']
        try:
            decdeg = int(dec_deg)
            if (decdeg > 90) or (decdeg < 0):
                failflag = True
                dec_deg = ''
            else:
                dec_deg = str(decdeg)
        except:
            failflag = True
            dec_deg = ''
        call_data['dec_deg','input_text'] = dec_deg


    if call_data['dec_min','input_text']:
        dec_min = call_data['dec_min','input_text']
        try:
            decmin = int(dec_min)
            if (decmin > 59) or (decmin < 0):
                failflag = True
                dec_min = ''
            else:
                dec_min = str(decmin)
        except:
            failflag = True
            dec_min = ''
        call_data['dec_min','input_text'] = dec_min

    if call_data['dec_sec','input_text']:
        dec_sec = call_data['dec_sec','input_text']
        try:
            decsec = float(dec_sec)
            if (decsec >= 60.0) or (decsec < 0.0):
                failflag = True
                dec_sec = ''
            else:
                dec_sec = "{:2.1f}".format(decsec)
        except:
            failflag = True
            dec_sec = ''
        call_data['dec_sec','input_text'] = dec_sec

    if call_data['ra_hr','input_text']:
        # declination must be given
        if not call_data['dec_deg','input_text']:
            failflag = True
        # name must be empty
        if call_data['name','input_text']:
            failmessage = "Either name or coordinates, not both!"
            failflag = True
    else:
        # all the remaining coordinates must be empty
        if call_data['ra_min','input_text'] or call_data['ra_sec','input_text'] or call_data['dec_deg','input_text']:
            failflag = True
        # and instead a name must be given
        if not call_data['name','input_text']:
            failflag = True


    if call_data['dec_deg','input_text']:
        # ra must be given
        if not call_data['ra_hr','input_text']:
            failflag = True
        # name must be empty
        if call_data['name','input_text']:
            failmessage = "Either name or coordinates, not both!"
            failflag = True
    else:
        # all the remaining coordinates must be empty
        if call_data['dec_min','input_text'] or call_data['dec_sec','input_text'] or call_data['ra_hr','input_text']:
            failflag = True
        # and instead a name must be given
        if not call_data['name','input_text']:
            failflag = True

    # create a date object and set into call_data['thisdate']

    if not failflag:
        failmessage = "Invalid date"

    targetdate = call_data['plandate'].split("-")
    if len(targetdate) == 3:
        yr, mth, day = targetdate
        try:
            yr = int(yr)
        except:
            failflag = True
        else:
            if yr<2000 or yr>2100:
                failflag = True
        try:
            mth = int(mth)
        except:
            failflag = True
        else:
            if mth<1 or mth>12:
                failflag = True
        try:
            day = int(day)
        except:
            failflag = True
        else:
            if day<1 or day>31:
                failflag = True
        if not failflag:
            try:
                call_data['thisdate'] = date(yr, mth, day)
            except ValueError:
                failflag = True
    else:
        failflag = True

    if failflag:
        raise FailPage(failmessage)



def show_target(skicall):
    "Shows the target alt azimuth table"

    call_data = skicall.call_data
    page_data = skicall.page_data

    if 'flip' in call_data['stored_values']:
        call_data['set_values']['flip_ident'] = call_data['stored_values']['flip']
    if 'rot' in call_data['stored_values']:
        call_data['set_values']['rot_ident'] = call_data['stored_values']['rot']

    # keep the field of view
    if 'view' in call_data['stored_values']:
        call_data['set_values']['view_ident'] = call_data['stored_values']['view']
    else:
        call_data['set_values']['view_ident'] = "100.0"

    # longitude, latitude, elevation of the astronomy centre
    longitude, latitude, elevation = observatory()
    #elevation = elevation * u.m

    astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    table = []
    # List of lists - each inner list describing a row.
    # Index 0, 1 and 2 is the text to place in the first three columns,
    # Index 3, 4 is the two get field contents of the first link,
    # Index 5, 6 is the two get field contents of the second link.
    # Index 7 - True if the first button and link is to be shown, False if not.
    # Index 8 - True if the second button and link is to be shown, False if not

    # target_ra = '19h50m47.6s'
    # target_dec = '+08d52m12.0s'

    if call_data['ra_hr','input_text']:
        target_ra = call_data['ra_hr','input_text'] + 'h'
        if call_data['ra_min','input_text']:
            target_ra += call_data['ra_min','input_text'] + 'm'
        if call_data['ra_sec','input_text']:
            target_ra += call_data['ra_sec','input_text'] + 's'
    else:
        target_ra = ''

    if call_data['dec_deg','input_text']:
        target_dec = call_data['dec_deg','input_text'] + 'd'
        if call_data['dec_sign','input_text']:
            target_dec = call_data['dec_sign','input_text'] + target_dec
        if call_data['dec_min','input_text']:
            target_dec += call_data['dec_min','input_text'] + 'm'
        if call_data['dec_sec','input_text']:
            target_dec += call_data['dec_sec','input_text'] + 's'
    else:
        target_dec = ''


    if call_data['name','input_text']:
        target_name = call_data['name','input_text']
        target_ra = "none"
        target_dec = "none"
        try:
            target_list = get_named_object_slots(target_name, call_data['thisdate'], astro_centre)
        except Exception:
            page_data['name','input_text'] = call_data['name','input_text']
            page_data['dateradec','input_text'] = call_data['plandate']
            page_data['datename','input_text'] = call_data['plandate']
            raise FailPage("Failed to resolve the name")
        if target_list is None:
            page_data['name','input_text'] = call_data['name','input_text']
            page_data['dateradec','input_text'] = call_data['plandate']
            page_data['datename','input_text'] = call_data['plandate']
            raise FailPage("Unable to resolve the target name")
        page_data['toppara', 'para_text'] = "Altitude and azimuth for %s" % (target_name,)
        call_data['set_values']['target_name_ident'] = target_name
    else:
        target_name = ''
        # no target name, so it must be a fixed ra dec point
        if (not target_ra) or (not target_ra):
            raise FailPage("Failed to resolve the target")
        target_list = get_unnamed_object_slots(target_ra, target_dec, call_data['thisdate'], astro_centre)
        if target_list is None:
            page_data['dateradec','input_text'] = call_data['plandate']
            page_data['datename','input_text'] = call_data['plandate']
            raise FailPage("Unable to resolve the target")
        page_data['toppara', 'para_text'] = "Altitude and azimuth for %s, %s" % (target_ra, target_dec)
        call_data['set_values']['target_name_ident'] = "none"


    for item in target_list:
        # each item is a list [ datetime, ra, dec, alt, az] in degrees
        row = [str(item[0].hour) + ":30"]
        # get ra and dec of the slot
        slot_ra = item[1]
        slot_dec = item[2]
        # get ra, dec in hms, dms
        slot_rahr, slot_ramin, slot_rasec, slot_decsign, slot_decdeg, slot_decmin, slot_decsec = _ra_dec_conversion(slot_ra, slot_dec)
        row.append("{:2.1f}".format(item[3]))
        row.append("{:2.1f}".format(item[4]))
        row.append(item[0].isoformat(sep='T'))
        row.append('')
        row.append(item[0].isoformat(sep='T'))
        row.append("{:2.1f}:{:2.1f}:{}h{}m{:2.1f}s:{}{}d{}m{:2.1f}s".format(item[3],
                                                                            item[4],
                                                                            slot_rahr,
                                                                            slot_ramin,
                                                                            slot_rasec,
                                                                            slot_decsign,
                                                                            slot_decdeg,
                                                                            slot_decmin,
                                                                            slot_decsec))
        row.append(True)
        row.append(True)
        table.append(row)

    page_data['fromdate','para_text'] = "mid - time of observing sessions for the evening of " + target_list[0][0].date().isoformat()
    page_data['ephems','contents'] = table
    page_data['todate','para_text'] = "To mid-time of the last session in the morning of " + target_list[-1][0].date().isoformat()

    call_data['set_values']['target_date_ident'] = call_data['plandate']
    call_data['set_values']['planning_date_ident'] = call_data['plandate']
    # These may be 'none' as no specific time has been set, which will be done when the finder chart is called
    # note, the finder cannot used stored dates yet, as the date chosen is over a two day period, so must be delivered by get field.
    call_data['set_values']['target_time_ident'] = "none"
    call_data['set_values']['target_ra_ident'] = target_ra
    call_data['set_values']['target_dec_ident'] = target_dec
    call_data['set_values']['target_alt_ident'] = "none"
    call_data['set_values']['target_az_ident'] = "none"



def detail_planet(skicall):
    "accept a planet field from session planets page, and fills the detail table"

    call_data = skicall.call_data
    page_data = skicall.page_data

    stored_values = skicall.call_data['stored_values']

    if 'received_data' not in skicall.submit_dict:
        raise FailPage("Invalid planet")

    datadict = skicall.submit_dict['received_data']

    if len(datadict) != 1:
        raise FailPage("Invalid planet")

    for val in datadict.values():
        position = val

    try:
        splitposition = position.split(":")
        target_name = splitposition[0].lower()
        ra = Angle(splitposition[1]).hms
        dec = Angle(splitposition[2]).signed_dms
        stralt = splitposition[3]
        straz = splitposition[4]
        alt = float(stralt)
        az = float(straz)
    except:
        raise FailPage("Invalid position parameters")

    if (target_name not in _PLANETS) and ( target_name != 'moon'):
        # given target is not a planet, nor moon
        raise FailPage("Invalid planet")

    if alt>90.0 or alt<-90.0:
        raise FailPage("Invalid Altitude")
    if az>360.0 or az<0.0:
        raise FailPage("Invalid Azimuth")

    stored_values['target_name'] = splitposition[0]
    stored_values['target_ra'] = splitposition[1]
    stored_values['target_dec'] = splitposition[2]
    stored_values['target_alt'] = stralt
    stored_values['target_az'] = straz
    stored_values['view'] = "100.0"
    stored_values['back'] = "30201"

    storedtarget = target_from_store(skicall)

    # hold the target parameters
    set_target_from_store(skicall)

    try:
        datestring = stored_values['target_date']
        timestring = stored_values['target_time']
        yearstring,monthstring,daystring = datestring.split('-')
        year = int(yearstring)
        month = int(monthstring)
        day = int(daystring)
        hourstring, minstring, secstring = timestring.split(':')
        hour = int(hourstring)
        minute = int(minstring)
        start = datetime(year=year, month=month, day=day, hour=hour, minute=0, second=0)
    except:
        raise FailPage("Invalid date and time")

    # need seven rows at ten minute intervals
    step = timedelta(minutes=10)
    number = 7

    result_list = get_named_object_intervals(target_name, start, step, number)

    # result list is a list of lists : [ datetime, ra, dec, alt, az] in degrees

    page_data['table', 'titles'] = ["Time (UTC)", "RA", "DEC", "ALT (Degrees)", "AZ (Degrees)"]

    # for each cell; [0:text in the table, 1:the text color, 2:the background color]

    contents = []
    for row in result_list:
        t = row[0]
        tstring = str(t.hour) + ":"
        if t.minute:
            tstring = tstring + str(t.minute)
        else:
            tstring = tstring + "00"
        contents.append([tstring, '', ''])
        ra_angle = Angle(row[1] * u.deg)
        contents.append([ra_angle.to_string(unit='hourangle', precision=1, sep='hms'), '', ''])
        dec_angle = Angle(row[2] * u.deg)
        contents.append([dec_angle.to_string(unit=u.deg, precision=1, sep='dms'), '', ''])
        if row[3] > 5:
            contents.append(["{:3.2f}".format(row[3]), '', ''])
        else:
            contents.append(["{:3.2f}".format(row[3]), 'red', 'grey'])
        contents.append(["{:3.2f}".format(row[4]), '', ''])

    page_data['table', 'contents'] = contents

    page_data['toppara', 'para_text'] = "Ephemeris for %s" % (target_name,)

    page_data['fromdate','para_text'] = "at 10 minute intervals for session starting " + result_list[0][0].isoformat(sep=' ')
    page_data['todate','para_text'] = "and ending " + result_list[-1][0].isoformat(sep=' ')
    page_data['back', 'link_ident'] = "30201"
    page_data['printout', 'get_field1'] = datestring + "T" + timestring

    page_data['coords', 'get_field1'] = datestring + "T" + timestring
    page_data['coords', 'button_text'] = "Precessed"
    page_data['coords', 'get_field2'] = "session_pg"


def detail(skicall):
    """Fills in the detail page, from ident data and received hour info"""

    call_data = skicall.call_data
    pd = call_data['pagedata']
    sd_weather = SectionData("weather")

    # gets a Target tuple from call_data['stored_values']
    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    # copy call_data['stored_values'] into call_data['set_values']
    set_target_from_store(skicall)

    target_datetime = call_data.get(('ephems', 'get_field1_1'))
    if not target_datetime:
        target_datetime = call_data.get(('coords', 'get_field1'))

    if not target_datetime:
        # no time data
        raise FailPage("Target date and time unavailable")

    # altaz or pg, use altaz as default
    altaz = True
    back_to_session = False
    if ('coords', 'get_field2') in call_data:
        if call_data['coords', 'get_field2'] == "pg":
            altaz = False
        if call_data['coords', 'get_field2'] == "session_pg":
            altaz = False
            back_to_session = True
        if call_data['coords', 'get_field2'] == "session_altaz":
            back_to_session = True

    target_ra = ''
    target_dec = ''
    target_name = ''

    # date is storedtarget.str_date, but in this case, the date and time are obtained from the submitted get field
    try:
        datestring, timestring = target_datetime.split('T')
        yearstring,monthstring,daystring = datestring.split('-')
        year = int(yearstring)
        month = int(monthstring)
        day = int(daystring)
        hourstring, minstring, secstring = timestring.split(':')
        hour = int(hourstring)
        minute = int(minstring)
        start = datetime(year=year, month=month, day=day, hour=hour, minute=0, second=0)
    except:
        raise FailPage("Invalid date and time")

    # ra is plan[1] - or 'none'
    if storedtarget.ra != 'none':
        target_ra = storedtarget.ra
    # dec is plan[2] - or 'none'
    if storedtarget.dec != 'none':
        target_dec = storedtarget.dec
    # name is rest, may have a , in it
    if storedtarget.target_name != 'none':
        target_name = storedtarget.target_name

    # need seven rows at ten minute intervals
    step = timedelta(minutes=10)
    number = 7

    if target_name:
        result_list = get_named_object_intervals(target_name, start, step, number)
    else:
        result_list = get_unnamed_object_intervals(storedtarget.ra, storedtarget.dec, start, step, number)

    # result list is a list of lists : [ datetime, ra(J2000), dec(J2000), alt, az, ra(precessed), dec(precessed)]

    if altaz:
        pd['table', 'titles'] = ["Time (UTC)", "RA (J2000)", "DEC (J2000)", "ALT (Degrees)", "AZ (Degrees)"]
    else:
        pd['table', 'titles'] = ["Time (UTC)", "RA (J2000)", "DEC (J2000)", "RA (Precessed)", "DEC (Precessed)"]

    # for each cell; [0:text in the table, 1:the text color, 2:the background color]

    contents = []
    for row in result_list:
        t = row[0]
        tstring = str(t.hour) + ":"
        if t.minute:
            tstring = tstring + str(t.minute)
        else:
            tstring = tstring + "00"
        contents.append([tstring, '', ''])
        ra_angle = Angle(row[1] * u.deg)
        contents.append([ra_angle.to_string(unit='hourangle', precision=1, sep='hms'), '', ''])
        dec_angle = Angle(row[2] * u.deg)
        contents.append([dec_angle.to_string(unit=u.deg, precision=1, sep='dms'), '', ''])
        if altaz:
            if row[3] > 5:
                contents.append(["{:3.2f}".format(row[3]), '', ''])
            else:
                contents.append(["{:3.2f}".format(row[3]), 'red', 'grey'])
            contents.append(["{:3.2f}".format(row[4]), '', ''])
        else:
            ra_pg = Angle(row[5] * u.deg).to_string(unit='hourangle', precision=1, sep='hms')
            dec_pg = Angle(row[6] * u.deg).to_string(unit=u.deg, precision=1, sep='dms')
            if row[3] > 5:
                contents.append([ra_pg, '', ''])
                contents.append([dec_pg, '', ''])
            else:
                contents.append([ra_pg, 'red', 'grey'])
                contents.append([dec_pg, 'red', 'grey'])

    pd['table', 'contents'] = contents

    if target_name:
        pd['toppara', 'para_text'] = "Ephemeris for %s" % (target_name,)
    else:
        pd['toppara', 'para_text'] = "Ephemeris for %s, %s" % (target_ra, target_dec)
    pd['fromdate','para_text'] = "at 10 minute intervals for session starting " + result_list[0][0].isoformat(sep=' ')
    pd['todate','para_text'] = "and ending " + result_list[-1][0].isoformat(sep=' ')

    pd['printout', 'get_field1'] = target_datetime
    pd['coords', 'get_field1'] = target_datetime
    if altaz:
        pd['coords', 'button_text'] = "Precessed"
        pd['printout', 'get_field2'] = "altaz"
        if back_to_session:
            pd['coords', 'get_field2'] = "session_pg"
            pd['back', 'link_ident'] = "30201"
        else:
            pd['coords', 'get_field2'] = "pg"
    else:
        pd['coords', 'button_text'] = "Alt Az"
        pd['printout', 'get_field2'] = "pg"
        if back_to_session:
            pd['coords', 'get_field2'] = "session_altaz"
            pd['back', 'link_ident'] = "30201"
        else:
            pd['coords', 'get_field2'] = "altaz"


    # datetime needed in a format like 2021-06-13T12:00Z
    thistime = start.strftime("%G-%m-%dT%H:00Z")
    weatherfile = os.path.join(get_astrodata_directory(),"weather.json")
    try:
        with open(weatherfile, 'r') as fp:
            weather_dict = json.load(fp)

        if thistime not in weather_dict:
            sd_weather.show = False
        else:
            weathernow = weather_dict[thistime]
            columns = list(zip(*weathernow))
            sd_weather["wtable","col1"] = columns[0]
            sd_weather["wtable","col2"] = columns[1]
            sd_weather["wtable","col3"] = columns[2]
            sd_weather["weatherhead","large_text"] = f"Met office data for UTC time : {thistime[:-4]}"
            try:
                index = columns[0].index("Significant Weather Code")
                code = int(columns[1][index])
                sd_weather["weatherhead","small_text"] = "Weather summary : " + SIG_WEATHER[code]
            except:
                pass                
            sd_weather["weatherhead","large_text"]
    except:
        # The file does not exist, or is not readable by json
        sd_weather.show = False

    pd.update(sd_weather)
    skicall.update(pd)



def detailprint(skicall):
    """Fills in the detail printout page, from ident data and received hour info"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    if ('printout', 'get_field1') not in call_data:
        # no time data
        raise FailPage("Target date and time unavailable")

    # altaz or pg, use altaz as default
    altaz = True
    if (('printout', 'get_field2') in call_data) and call_data['printout', 'get_field2'] == "pg":
        altaz = False


    target_ra = ''
    target_dec = ''
    target_name = ''

    # date is storedtarget.str_date, but in this case, the date and time are obtained from the submitted get field
    try:
        datestring, timestring = call_data['printout', 'get_field1'].split('T')
        yearstring,monthstring,daystring = datestring.split('-')
        year = int(yearstring)
        month = int(monthstring)
        day = int(daystring)
        hourstring, minstring, secstring = timestring.split(':')
        hour = int(hourstring)
        minute = int(minstring)
        start = datetime(year=year, month=month, day=day, hour=hour, minute=0, second=0)
    except:
        raise FailPage("Invalid date and time")

    # ra is storedtarget.ra - or 'none'
    if storedtarget.ra != 'none':
        target_ra = storedtarget.ra
    # dec is storedtarget.dec - or 'none'
    if storedtarget.dec != 'none':
        target_dec = storedtarget.dec
    # name is rest, may have a , in it
    if storedtarget.target_name != 'none':
        target_name = storedtarget.target_name

    # longitude, latitude, elevation of the astronomy centre
    longitude, latitude, elevation = observatory()
    #elevation = elevation * u.m

    astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    # need seven rows at ten minute intervals
    step = timedelta(minutes=10)
    number = 7

    solar_system_ephemeris.set('jpl')
    if target_name:
        result_list = get_named_object_intervals(target_name, start, step, number, astro_centre)
    else:
        result_list = get_unnamed_object_intervals(storedtarget.ra, storedtarget.dec, start, step, number, astro_centre)

    # result list is a list of lists : [ datetime, ra(J2000), dec(J2000), alt, az, ra(precessed), dec(precessed)]

    if altaz:
        page_data['table', 'titles'] = ["Time (UTC)", "RA (J2000)", "DEC (J2000)", "ALT (Degrees)", "AZ (Degrees)"]
    else:
        page_data['table', 'titles'] = ["Time (UTC)", "RA (J2000)", "DEC (J2000)", "RA (Precessed)", "DEC (Precessed)"]

    # for each cell; [0:text in the table, 1:the text color, 2:the background color]

    contents = []
    for row in result_list:
        t = row[0]
        tstring = str(t.hour) + ":"
        if t.minute:
            tstring = tstring + str(t.minute)
        else:
            tstring = tstring + "00"
        contents.append([tstring, '', ''])
        ra_angle = Angle(row[1] * u.deg)
        contents.append([ra_angle.to_string(unit='hourangle', precision=1, sep='hms'), '', ''])
        dec_angle = Angle(row[2] * u.deg)
        contents.append([dec_angle.to_string(unit=u.deg, precision=1, sep='dms'), '', ''])
        if altaz:
            contents.append(["{:3.2f}".format(row[3]), '', ''])
            contents.append(["{:3.2f}".format(row[4]), '', ''])
        else:
            ra_pg = Angle(row[5] * u.deg).to_string(unit='hourangle', precision=1, sep='hms')
            dec_pg = Angle(row[6] * u.deg).to_string(unit=u.deg, precision=1, sep='dms')
            contents.append([ra_pg, '', ''])
            contents.append([dec_pg, '', ''])

    page_data['table', 'contents'] = contents

    if target_name:
        page_data['toppara', 'para_text'] = "Ephemeris for %s" % (target_name,)
    else:
        page_data['toppara', 'para_text'] = "Ephemeris for %s, %s" % (target_ra, target_dec)

    page_data['toppara', 'para_text']  += """
Observatory longitude: {:2.3f}, latitude: {:2.3f}, elevation: {:2.1f}""".format(longitude, latitude, elevation)
    page_data['fromdate','para_text'] = "at 10 minute intervals for session starting " + result_list[0][0].isoformat(sep=' ')
    page_data['todate','para_text'] = "and ending " + result_list[-1][0].isoformat(sep=' ')




def target_from_stored_planning(skicall):
    """Used by the back key, reads ident and sets values into call_data as if
       call data had been created from a submitted form"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    call_data['ra_hr','input_text'] = storedtarget.ra_hr
    call_data['ra_min','input_text'] = storedtarget.ra_min
    call_data['ra_sec','input_text'] = storedtarget.ra_sec
    call_data['dec_sign','input_text'] = storedtarget.dec_sign
    call_data['dec_deg','input_text'] = storedtarget.dec_deg
    call_data['dec_min','input_text'] = storedtarget.dec_min
    call_data['dec_sec','input_text'] = storedtarget.dec_sec
    if storedtarget.target_name == 'none':
        call_data['name','input_text'] = ''
    else:
        call_data['name','input_text'] = storedtarget.target_name

    call_data['thisdate'] = storedtarget.planning_date
    if storedtarget.planning_date:
        call_data['plandate'] = storedtarget.planning_date.isoformat()
    else:
        call_data['plandate'] = ''



def finder_target(skicall):
    """Reads ident and sets target_name into call_data"""

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    if storedtarget.target_name != 'none':
        skicall.call_data['target_name'] = storedtarget.target_name
    else:
        skicall.call_data['target_name'] = ''



def create_finder(skicall):
    """Called from ephem table to display a finder chart, accepts inputs and places them into stored data
       then calls _draw_finder(skicall) which does the actual drawing from the stored data"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    stored_values = skicall.call_data['stored_values']

    # stored_values['target_name'] is already set, to either none or the item name
    # stored_values['planning_date'] is already set

    # the date, time and positions are obtained from submitted get field
    if ('ephems', 'get_field2_1') in call_data:
        thisdate_time = call_data['ephems', 'get_field2_1']
    else:
        raise FailPage("Invalid date and time")

    try:
        datestring, timestring = thisdate_time.split('T')
        yearstring,monthstring,daystring = datestring.split('-')
        year = int(yearstring)
        month = int(monthstring)
        day = int(daystring)
        hourstring, minstring, secstring = timestring.split(':')
        hour = int(hourstring)
        minute = int(minstring)
    except:
        raise FailPage("Invalid date and time")

    # set the date and time string into store
    stored_values['target_date'] = datestring
    stored_values['target_time'] = timestring

    # the alt,az,ra,dec positions are obtained from submitted get field

    if ('ephems', 'get_field2_2') in call_data:
        position = call_data['ephems', 'get_field2_2']
    else:
        raise FailPage("Invalid position parameters")

    try:
        splitposition = position.split(":")
        stralt = splitposition[0]
        straz = splitposition[1]
        alt = float(stralt)
        az = float(straz)
        ra = Angle(splitposition[2]).hms
        dec = Angle(splitposition[3]).signed_dms
    except:
        raise FailPage("Invalid position parameters")

    if alt>90.0 or alt<-90.0:
        raise FailPage("Invalid Altitude")
    if az>360.0 or az<0.0:
        raise FailPage("Invalid Azimuth")

    stored_values['target_ra'] = splitposition[2]
    stored_values['target_dec'] = splitposition[3]
    stored_values['target_alt'] = "{:2.1f}".format(alt)
    stored_values['target_az'] = "{:2.1f}".format(az)

    # field of view is may be available, or just 100 if called from the ephems table
    if ('view' in stored_values) and stored_values['view']:
        view = float(stored_values['view'])
    else:
        view = 100.0
        stored_values['view'] = "100.0"

    # now draw the chart
    _draw_finder(skicall)


def plus_view(skicall):
    "reduce the view by 10%, hence magnify, and call _draw_finder"
    try:
        view = float(skicall.call_data['stored_values']['view'])
    except:
        view = 100.0
    view = view * 0.9
    if view < 0.1:
        view = 0.1
    if view > 270.0:
        view = 270.0
    skicall.call_data['stored_values']['view'] = "{:3.2f}".format(view)
    # now draw the chart
    _draw_finder(skicall)


def minus_view(skicall):
    "increase the field of view by 10%, hence reduce magnification, and call _draw_finder"
    try:
        view = float(skicall.call_data['stored_values']['view'])
    except:
        view = 100.0
    view = view * 1.1
    if view < 0.1:
        view = 0.1
    if view > 270.0:
        view = 270.0    
    skicall.call_data['stored_values']['view'] = "{:3.2f}".format(view)
    # now draw the chart
    _draw_finder(skicall)


def set_view(skicall):
    "accept a view input field, set it into stored data, and call _draw_finder"
    if ('view','input_text') not in skicall.call_data:
        raise FailPage("Field of view not given")
    try:
        view = float(skicall.call_data['view','input_text'])
    except:
        raise FailPage("Invalid field of view")
    if view < 0.1:
        view = 0.1
    if view > 270.0:
        view = 270.0
    skicall.call_data['stored_values']['view'] = "{:3.2f}".format(view)
    # now draw the chart
    _draw_finder(skicall)


def _new_ra_dac(ra, dec, position_angle, separation):
    "Returns new SkyCoord and position angle back to initial ra, dec given ra,dec, position_angle and separation"

    if position_angle>=360:
        position_angle = position_angle-360
    if position_angle<0:
        position_angle = position_angle+360

    try:
        target = SkyCoord(ra, dec, frame='icrs')
    except Exception:
        raise FailPage("Unable to determine astropy.coordinates.SkyCoord")

    position_angle = position_angle * u.deg
    separation = separation * u.deg
    newskycoord = target.directional_offset_by(position_angle, separation)

    backpositionangle = newskycoord.position_angle(target)

    return newskycoord, int(backpositionangle.deg)


def up_arrow(skicall):
    "Moves the finder chart up a bit"

    call_data = skicall.call_data

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    try:
        ra = Angle(storedtarget.ra).hms
        ra = ra.h * 360.0/24.0 + ra.m * 360.0/(24.0*60.0) +  ra.s * 360.0/(24.0*60.0*60.0)
        dec1 = Angle(storedtarget.dec).signed_dms
        dec = dec1.d + dec1.m/60.0 + dec1.s/3600.0
        if dec1.sign < 1:
            dec = -1 * dec
    except:
        raise FailPage("Invalid target data")

    try:
        view = float(storedtarget.view)
    except:
        view = 100.0

    if view > 100.0:
        separation = 10.0
    else:
        separation = view/10.0

    rot = storedtarget.rot
    if rot == 360:
        rot = 0

    solar_system_ephemeris.set('jpl')
    # longitude, latitude, elevation of the astronomy centre
    longitude, latitude, elevation = observatory()
    astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    newtarget, backangle = _new_ra_dac(storedtarget.ra, storedtarget.dec, rot, separation)
    newra, newdec = Angle(newtarget.ra).deg, Angle(newtarget.dec).deg
    # rotate the diagram
    newrot = backangle - 180
    if newrot > 360:
        newrot = newrot-360
    if newrot < 0:
        newrot = newrot+360


    call_data['stored_values']['rot'] = newrot

    rahr, ramin, rasec, decsign, decdeg, decmin, decsec = _ra_dec_conversion(newra, newdec)

    call_data['stored_values']['target_dec'] = "{}{}d{}m{:2.1f}s".format(decsign, decdeg, decmin, decsec)
    call_data['stored_values']['target_ra'] = "{}h{}m{:2.1f}s".format(rahr, ramin, rasec)

    thisdate_time = storedtarget.target_datetime
    time = Time(thisdate_time.isoformat(sep=' '))
    newtarget_altaz = newtarget.transform_to(AltAz(obstime = time, location = astro_centre))
    call_data['stored_values']['target_alt'] = "{:3.2f}".format(newtarget_altaz.alt.degree)
    call_data['stored_values']['target_az'] = "{:3.2f}".format(newtarget_altaz.az.degree)

    call_data['stored_values']['back'] = 30104
    call_data['stored_values']['target_name'] = 'none'
    # now draw the chart
    _draw_finder(skicall)


def left_arrow(skicall):
    "Moves the finder chart left a bit"

    call_data = skicall.call_data

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    try:
        ra = Angle(storedtarget.ra).hms
        ra = ra.h * 360.0/24.0 + ra.m * 360.0/(24.0*60.0) +  ra.s * 360.0/(24.0*60.0*60.0)
        dec1 = Angle(storedtarget.dec).signed_dms
        dec = dec1.d + dec1.m/60.0 + dec1.s/3600.0
        if dec1.sign < 1:
            dec = -1 * dec
    except:
        raise FailPage("Invalid target data")

    try:
        view = float(storedtarget.view)
    except:
        view = 100.0

    if view > 100.0:
        separation = 10.0
    else:
        separation = view/10.0

    rot = storedtarget.rot
    if rot == 360:
        rot = 0

    solar_system_ephemeris.set('jpl')
    # longitude, latitude, elevation of the astronomy centre
    longitude, latitude, elevation = observatory()
    astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    if storedtarget.flip:
        newtarget, backangle = _new_ra_dac(storedtarget.ra, storedtarget.dec, rot-90, separation)
        newra, newdec = Angle(newtarget.ra).deg, Angle(newtarget.dec).deg
        # rotate the diagram
        newrot = backangle-90
    else:
        newtarget, backangle = _new_ra_dac(storedtarget.ra, storedtarget.dec, rot+90, separation)
        newra, newdec = Angle(newtarget.ra).deg, Angle(newtarget.dec).deg
        # rotate the diagram
        newrot = backangle+90

    if newrot<0:
        newrot = 360+newrot
    if newrot>360:
        newrot = newrot-360
    call_data['stored_values']['rot'] = newrot

    rahr, ramin, rasec, decsign, decdeg, decmin, decsec = _ra_dec_conversion(newra, newdec)

    call_data['stored_values']['target_dec'] = "{}{}d{}m{:2.1f}s".format(decsign, decdeg, decmin, decsec)
    call_data['stored_values']['target_ra'] = "{}h{}m{:2.1f}s".format(rahr, ramin, rasec)

    thisdate_time = storedtarget.target_datetime
    time = Time(thisdate_time.isoformat(sep=' '))
    newtarget_altaz = newtarget.transform_to(AltAz(obstime = time, location = astro_centre))
    call_data['stored_values']['target_alt'] = "{:3.2f}".format(newtarget_altaz.alt.degree)
    call_data['stored_values']['target_az'] = "{:3.2f}".format(newtarget_altaz.az.degree)

    call_data['stored_values']['back'] = 30104
    call_data['stored_values']['target_name'] = 'none'
    # now draw the chart
    _draw_finder(skicall)



def right_arrow(skicall):
    "Moves the finder chart right a bit"

    call_data = skicall.call_data

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    try:
        ra = Angle(storedtarget.ra).hms
        ra = ra.h * 360.0/24.0 + ra.m * 360.0/(24.0*60.0) +  ra.s * 360.0/(24.0*60.0*60.0)
        dec1 = Angle(storedtarget.dec).signed_dms
        dec = dec1.d + dec1.m/60.0 + dec1.s/3600.0
        if dec1.sign < 1:
            dec = -1 * dec
    except:
        raise FailPage("Invalid target data")

    try:
        view = float(storedtarget.view)
    except:
        view = 100.0

    if view > 100.0:
        separation = 10.0
    else:
        separation = view/10.0

    rot = storedtarget.rot
    if rot == 360:
        rot = 0

    solar_system_ephemeris.set('jpl')
    # longitude, latitude, elevation of the astronomy centre
    longitude, latitude, elevation = observatory()
    astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    if storedtarget.flip:
        newtarget, backangle = _new_ra_dac(storedtarget.ra, storedtarget.dec, rot+90, separation)
        newra, newdec = Angle(newtarget.ra).deg, Angle(newtarget.dec).deg
        # rotate the diagram
        newrot = backangle+90
    else:
        newtarget, backangle = _new_ra_dac(storedtarget.ra, storedtarget.dec, rot-90, separation)
        newra, newdec = Angle(newtarget.ra).deg, Angle(newtarget.dec).deg
        # rotate the diagram
        newrot = backangle-90

    if newrot<0:
        newrot = 360+newrot
    if newrot>360:
        newrot = newrot-360
    call_data['stored_values']['rot'] = newrot

    rahr, ramin, rasec, decsign, decdeg, decmin, decsec = _ra_dec_conversion(newra, newdec)

    call_data['stored_values']['target_dec'] = "{}{}d{}m{:2.1f}s".format(decsign, decdeg, decmin, decsec)
    call_data['stored_values']['target_ra'] = "{}h{}m{:2.1f}s".format(rahr, ramin, rasec)

    thisdate_time = storedtarget.target_datetime
    time = Time(thisdate_time.isoformat(sep=' '))
    newtarget_altaz = newtarget.transform_to(AltAz(obstime = time, location = astro_centre))
    call_data['stored_values']['target_alt'] = "{:3.2f}".format(newtarget_altaz.alt.degree)
    call_data['stored_values']['target_az'] = "{:3.2f}".format(newtarget_altaz.az.degree)

    call_data['stored_values']['back'] = 30104
    call_data['stored_values']['target_name'] = 'none'
    # now draw the chart
    _draw_finder(skicall)


def down_arrow(skicall):
    "Moves the finder chart down a bit"

    call_data = skicall.call_data

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    try:
        ra = Angle(storedtarget.ra).hms
        ra = ra.h * 360.0/24.0 + ra.m * 360.0/(24.0*60.0) +  ra.s * 360.0/(24.0*60.0*60.0)
        dec1 = Angle(storedtarget.dec).signed_dms
        dec = dec1.d + dec1.m/60.0 + dec1.s/3600.0
        if dec1.sign < 1:
            dec = -1 * dec
    except:
        raise FailPage("Invalid target data")

    try:
        view = float(storedtarget.view)
    except:
        view = 100.0

    if view > 100.0:
        separation = 10.0
    else:
        separation = view/10.0

    rot = storedtarget.rot
    if rot == 360:
        rot = 0

    solar_system_ephemeris.set('jpl')
    # longitude, latitude, elevation of the astronomy centre
    longitude, latitude, elevation = observatory()
    astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)

    newtarget, newrot = _new_ra_dac(storedtarget.ra, storedtarget.dec, rot+180, separation)
    newra, newdec = Angle(newtarget.ra).deg, Angle(newtarget.dec).deg

    # rotate the diagram
    call_data['stored_values']['rot'] = newrot

    rahr, ramin, rasec, decsign, decdeg, decmin, decsec = _ra_dec_conversion(newra, newdec)

    call_data['stored_values']['target_dec'] = "{}{}d{}m{:2.1f}s".format(decsign, decdeg, decmin, decsec)
    call_data['stored_values']['target_ra'] = "{}h{}m{:2.1f}s".format(rahr, ramin, rasec)

    thisdate_time = storedtarget.target_datetime
    time = Time(thisdate_time.isoformat(sep=' '))
    newtarget_altaz = newtarget.transform_to(AltAz(obstime = time, location = astro_centre))
    call_data['stored_values']['target_alt'] = "{:3.2f}".format(newtarget_altaz.alt.degree)
    call_data['stored_values']['target_az'] = "{:3.2f}".format(newtarget_altaz.az.degree)

    call_data['stored_values']['back'] = 30104
    call_data['stored_values']['target_name'] = 'none'
    # now draw the chart
    _draw_finder(skicall)



def _draw_finder(skicall):
    """Function to draw the finder chart from stored data"""
    call_data = skicall.call_data
    page_data = skicall.page_data

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    # hold the target parameters - this ensures stored data is saved to redis
    set_target_from_store(skicall)

    thisdate_time = storedtarget.target_datetime

    try:
        ra = Angle(storedtarget.ra).hms
        ra = ra.h * 360.0/24.0 + ra.m * 360.0/(24.0*60.0) +  ra.s * 360.0/(24.0*60.0*60.0)
        dec1 = Angle(storedtarget.dec).signed_dms
        dec = dec1.d + dec1.m/60.0 + dec1.s/3600.0
        if dec1.sign < 1:
            dec = -1 * dec
    except:
        raise FailPage("Invalid target data")

    try:
        view = float(storedtarget.view)
        page_data['view','input_text'] = storedtarget.view
    except:
        raise FailPage("Invalid view")

    header_text = 'Finder Chart for '
    target_name = storedtarget.target_name

    if target_name and (target_name != "none"):
        header_text += target_name + " "

    header_text += "RA: {} DEC: {} ALT: {} AZ: {}".format(storedtarget.ra, storedtarget.dec, storedtarget.alt, storedtarget.az)

    # set the transform on the widget
    page_data['starchart', 'transform'] = _transform(storedtarget.flip, storedtarget.rot)

    if view>10.0:
        page_data['starchart', 'lines'] = list(xy_constellation_lines(ra, dec, view))

    stars, scale, const = get_stars(ra, dec, view)
    planets = get_planets(thisdate_time, dec, view, scale, const)

    # convert stars ra, dec, to xy positions on the chart
    stars = list(radec_to_xy(stars, ra, dec, view))

    if planets:
        planets = list(radec_to_xy(planets, ra, dec, view))
        stars.extend(planets)
    if stars:
        page_data['starchart', 'stars'] = stars

    if call_data['json_requested']:
        # set header text into page_data, otherwise set it into call_data for the end_call function to sort out
        page_data['header', 'headpara', 'para_text'] = header_text
        return
 
    # not a json page, so set header text into call_data
    call_data['header_text'] = header_text

    if 'back' in skicall.call_data['stored_values']:
        # set back button to call correct page
        page_data['back', 'link_ident'] = int(skicall.call_data['stored_values']['back'])
        # and set the value to be stored
        skicall.call_data['set_values']['back_ident'] = skicall.call_data['stored_values']['back']




def print_finder(skicall):
    "Creates a printable finder chart"

    call_data = skicall.call_data
    page_data = skicall.page_data

    storedtarget = target_from_store(skicall)

    if not storedtarget:
        # no ident data
        raise FailPage("Target data unavailable")

    # parameters are obtained from stored data

    thisdate_time = storedtarget.target_datetime

    try:
        ra = Angle(storedtarget.ra).hms
        ra = ra.h * 360.0/24.0 + ra.m * 360.0/(24.0*60.0) +  ra.s * 360.0/(24.0*60.0*60.0)
        dec1 = Angle(storedtarget.dec).signed_dms
        dec = dec1.d + dec1.m/60.0 + dec1.s/3600.0
        if dec1.sign < 1:
            dec = -1 * dec
        target_time = Time(storedtarget.target_datetime, format='datetime', scale='utc')
        target_skyc = SkyCoord(Angle(storedtarget.ra), Angle(storedtarget.dec), frame='icrs')
        target_pg = target_skyc.transform_to(PrecessedGeocentric(obstime = target_time, equinox = target_time))
    except:
        raise FailPage("Invalid target data")

    try:
        view = float(storedtarget.view)
        if (view > 270.0) or (view < 0.0):
            view = 100.0
    except:
        raise FailPage("Invalid view")

    header_text = 'Finder Chart for '
    target_name = storedtarget.target_name

    if target_name and (target_name != "none"):
        header_text += target_name

    # longitude, latitude, elevation of the astronomy centre
    longitude, latitude, elevation = observatory()

    header_text += """:\nRight Ascension: {} (J2000)
Declination: {} (J2000)
Field of view: {:2.1f} degrees
Altitude: {} degrees
Azimuth: {} degrees
Right Ascension: {} (Precessed)
Declination: {} (Precessed)
Date: {} {}
Observatory
Longitude: {:2.3f} degrees
Latitude: {:2.3f} degrees
Elevation: {:2.1f} meters""".format(storedtarget.ra,
                                    storedtarget.dec,
                                    view,
                                    storedtarget.alt,
                                    storedtarget.az,
                                    target_pg.ra.to_string(unit='hourangle', precision=1, sep='hms'),
                                    target_pg.dec.to_string(unit=u.deg, precision=1, sep='dms'),
                                    storedtarget.str_date, storedtarget.str_time,
                                    longitude,
                                    latitude,
                                    elevation)

    page_data['details','para_text'] = header_text


    # set the transform
    page_data['starchart', 'transform'] = _transform(storedtarget.flip, storedtarget.rot)

    if view>10.0:
        page_data['starchart', 'lines'] = list(xy_constellation_lines(ra, dec, view))

    stars, scale, const = get_stars(ra, dec, view)
    planets = get_planets(thisdate_time, dec, view, scale, const)

    # convert stars ra, dec, to xy positions on the chart
    stars = list(radec_to_xy(stars, ra, dec, view))

    if planets:
        planets = list(radec_to_xy(planets, ra, dec, view))
        stars.extend(planets)
    if stars:
        page_data['starchart', 'stars'] = stars




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



def rotate_plus(skicall):
    """Rotates the chart by 30 degrees"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    storedtarget = target_from_store(skicall)
    rot = storedtarget.rot

    if storedtarget.flip:
        # Do the actual rotating
        rot -= 30
        if rot < 0:
            rot += 360
    else:
        # Do the actual rotating
        rot += 30
        if rot >= 360:
            rot -= 360

    # set the stored target in ident data
    set_target_from_store(skicall)

    skicall.call_data['set_values']['rot_ident'] = rot
    page_data['starchart', 'transform'] = _transform(storedtarget.flip, rot)

    if 'back' in skicall.call_data['stored_values']:
        # and set the value to be stored
        skicall.call_data['set_values']['back_ident'] = skicall.call_data['stored_values']['back']



def rotate_minus(skicall):
    """Rotates the chart by -30 degrees"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    storedtarget = target_from_store(skicall)
    rot = storedtarget.rot

    if storedtarget.flip:
        # Do the actual rotating
        rot += 30
        if rot >= 360:
            rot -= 360
    else:
        # Do the actual rotating
        rot -= 30
        if rot < 0:
            rot += 360

    # set the stored target in ident data
    set_target_from_store(skicall)

    skicall.call_data['set_values']['rot_ident'] = rot
    page_data['starchart', 'transform'] = _transform(storedtarget.flip, rot)

    if 'back' in skicall.call_data['stored_values']:
        # and set the value to be stored
        skicall.call_data['set_values']['back_ident'] = skicall.call_data['stored_values']['back']


def flip_v(skicall):
    """Flips the chart vertically - this is done with a horizontal flip plus 180 degree rotation"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    storedtarget = target_from_store(skicall)
    rot = storedtarget.rot
    flip = storedtarget.flip

    # Do the actual flipping
    if flip:
        flipv = False
    else:
        flipv = True

    rot += 180
    if rot >= 360:
        rot -= 360

    # set the stored target in ident data
    set_target_from_store(skicall)
    skicall.call_data['set_values']['flip_ident'] = flipv
    skicall.call_data['set_values']['rot_ident'] = rot

    page_data['starchart', 'transform'] = _transform(flipv, rot)

    if 'back' in skicall.call_data['stored_values']:
        # and set the value to be stored
        skicall.call_data['set_values']['back_ident'] = skicall.call_data['stored_values']['back']


def flip_h(skicall):
    """Flips the chart horizontally"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    storedtarget = target_from_store(skicall)
    flip = storedtarget.flip

    # Do the actual flipping
    if flip:
        fliph = False
    else:
        fliph = True

    # set the stored target in ident data
    set_target_from_store(skicall)
    skicall.call_data['set_values']['flip_ident'] = fliph

    page_data['starchart', 'transform'] = _transform(fliph, storedtarget.rot)

    if 'back' in skicall.call_data['stored_values']:
        # and set the value to be stored
        skicall.call_data['set_values']['back_ident'] = skicall.call_data['stored_values']['back']


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


def planets(skicall):
    "Fills in the planet positions page"

    if 'received_data' not in skicall.submit_dict:
        raise FailPage("Invalid session")

    planets = ("Mercury", "Venus", "Moon", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")

    try:
        # slot obtained from received_data or stored date
        if ('received_data' not in skicall.submit_dict) or (not skicall.submit_dict['received_data']):
            # get slot from stored data
            target = target_from_store(skicall)
            if not target:
                raise FailPage("Date for planets not found")
            dt = target.target_datetime
            slot = Slot.slot_from_time(dt.year, dt.month, dt.day, dt.hour, dt.minute)
        else:
            slot = _slot_from_received_data(skicall.submit_dict['received_data'])
    except:
        raise FailPage("time slot not found")

    midtime = slot.midtime.isoformat(sep=' ')
    skicall.page_data['timepara', 'para_text'] = "At %s" % (midtime,)

    try:
        con = sqlite3.connect(get_planetdb(), detect_types=sqlite3.PARSE_DECLTYPES)
        con.execute("PRAGMA foreign_keys = 1")
        cur = con.cursor()
    except:
        raise FailPage("Unable to open planets database")

    try:
        for seq in range(9):
            sectionseq = 'planetposition_%s' % (seq,)
            # gives planetposition_0, planetposition_1,...etc

            # The planet name as section header large text
            skicall.page_data[sectionseq, 'htext', 'large_text'] = planets[seq]

            # For this time and planet, read the database, and if the data is present, display it
            cur.execute('SELECT RA,DEC,ALT,AZ FROM POSITIONS WHERE DATEANDTIME=? AND NAME=?', (slot.midtime, planets[seq].lower()))
            planet_data = cur.fetchone()
            if not planet_data:
                skicall.page_data[sectionseq, 'ratext', 'tag_text'] = "RA: --"
                skicall.page_data[sectionseq, 'dectext', 'tag_text'] = "DEC: --"
                skicall.page_data[sectionseq, 'alttext', 'tag_text'] = "ALT: --"
                skicall.page_data[sectionseq, 'aztext', 'tag_text'] = "AZ: --"
                skicall.page_data[sectionseq, 'detail', 'show'] = False
                skicall.page_data[sectionseq, 'finder', 'show'] = False
            else:
                ra, dec, alt, az = planet_data
                rahr, ramin, rasec, decsign, decdeg, decmin, decsec = _ra_dec_conversion(ra, dec)
                ra = f"{rahr}h{ramin}m{rasec:.1f}s"
                dec =f"{decsign}{decdeg}d{decmin}m{decsec:.1f}s"
                alt =f"{alt:.2f}"
                az = f"{az:.2f}"
                skicall.page_data[sectionseq, 'ratext', 'tag_text'] = "RA: " + ra
                skicall.page_data[sectionseq, 'dectext', 'tag_text'] = "DEC: " + dec
                skicall.page_data[sectionseq, 'alttext', 'tag_text'] = "ALT: " + alt
                skicall.page_data[sectionseq, 'aztext', 'tag_text'] = "AZ: " + az
                skicall.page_data[sectionseq, 'detail', 'get_field1'] = f"{planets[seq]}:{ra}:{dec}:{alt}:{az}" 
                skicall.page_data[sectionseq, 'finder', 'get_field1'] = f"{planets[seq]}:{ra}:{dec}:{alt}:{az}"
    except:
        raise FailPage("Failure when reading planets database")
    finally:
        con.close()

    set_values = skicall.call_data['set_values']
    set_values['planning_date_ident'] = slot.startday_string()
    set_values['target_date_ident'] = slot.midtime.date().isoformat()
    set_values['target_time_ident'] = str(slot.starttime.hour) + ":30:00"



def session_planets(skicall):
    "accept a finder input field from session planets page, sets it into stored data, and call _draw_finder"

    stored_values = skicall.call_data['stored_values']

    if 'received_data' not in skicall.submit_dict:
        raise FailPage("Invalid planet")

    datadict = skicall.submit_dict['received_data']

    if len(datadict) != 1:
        raise FailPage("Invalid planet")

    for val in datadict.values():
        position = val

    try:
        splitposition = position.split(":")
        target_name = splitposition[0].lower()
        ra = Angle(splitposition[1]).hms
        dec = Angle(splitposition[2]).signed_dms
        stralt = splitposition[3]
        straz = splitposition[4]
        alt = float(stralt)
        az = float(straz)
    except:
        raise FailPage("Invalid position parameters")

    if (target_name not in _PLANETS) and ( target_name != 'moon'):
        # given target is not a planet, nor moon
        raise FailPage("Invalid planet")

    if alt>90.0 or alt<-90.0:
        raise FailPage("Invalid Altitude")
    if az>360.0 or az<0.0:
        raise FailPage("Invalid Azimuth")

    stored_values['target_name'] = splitposition[0]
    stored_values['target_ra'] = splitposition[1]
    stored_values['target_dec'] = splitposition[2]
    stored_values['target_alt'] = stralt
    stored_values['target_az'] = straz
    stored_values['view'] = "100.0"
    stored_values['back'] = "30201"  # set back button to planets page

    # now draw the chart
    _draw_finder(skicall)


def _slot_from_received_data(received_data):
    "Returns slot"
    # Check received data
    if not received_data:
        raise FailPage("Invalid data")
    # received data should be a dictionary with one element
    received_item = list(received_data.items())
    # received_item is [(key,value)]
    if len(received_item) != 1:
        raise FailPage("Invalid data")
    widgfield,startday_string = received_item[0]
    if len(widgfield) != 3:
        raise FailPage("Invalid data")
    if (widgfield[1] != 'planets'):
        raise FailPage("Invalid data")
    if widgfield[2] != 'get_field1':
        raise FailPage("Invalid data")
    string_sequence = widgfield[0].split('_')[-1]
    try:
        sequence = int(string_sequence)
    except:
        raise FailPage("Invalid data")
    if sequence < 2 or sequence > 21:
        raise FailPage("Invalid data")

    # so sequence is sorted
    # now startday
    try:
        startcomponents = [int(i) for i in startday_string.split('-')]
    except:
        raise FailPage("Invalid date")
    if len(startcomponents) != 3:
        raise FailPage("Invalid date")
    year,month,day = startcomponents

    today = datetime.utcnow().date()

    if not ((year == today.year) or (year == today.year + 1)  or (year == today.year - 1)):
        raise FailPage("Invalid date")
    try:
        startday = date(year, month, day)
    except:
        raise FailPage("Invalid date")

    return Slot(startday, sequence)






