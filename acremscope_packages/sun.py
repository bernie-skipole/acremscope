


from datetime import date, timedelta, datetime, timezone
from functools import lru_cache

from astropy.coordinates import EarthLocation
from astropy.time import Time

from astroplan import Observer

from .cfg import observatory


def sunrise(date_object):
    "Given a date object, returns sunrise time as (hour, minute)"
    t = suntime(date_object.day, date_object.month, date_object.year, rise=True)
    thour = int(t)
    tmin =  (t - thour) * 60
    return thour, tmin

def sunrisetoday():
    "Returns sunrise time today as (hour, minute)"
    return sunrise(datetime.now(timezone.utc).date())

def sunrisetomorrow():
    "Returns sunrise time tomorrow as (hour, minute)"
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    return sunrise(tomorrow)

def sunset(date_object):
    "Given a date object, returns sunset time as (hour, minute)"
    t = suntime(date_object.day, date_object.month, date_object.year, rise=False)
    thour = int(t)
    tmin =  (t - thour) * 60
    return thour, tmin

def sunsettoday():
    "Returns sunset time today as (hour, minute)"
    return sunset(datetime.now(timezone.utc).date())

def sunsettomorrow():
    "Returns sunset time tomorrow as (hour, minute)"
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    return sunset(tomorrow)

@lru_cache(maxsize=32)
def suntime(day, month, year, rise=True):
    """Given day month year, if rise is True returns sunrise time, if False return sunset time
          For the todmorden astronomy centre"""

    longitude, latitude, elevation = observatory()
    astro_centre = EarthLocation.from_geodetic(longitude, latitude, elevation)
    centre_observer = Observer(location=astro_centre, name="centre_observer", timezone="utc")

    if rise:
        # get sunrise to the nearest time of 5:00 am
        thedate = datetime(year, month, day, hour=5, tzinfo=timezone.utc)
        astrotime = Time(thedate, format='datetime', scale='utc')
        sun_rise = centre_observer.sun_rise_time(astrotime, which="nearest")
        sun_rise.format = 'datetime'
        return sun_rise.value.hour + sun_rise.value.minute/60.0 + sun_rise.value.second/360.0
    else:
        # get sunset to the nearest time of 19:00 pm
        thedate = datetime(year, month, day, hour=19, tzinfo=timezone.utc)
        astrotime = Time(thedate, format='datetime', scale='utc')
        sun_set = centre_observer.sun_set_time(astrotime, which="nearest")
        sun_set.format = 'datetime'
        return sun_set.value.hour + sun_set.value.minute/60.0 + sun_set.value.second/360.0


class Slot(object):

    @classmethod
    def slot_from_time(cls, year, month, day, hour=0, minute=0, second=0):
        "Return a slot for the given day and time"
        dt = datetime(year, month, day, hour, minute, second)
        this_hour = dt.hour
        if this_hour > 12:
            return cls(dt.date(), this_hour-12)
        # startday is the previous day
        prev_day = dt - timedelta(days=1)
        return cls(prev_day.date(), this_hour+12)


    @classmethod
    def now(cls):
        "Return a Slot for the current date and time"
        dt = datetime.now(timezone.utc)
        this_hour = dt.hour
        if this_hour > 12:
            return cls(dt.date(), this_hour-12)
        # startday is the previous day
        prev_day = dt - timedelta(days=1)
        return cls(prev_day.date(), this_hour+12)


    def __init__(self, startday, sequence):
        "startday is a date object"
        self.startday = startday
        self.nextday = startday + timedelta(days=1)
        # The night viewing time
        self.set = int( suntime(startday.day, startday.month, startday.year, rise=False) ) + 1  # +1 to round up
        self.rise = int( suntime(self.nextday.day, self.nextday.month, self.nextday.year, rise=True) ) # auto rounds down
        # sequence 0 is 12 mid day of startday
        # sequence 12 is midnight, or hour zero of nextday
        # sequence 23 is 11 am of nextday
        self.sequence = sequence
        if sequence < 12:
            self.starttime = datetime(startday.year, startday.month, startday.day, hour=sequence+12)
        else:
            self.starttime = datetime(self.nextday.year, self.nextday.month, self.nextday.day, hour=sequence-12)
        if sequence < 11:
            self.endtime = datetime(startday.year, startday.month, startday.day, hour=sequence+13)
        else:
            self.endtime = datetime(self.nextday.year, self.nextday.month, self.nextday.day, hour=sequence-11)

    def __str__(self):
        return str(self.starttime.hour) + ":00 - " + str(self.endtime.hour) + ":00"

    def __repr__(self):
        return __class__.__name__ +"(" + self.startday_string() + "," + str(self.sequence) + ")"

    def startday_string(self):
        return self.startday.isoformat()

    @property
    def midtime(self):
        "Returns start time of slot plus 30 minutes"
        return self.starttime + timedelta(minutes=30)

    def ten_min_times(self):
        "Returns list of seven datetimes, from starttime to endtime, at ten minute intervals"
        time_list =  []
        for n in range(0, 70, 10):
            if n == 0:
                time_list.append(self.starttime)
            else:
                time_list.append(self.starttime + timedelta(minutes=n))
        return time_list

    def in_daylight(self):
        if (self.starttime.hour > 12) and (self.starttime.hour < self.set):   # evening and earlier than set time
            return True
        if (self.endtime.hour < 12) and (self.endtime.hour > self.rise):      # morning and later than rise time
            return True
        return False


