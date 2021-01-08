#!/home/bernard/catalog/bitenv/bin/python3

"""
Once the gsc files have been downloaded from https://cdsarc.unistra.fr/viz-bin/cat/I/254
this python script can read through them and will create the following sqlite databases:

CAT6.db - stars to magnitude 6
CAT9.db - stars to magnitude 9

CAT14_P90.db - covers declination 50 to 90
CAT14_P60.db - covers declination 20 to 60
CAT14_P30.db - covers declination -10 to 30
CAT14_M90.db - covers declination -50 to -90
CAT14_M60.db - covers declination -20 to -60
CAT14_M30.db - covers declination 10 to -30

Note, as these have overlapping areas, stars can appear in more than one database

Each database has a single table 'stars" with columns (GSC_ID TEXT, RA REAL, DEC REAL, MAG REAL)

The GSC_ID is not used by my chart, but is saved should there be a future need
to cross-reference a star on the chart with the source material.
"""


####
# notes, this script need the package bitstring, available from pypi
#
# under /home/bernard/catalog I created 
#
# python3 -m venv bitenv
#
# activated it, and then python3 -m pip install bitstring
#
# if you locate your virtual environment elsewhere, you will
# have to change the top shebang line of this script
#

import os, sys, sqlite3

from bitstring import ConstBitStream



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

    # each dictionary has the database name as key (without the .db file extension)

    # database cat6.db has stars to magnitude 6
    dbpaths["CAT6"] = os.path.join(starcatalogs, "CAT6.db")

    # database cat9.db has stars to magnitude 9
    dbpaths["CAT9"] = os.path.join(starcatalogs, "CAT9.db")

    # These are a set of databases containing all stars
    dbpaths["CAT14_P90"] = os.path.join(starcatalogs, "CAT14_P90.db")  # covers declination 50 to 90
    dbpaths["CAT14_P60"] = os.path.join(starcatalogs, "CAT14_P60.db")  # covers declination 20 to 60
    dbpaths["CAT14_P30"] = os.path.join(starcatalogs, "CAT14_P30.db")  # covers declination -10 to 30
    dbpaths["CAT14_M90"] = os.path.join(starcatalogs, "CAT14_M90.db")  # covers declination -50 to -90
    dbpaths["CAT14_M60"] = os.path.join(starcatalogs, "CAT14_M60.db")  # covers declination -20 to -60
    dbpaths["CAT14_M30"] = os.path.join(starcatalogs, "CAT14_M30.db")  # covers declination 10 to -30

    # for every name in dbpaths
    # create the database

    for path in dbpaths.values():
        con = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        con.execute("create table stars (GSC_ID TEXT, RA REAL, DEC REAL, MAG REAL)")
        con.execute("create index RA_IDX  on stars(RA)")
        con.execute("create index DEC_IDX on stars(DEC)")
        con.execute("create index MAG_IDX on stars(MAG)")
        con.commit()
        con.close()

    return dbpaths



def add_record(gsc_id, ra, dec, mag):
    """Returns a set of database names which should have this record inserted
       gsc_id, ra, dec, mag are the star parameters to add
"""
    # for the given star, set the names of the database it is to be added to in this set
    # the record can be added to more than one database, as they overlap
    dbnames = set()
    if mag < 6:
        dbnames.add("CAT6")
    if mag < 9:
        dbnames.add("CAT9")

    if dec > 50:
        dbnames.add("CAT14_P90")    # covers declination 50 to 90
    if 20 < dec < 60:
        dbnames.add("CAT14_P60")
    if -10 < dec < 30:
        dbnames.add("CAT14_P30")
    if -30 < dec < 10:
        dbnames.add("CAT14_M30")
    if -60 < dec < -20:
        dbnames.add("CAT14_M60")
    if dec < -50:
        dbnames.add("CAT14_M90")
    return dbnames



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
        for record in read_gsc_file(filepath):
            # record = GSC_ID, RA, DEC, magnitude
            # get the database names which should have this record inserted
            recordbases = add_record(*record)
            for name in recordbases:
                if name not in connections:
                    path =  dbpaths[name]
                    connections[name] = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
                connections[name].execute("insert into stars values (?, ?, ?, ?)", record)
        # commit and close the database connections after reading this file
        for con in connections.values():
            con.commit()
            con.close()
        # print filepath so you can see something happenning
        print(filepath)
        # then repeats for the next file until all files read




