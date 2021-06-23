#!/home/bernard/makecat/bin/python3

"""
Once the gsc files have been downloaded from https://cdsarc.unistra.fr/viz-bin/cat/I/254
this python script can read through them and will create the following sqlite databases:

HP48.db - stars to magnitude 6
HP192.db - stars to magnitude 9
HP768.db - all stars

Each database has a single table 'stars" with columns (HP INTEGER, GSC_ID TEXT, RA REAL, DEC REAL, MAG REAL)

The GSC_ID is not used by my chart, but is saved should there be a future need
to cross-reference a star on the chart with the source material.

HP is the healpix index containing the star
"""


####
# notes, this script need an number of packages, available from pypi
#
# under /home/bernard I created 
#
# python3 -m venv ~/makecat
#
# activated it, and then

# pip install bitstring
# pip install astropy
# pip install astropy_healpix
#
# if you locate your virtual environment elsewhere, you will
# have to change the top shebang line of this script
#

import os, sys, sqlite3

from bitstring import ConstBitStream

from astropy_healpix import HEALPix
from astropy.coordinates import ICRS, SkyCoord
from astropy import units as u
import numpy


# HEALPix object with nside 2 and 48 pixels
hp48 = HEALPix(nside=numpy.int64(2), order='nested', frame=ICRS())

# HEALPix object with nside 4 and 192 pixels
hp192 = HEALPix(nside=numpy.int64(4), order='nested', frame=ICRS())

# HEALPix object with nside 8 and 768 pixels
hp768 = HEALPix(nside=numpy.int64(8), order='nested', frame=ICRS())



def read_gsc_file(filepath):
    "Generator which reads the given file, and yields (GSC_ID, RA, DEC, magnitude) for each star"


    # Each file starts with ascii header
    #
    #	 size of header 3 bytes
    #	 encoding version 2
    #	 region no.					
    #	 number of records
    #	 offset ra
    #	 ra - max;
    #	 offset dec
    #	 dec - max
    #	 offset mag
    #	 scale ra
    #	 scale dec
    #	 scale position error;
    #    scale_magnitude
    #    no. of plates
    #    plate list
    #    epoch-list


    # First read header length, get scaling factor and offsets


    with open(filepath, "rb") as fp:
       # the first three ascii characters of the header are the header length
       # we need this to start reading each field after the header
       # so get the headerlength as an integer
       headerlength = int(fp.read(3).decode(encoding="ascii"))
       header = fp.read(headerlength - 3).decode(encoding="ascii")
       # remove any start and end spaces
       header = header.strip()
       # split the header
       headerfields = header.split(" ")
       # print(headerfields)

       region = headerfields[1]

       offset_ra = float(headerfields[3])
       offset_dec = float(headerfields[5])
       offset_mag = float(headerfields[7])
       scale_ra = float(headerfields[8])
       scale_dec = float(headerfields[9])
       scale_magnitude = float(headerfields[11])

       # after the header, read each star record, which is 12 bytes
       # and split into binary areas

       # some stars have multiple entries, ensure only the first is recorded
       last_id = ''

       while True:
           star_record = fp.read(12)
           if star_record == b'':
               break
           s = ConstBitStream(star_record)
           topspare = s.read('bin:1')
           GSC_ID = s.read('uint:14')

           if last_id == GSC_ID:
               # A record with this id has been read, skip it
               continue
           last_id = GSC_ID

           RA = s.read('uint:22')
           DEC = s.read('uint:19')
           pos_error = s.read('uint:9')
           mag_error = s.read('uint:7')
           magnitude = s.read('uint:11')
           mag_band = s.read('uint:4')
           class_ = s.read('uint:3')
           plate_id = s.read('uint:4')
           multiple = s.read('uint:1')
           spare = s.read('bin:1')

           # some spurious??? records have magnitude 0, since this is unlikely to be an actual star
           # skip them
           if magnitude == 0:
               continue

           # The full GSC_ID is 5 digit region, with five digit star number
           GSC_ID = f"{region}{GSC_ID:05}"

           RA = offset_ra + RA/scale_ra
           DEC = offset_dec + DEC/scale_dec
           magnitude = offset_mag + magnitude/scale_magnitude

           if RA > 360:
               RA = RA - 360
           if RA < 0:
               RA = RA + 360

           yield (GSC_ID, RA, DEC, magnitude)