def this_slot(this_time):
    "Returns a slot object for this_time, which should be a datetime object"
    this_hour = this_time.hour
    if this_hour > 12:
        return Slot(this_time.date(), this_hour-12)
    # startday is the previous day
    prev_day = this_time - timedelta(days=1)
    return Slot(prev_day.date(), this_hour+12)


def next_slot(this_time):
    "Returns a slot object for the next hour after this_time, which is a datetime object"
    next_time = this_time + timedelta(hours=1)
    return this_slot(next_time)
 

def twoday_slots(fromdate = None):
    "Create two lists, equal length, for tonights slots and tomorrow night slots"
    if fromdate is None:
        today = datetime.now(timezone.utc).date()
    else:
        today = fromdate
    tomorrow = today + timedelta(days=1)
    dayafter = today + timedelta(days=2)

    # night one
    one_set = int( suntime(today.day, today.month, today.year, rise=False) )
    one_rise = int( suntime(tomorrow.day, tomorrow.month, tomorrow.year, rise=True) )

    # night two
    two_set = int( suntime(tomorrow.day, tomorrow.month, tomorrow.year, rise=False) )
    two_rise = int( suntime(dayafter.day, dayafter.month, dayafter.year, rise=True) )

    # table start and end hours
    table_start = min(one_set, two_set) + 1  # +1 for observing to start in the hour after sunset
    table_end = max(one_rise, two_rise) - 1  # -1 for observing to end in the hour before sunrise

    night0 = []
    night1 = []

    for seq in range(0, 12):
        if (seq+12) < table_start:
            continue
        night0.append(Slot(today,seq))
        night1.append(Slot(tomorrow,seq))

    for seq in range(12, 24):
        if (seq-12) > table_end:
            continue
        night0.append(Slot(today,seq))
        night1.append(Slot(tomorrow,seq))

    return night0, night1



def night_slots(thisdate = None):
    "Create a list of Slots for this nights slots"
    if thisdate is None:
        today = datetime.now(timezone.utc).date()
    else:
        today = thisdate
    tomorrow = today + timedelta(days=1)

    # night one
    sun_set = int( suntime(today.day, today.month, today.year, rise=False) )
    sun_rise = int( suntime(tomorrow.day, tomorrow.month, tomorrow.year, rise=True) )

    # list start and end hours
    list_start = sun_set + 1  # +1 for observing to start in the hour after sunset
    list_end = sun_rise - 1  # -1 for observing to end in the hour before sunrise

    night = []

    for seq in range(0, 12):
        if (seq+12) < list_start:
            continue
        night.append(Slot(today,seq))

    for seq in range(12, 24):
        if (seq-12) > list_end:
            continue
        night.append(Slot(today,seq))

    return night

