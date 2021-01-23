#!/usr/bin/python3


"""temperaturedriver.py

Gets temperature from the pi sensor, and sends it at regular intervals

Initially, this is a simulator, using metoffice data

"""

import os, sys, collections, asyncio

import urllib.request, json     # required for met office communications

import xml.etree.ElementTree as ET

from datetime import datetime

# All xml data received on the port from the client should be contained in one of the following tags
TAGS = (b'getProperties',
  #      b'newTextVector',
  #      b'newNumberVector',
  #      b'newSwitchVector',
  #      b'newBLOBVector'
       )

# _STARTTAGS is a tuple of ( b'<newTextVector', ...  ) data received will be tested to start with such a starttag
_STARTTAGS = tuple(b'<' + tag for tag in TAGS)

# _ENDTAGS is a tuple of ( b'</newTextVector>', ...  ) data received will be tested to end with such an endtag
_ENDTAGS = tuple(b'</' + tag + b'>' for tag in TAGS)


_DEVICE = 'Rempi01 Temperature'
_NAME = 'Temperature'
_ELEMENT = 'Temperature'

_MET_OFFICE_KEY = 'XXXXXXXXXXXXXXXXXX'


def driver():
    "Blocking call"

    # now start eventloop to read and write to stdin, stdout
    loop = asyncio.get_event_loop()

    connections = _TEMPERATURE(loop)

    while True:
        try:
            loop.run_until_complete(connections.handle_data())
        except Exception as e:
            raise
            print("An exception has occurred")
        finally:
            loop.close()


class _TEMPERATURE:

    def __init__(self, loop):
        "Sets the data used by the data handler"
        self.loop = loop
        self.sender = collections.deque(maxlen=100)
        # start with zero values, which should be immediately overwritten
        self.temperature, self.timestamp = hardwaretemperature("0.0", datetime.utcnow().isoformat(sep='T'))


    async def handle_data(self):
        """handle data via stdin and stdout"""
        reader = asyncio.StreamReader(loop=self.loop)
        reader_protocol = asyncio.StreamReaderProtocol(reader, loop=self.loop)
        await self.loop.connect_read_pipe( lambda: reader_protocol, sys.stdin)

        writer_transport, writer_protocol = await self.loop.connect_write_pipe(
                                                       lambda: asyncio.Protocol(),
                                                       sys.stdout)
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, self.loop)


        await asyncio.gather(self.reader(reader), self.writer(writer), self.update())


    async def update(self):
        """Gets an updated temperature, and creates a setNumberVector placing it into self.sender for transmission"""
        # Send every ten minutes
        while True:            
            await asyncio.sleep(600)
            self.temperature, self.timestamp = await self.loop.run_in_executor(None, self.setNumberVector)



    async def writer(self, writer):
        """Writes data in sender to stdout writer"""
        while True:
            if self.sender:
                # add a new line to help if the software receiving this is line bufferred
                writer.write(self.sender.popleft() + b"\n")
            else:
                # no message to send, do an async pause
                await asyncio.sleep(0.5)


    async def reader(self, reader):
        """Reads data from stdin reader which is the input stream of the driver
           if a getProperties is received (only entry in TAGS), then puts a
           defNumberVector into self.sender"""
        # get received data, and put it into message
        message = b''
        messagetagnumber = None
        while True:
            # get blocks of data
            try:
                data = await reader.readuntil(separator=b'>')
            except asyncio.LimitOverrunError:
                data = await reader.read(n=32000)
            if not message:
                # data is expected to start with <tag, first strip any newlines
                data = data.strip()
                for index, st in enumerate(_STARTTAGS):
                    if data.startswith(st):
                        messagetagnumber = index
                        break
                else:
                    # data does not start with a recognised tag, so ignore it
                    # and continue waiting for a valid message start
                    continue
                # set this data into the received message
                message = data
                # either further children of this tag are coming, or maybe its a single tag ending in "/>"
                if message.endswith(b'/>'):
                    # the message is complete, handle message here
                    # Run 'fromindi.receive_from_indiserver' in the default loop's executor:
                    try:
                        root = ET.fromstring(message.decode("utf-8"))
                    except Exception:
                        # possible malformed
                        message = b''
                        messagetagnumber = None
                        continue
                    ########## does not measure temperature, just gets last measured value,
                    # and sets xml into the sender deque
                    self.defnumbervector(root)

                    # and start again, waiting for a new message
                    message = b''
                    messagetagnumber = None
                # and read either the next message, or the children of this tag
                continue
            # To reach this point, the message is in progress, with a messagetagnumber set
            # keep adding the received data to message, until an endtag is reached
            message += data
            if message.endswith(_ENDTAGS[messagetagnumber]):
                # the message is complete, handle message here
                # Run 'fromindi.receive_from_indiserver' in the default loop's executor:
                try:
                    root = ET.fromstring(message.decode("utf-8"))
                except Exception:
                    # possible malformed
                    message = b''
                    messagetagnumber = None
                    continue
                ########## does not measure temperature, just gets last measured value,
                # and sets xml into the sender deque
                self.defnumbervector(root)

                # and start again, waiting for a new message
                message = b''
                messagetagnumber = None

    def defnumbervector(self, root):
        """Responds to a getProperties, and sets temperature defNumberVector in the sender deque.
           Returns None"""

        if root.tag == "getProperties":

            # expecting something like
            # <getProperties version="1.7" device="Rempi01 Temperature" name="Temperature" />

            version = root.get("version")
            if version != "1.7":
                return

            device = root.get("device")
            # device must be None (for all devices), or value of _DEVICE
            if (not (device is None)) and (device != _DEVICE):
                # not a recognised device
                return

            name = root.get("name")
            # name must be None (for all properties), or value of _NAME which is the only property
            # of this device
            if (not (name is None)) and (name != _NAME):
                # not a recognised property
                return

            # create the responce
            xmldata = ET.Element('defNumberVector')
            xmldata.set("device", _DEVICE)
            xmldata.set("name", _NAME)
            xmldata.set("label", "Temperature (Centigrade)")
            xmldata.set("group", "Status")
            xmldata.set("state", "Ok")
            xmldata.set("perm", "ro")
            xmldata.set("timestamp", self.timestamp)

            ne = ET.Element('defNumber')
            ne.set("name", _ELEMENT)
            ne.set("format", "%.1f")
            ne.set("min", "-30")
            ne.set("max", "-30")   # min== max means ignore
            ne.set("step", "0")    # 0 means ignore
            ne.text = self.temperature
            xmldata.append(ne)
        else:
            # tag not recognised, do not add anything to sender
            return

        # appends the xml data to be sent to the sender deque object
        self.sender.append(ET.tostring(xmldata))
        return


    def setNumberVector(self):
        """Sets temperature setNumberVector in the sender deque.
           Returns new temperature, timestamp"""
        temperature, timestamp = hardwaretemperature(self.temperature, self.timestamp)
        # create the setNumberVector
        xmldata = ET.Element('setNumberVector')
        xmldata.set("device", _DEVICE)
        xmldata.set("name", _NAME)
        xmldata.set("timestamp", timestamp)
        xmldata.set("message", f"{datetime.utcnow().isoformat(sep='T')} [INFO] Temperature {temperature} Centigrade received")
        ne = ET.Element('oneNumber')
        ne.set("name", _ELEMENT)
        ne.text = temperature
        xmldata.append(ne)

        # appends the xml data to be sent to the sender deque object
        self.sender.append(ET.tostring(xmldata))
        return temperature, timestamp


