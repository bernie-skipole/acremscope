
"""This script is edited as required to search an entry in the database where
   a suspected spurios star is found
"""


import sqlite3


# database HP48.db has stars to magnitude 6, organised in 48 healpix pixels
_HP48 = "dbases/HP48.db"

# database HP192.db has stars to magnitude 9, organised in 192 healpix pixels
_HP192 = "dbases/HP192.db"

# database HP768.db has all stars, organised in 768 healpix pixels
_HP768 = "dbases/HP768.db"


ramin = 54.2400000 - 0.05

ramax =54.2400000 + 0.05

decmin = -28.1349166 - 0.05

decmax = -28.1349166 + 0.05

try:
    con = sqlite3.connect(_HP48, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = con.cursor()
    cur.execute( f"select * from stars where RA>{ramin} and RA<{ramax} and DEC>{decmin} and DEC<{decmax}" )
    result = cur.fetchall()
finally:
    con.close()



print(result)

# (HP INTEGER, GSC_ID TEXT, RA REAL, DEC REAL, MAG REAL)
# (35, '0645301224', 54.235119999999995, -28.137719999999998, 0.05)


# and this can be deleted with
# cur.execute("DELETE FROM stars WHERE GSC_ID=?", ('0645301224',))
# con.commit()