def gsc_files(path):
    "Generator which returns paths to all gsc files ending in .GSC"
    for root,d_names,f_names in os.walk(path):
        for f in f_names:
            if f.endswith(".GSC"):
                yield os.path.join(root, f)


def create_databases(starcatalogs):
    "starcatalogs is the directory where they are to be made"

    dbpaths = {}          # will hold the path to each database

    # this dictionary will have database names as key (without the .db file extension)
    # and database paths as values

    # database HP48.db has stars to magnitude 6, organised in 48 healpix pixels
    dbpaths["HP48"] = os.path.join(starcatalogs, "HP48.db")

    # database HP192.db has stars to magnitude 9, organised in 192 healpix pixels
    dbpaths["HP192"] = os.path.join(starcatalogs, "HP192.db")

    # database HP768.db has all stars, organised in 768 healpix pixels
    dbpaths["HP768"] = os.path.join(starcatalogs, "HP768.db")

    # for every name in dbpaths
    # create the database

    for path in dbpaths.values():
        con = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        con.execute("create table stars (HP INTEGER, GSC_ID TEXT, RA REAL, DEC REAL, MAG REAL)")
        con.execute("create index HP_IDX  on stars(HP)")
        con.execute("create index MAG_IDX on stars(MAG)")
        con.commit()
        con.close()

    return dbpaths



def add_record(gsc_id, ra, dec, mag):
    """Given a star record defined by gsc_id, ra, dec, mag
       Returns a list of database names and healpix pixel id's which contain this star
       so the star can be added to each database together with the id for that database
    """
    # for the given star, return the names of the databases it is to be added to
    # and the hp number in each database

    # HP48.db - stars to magnitude 6
    # HP192.db - stars to magnitude 9
    # HP768.db - all stars

    # a list of lists will be returned; [[dbasename, hp index],....]

    # Example: the healpix index in the global hp48 HEALPix object
    # can be found using
    # hp48.skycoord_to_healpix(coords)
    # where coords is the SkyCoord object for the star
    # the index is converted to a Python integer, since the method
    # returns a numpy integer

    coords = SkyCoord(ra=ra*u.deg, dec=dec*u.deg)

    recordbases = []

    if mag < 6:
        recordbases.append(["HP48", int(hp48.skycoord_to_healpix(coords))])

    if mag < 9:
        recordbases.append(["HP192", int(hp192.skycoord_to_healpix(coords))])

    recordbases.append(["HP768", int(hp768.skycoord_to_healpix(coords))])


    return recordbases



if __name__ == "__main__":

    # create databases
    dbpaths = create_databases("dbases")

    # dbases is the directory where the databases will be created, and must exist
    # dpaths is database name to path dictionary

    directory = "cdsarc.u-strasbg.fr/pub/cats/I/254/GSC"

    # the directory on your PC containing gsc 1.2 files

    # note this directory was created on my own machine from https://cdsarc.unistra.fr/viz-bin/cat/I/254
    # after loading the catalogs with the command:

    # wget -r ftp://anonymous:<myemail>@cdsarc.u-strasbg.fr/pub/cats/I/254/GSC/

    # set your own email address instead of <myemail> in the line above
    # use the special escape string of %40 instead of the @ character in the email address
    # expect the download to take some time (an hour)

    # The following builds sqlite databases in the directory "dbases", printing out each
    # filepath from the catalogue as it is read. This will take a long time, several hours.

    for filepath in gsc_files(directory):
        connections = {}
        for star in read_gsc_file(filepath):
            # star = GSC_ID, RA, DEC, magnitude
            # get the database names and hp number which should have this record inserted
            recordbases = add_record(*star)
            for name, hp in recordbases:
                if name not in connections:
                    path =  dbpaths[name]
                    connections[name] = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
                connections[name].execute("insert into stars values (?, ?, ?, ?, ?)", (hp, *star))
        # commit and close the database connections after reading this file
        for con in connections.values():
            con.commit()
            con.close()
        # print filepath so you can see something
        print(filepath)
        # then repeats for the next file until all files read