def hardwaretemperature(temperature, timestamp):
    """temperature is the current temperature, gets a new value from hardware and returns it
       with an updated timestamp. Both temperature and timestamp are strings
       If a temperature cannot be found, returns the old temperature and timestamp"""
    # Eventually this will use hardware, currently just use the met office
    try:

        # get a list of available timestamps, and choose the latest (last in list)
        url = f'http://datapoint.metoffice.gov.uk/public/data/val/wxobs/all/json/capabilities?res=hourly&key={_MET_OFFICE_KEY}'

        with urllib.request.urlopen(url) as response:
           values = json.loads(response.read())

        # get the last timestemp
        latest_time = values["Resource"]['TimeSteps']["TS"][-1]

        # remove the TZ info
        actimestring = latest_time[:-4]
        if actimestring == timestamp:
            # no new time temperature is available 
            return temperature, timestamp

        # 3344 = location id for Bingley Samos
        url = f'http://datapoint.metoffice.gov.uk/public/data/val/wxobs/all/json/3344?res=hourly&time={latest_time}&key={_MET_OFFICE_KEY}'
        with urllib.request.urlopen(url) as response:
           values = json.loads(response.read())
        temperature1 = values['SiteRep']['DV']['Location']['Period']['Rep']['T']

        # 99060 = location id for Stonyhurst
        url = f'http://datapoint.metoffice.gov.uk/public/data/val/wxobs/all/json/99060?res=hourly&time={latest_time}&key={_MET_OFFICE_KEY}'
        with urllib.request.urlopen(url) as response:
           values = json.loads(response.read())
        temperature2 = values['SiteRep']['DV']['Location']['Period']['Rep']['T']

        # temperature at the Astronomy Centre is estimated as the average of these two,
        # minus a quarter of a degree due to its height.

        actemp = (float(temperature1) + float(temperature2))/2.0 - 0.25
        actempstring = "%.1f" % actemp

    except Exception:
        # some failure occurred getting the temperature
        return temperature, timestamp

    return actempstring, actimestring







if __name__=="__main__":

    # start this blocking call
    driver()

