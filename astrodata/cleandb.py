
"""This script deletes spurious items
"""

import sqlite3

# database HP48.db has stars to magnitude 6, organised in 48 healpix pixels
_HP48 = "dbases/HP48.db"

# database HP192.db has stars to magnitude 9, organised in 192 healpix pixels
_HP192 = "dbases/HP192.db"

# database HP768.db has all stars, organised in 768 healpix pixels
_HP768 = "dbases/HP768.db"

items = ['0645301224']

try:
    con = sqlite3.connect(_HP48, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = con.cursor()
    for gsc_id in items:
        cur.execute("DELETE FROM stars WHERE GSC_ID=?", (gsc_id,))
    con.commit()
finally:
    con.close()

try:
    con = sqlite3.connect(_HP192, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = con.cursor()
    for gsc_id in items:
        cur.execute("DELETE FROM stars WHERE GSC_ID=?", (gsc_id,))
    con.commit()
finally:
    con.close()

try:
    con = sqlite3.connect(_HP768, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = con.cursor()
    for gsc_id in items:
        cur.execute("DELETE FROM stars WHERE GSC_ID=?", (gsc_id,))
    con.commit()
finally:
    con.close()




