"""
Module to create and query the members sqlite database

"""


import os, psycopg2, hashlib, random, shutil

from datetime import datetime, timedelta

from skipole import ServerError

# This is the default admin username
_USERNAME = "admin"
# This is the default  admin password
_PASSWORD = "password"
# This is the default  admin PIN
_PIN = "1234"

# characters used in generated passwords - letters avoiding 0, O, 1, l, I, i, j, S, 5
_CHARS = "abcdefghkmnpqrstuvwxyzABCDEFGHJKLMNPQRTUVWXYZ2346789"
_CHARSPUNCT = _CHARS + "$%*+?"

def get_admin_user():
    return _USERNAME

def get_default_password():
    return _PASSWORD

def get_default_pin():
    return _PIN

def hash_password(project, user_id, password):
    "Return hashed password, as a string, on failure return None"
    seed_password = project + str(user_id) +  password
    hashed_password = hashlib.sha512(   seed_password.encode('utf-8')  ).digest().hex()
    return hashed_password


def hash_pin(pin, seed):
    "Return hashed pin, as a string, on failure return None"
    seed_pin = seed +  pin
    hashed_pin = hashlib.sha512(   seed_pin.encode('utf-8')  ).digest().hex()
    return hashed_pin


def open_database():
    "Opens the database, and returns the database connection"
    # connect to database
    try:
        #con = psycopg2.connect(dbname='astrodb', user='astro', password='xxSgham', host='10.105.192.252')
        con = psycopg2.connect(dbname='astrodb', user='astro', password='xxSgham', host='localhost')
    except:
        raise ServerError(message="Failed database connection.")
    return con


def close_database(con):
    "Closes database connection"
    con.close()


def get_emailuserpass(con=None):
    "Return (emailusername, emailpassword) for server email account, return None on failure"
    if con is None:
        con = open_database()
        result = get_emailuserpass(con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select emailuser, emailpassword from serversettings where server_id = '1'")
        result = cur.fetchone()
        if not result:
            return None
    return result

def get_emailserver(con=None):
    "Return (emailserver, no_reply, starttls) for server email account, return None on failure"
    if con is None:
        con = open_database()
        result = get_emailserver(con)
        con.close()
        return result
    cur = con.cursor()
    cur.execute("select emailserver, no_reply, starttls from serversettings where server_id = '1'")
    result = cur.fetchone()
    if not result:
        return None
    if (not result[0]) or (not result[1]):
        return None
    return (result[0], result[1], bool(result[2]))


def set_emailserver(emailuser, emailpassword, emailserver, no_reply, starttls, con=None):
    "Return True on success, False on failure, this updates the email server settings, if con given does not commit"
    if (not emailserver) or (not no_reply):
        return False
    if con is None:
        try:
            con = open_database()
            result = set_emailserver(emailuser, emailpassword, emailserver, no_reply, starttls, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    try:
        cur = con.cursor()
        cur.execute("update serversettings set emailuser = %s, emailpassword = %s, emailserver = %s, no_reply = %s,  starttls = %s where server_id = '1'", (emailuser, emailpassword, emailserver, no_reply, int(starttls)))
    except:
        return False
    return True


def adduser(project, sponsor_id, username, role="MEMBER", member="0000", email=None, con=None):
    "Return new user_id, password on success, None on failure, this generates a password and inserts a new user, if con given, does not commit"
    if (not username) or (not role) or (not member):
        return False
    if role not in ('GUEST', 'MEMBER', 'ADMIN'):
        return False
    if role == 'GUEST':
        email = None
        member = "0000"
    if con is None:
        try:
            con = open_database()
            result = adduser(project, sponsor_id, username, role, member, email, con)
            if result is not None:
                con.commit()
            con.close()
        except:
            return
    else:
        try:
            cur = con.cursor()
            # create a user, initially without a password
            cur.execute("insert into users (user_id, username, password, role, email, member, guests) values (default, %s, %s, %s, %s, %s, %s)", (username, None,  role, email, member, 0))
            cur.execute("select user_id from users where username = %s", (username,))
            selectresult = cur.fetchone()
            if selectresult is None:
                return
            user_id = selectresult[0]
            # create six character password
            password = ''.join(random.choice(_CHARS) for x in range(6))
            hashed_password = hash_password(project, user_id, password)
            cur.execute("update users set password = %s where user_id = %s", (hashed_password, user_id))
            result = user_id, password
            # If the user is a guest, add to the guests expirey table
            if role == 'GUEST':
                # create an expire datetime of 10 days away at mid day
                ten_days = datetime.utcnow() + timedelta(days=10)
                expire_time = datetime(ten_days.year, ten_days.month, ten_days.day, hour=12)
                cur.execute("insert into guests (USER_ID, SPONSOR_ID, exp_date) values (%s, %s, %s)", (user_id, sponsor_id, expire_time))            
        except:
            return
    return result


def get_hashed_password_user_id(username, con=None):
    "Return (hashed_password, user_id) for username, return None on failure"
    if not username:
        return
    if con is None:
        con = open_database()
        result = get_hashed_password_user_id(username, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select password, user_id from users where username = %s", (username,))
        result = cur.fetchone()
        if not result:
            return
    return result


def get_hashed_password(user_id, con=None):
    "Return hashed_password for user_id, return None on failure"
    if not user_id:
        return
    if con is None:
        con = open_database()
        result = get_hashed_password(user_id, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select password from users where user_id = %s", (user_id,))
        result = cur.fetchone()
        if not result:
            return
        result = result[0]
    return result


def set_password(project, user_id, password, con=None):
    "Return True on success, False on failure, this updates an existing user, if con given does not commit"
    if (not user_id) or (not password):
        return False
    if con is None:
        try:
            con = open_database()
            result = set_password(project, user_id, password, con)
            if result:
                con.commit()
            con.close()
        except:
            return False
        return result
    hashed_password = hash_password(project, user_id, password)
    try:
        cur = con.cursor()
        cur.execute("update users set password = %s where user_id = %s", (hashed_password, user_id))
    except:
        return False
    return True


def new_password(project, user_id, con=None):
    "Return password on success, None on failure, this generates a password for an existing user, if con given does not commit"
    if not user_id:
        return
    if user_id == 1:
        return
    if con is None:
        try:
            con = open_database()
            password = new_password(project, user_id, con)
            if password:
                con.commit()
            con.close()
            return password
        except:
            return
    else:
        # create six character password
        password = ''.join(random.choice(_CHARS) for x in range(6))
        hashed_password = hash_password(project, user_id, password)
        try:
            cur = con.cursor()
            cur.execute("update users set password = %s where user_id = %s", (hashed_password, user_id))
        except:
            return
    return password


def check_password(project, username, password):
    "Returns True if this password belongs to this user, given a username"
    pwd_id = get_hashed_password_user_id(username)
    if not pwd_id:
        return False
    # Check if database hashed password is equal to the hash of the given password
    if pwd_id[0] == hash_password(project, pwd_id[1], password):
        # password valid
        return True
    return False


def check_password_of_user_id(project, user_id, password):
    "Returns True if this password belongs to this user, given a user_id"
    hashed_password = get_hashed_password(user_id)
    if not hashed_password:
        return False
    # Check if database hashed password is equal to the hash of the given password
    if hashed_password == hash_password(project, user_id, password):
        # password valid
        return True
    return False


def get_user_id(username, con=None):
    "Return user_id for user, return None on failure"
    if not username:
        return
    if con is None:
        con = open_database()
        user_id = get_user_id(username, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select user_id from users where username = %s", (username,))
        result = cur.fetchone()
        if result is None:
            return
        user_id = result[0]
    return user_id


def number_of_guests(sponsor_id, con=None):
    """Return max number of guests this user can create, return None on failure"""
    if not sponsor_id:
        return
    if con is None:
        con = open_database()
        number = number_of_guests(sponsor_id, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select guests from users where user_id = %s", (sponsor_id,))
        result = cur.fetchone()
        if result is None:
            number = 0
        else:
            number = result[0]
            if not number:
                number = 0
    return number


def get_guests(sponsor_id, con=None):
    """Return max number of guests this user can create,
       Followed by a tuple of current number of guests user has created, being
       (guest_user_id, guest_name, exp_date), return None, () on failure"""
    if not sponsor_id:
        return
    if con is None:
        con = open_database()
        number, guests = get_guests(sponsor_id, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select guests from users where user_id = %s", (sponsor_id,))
        result = cur.fetchone()
        if result is None:
            number = 0
        else:
            number = result[0]
            if not number:
                number = 0
        # number is zero, but guests may still exist due to number being
        # recently changed, and guests not yet expired, or due to sponsor being an admin
        # get guest id's, name and expirey date
        cur.execute("select guests.user_id, users.username, guests.exp_date from guests,users where guests.user_id = users.user_id and guests.sponsor_id = %s", (sponsor_id,))
        guests = cur.fetchall()
        if not guests:
            return number, ()
    return number, guests


def set_guests(user_id, guest_number, con=None):
    """Return True on success, False on failure, this updates the number of guests an existing member can create,
       if con given does not commit"""
    if not user_id:
        return False
    if con is None:
        try:
            con = open_database()
            result = set_guests(user_id, guest_number, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        try:
            # number of guests is only applicable to members
            cur = con.cursor()
            cur.execute("update users set guests = %s where user_id = %s and role = %s", (guest_number, user_id, "MEMBER"))
        except:
            return False
    return True


def get_role(user_id, con=None):
    "Return role for user, return None on failure"
    if not user_id:
        return
    if con is None:
        con = open_database()
        role = get_role(user_id, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select role from users where user_id = %s", (user_id,))
        result = cur.fetchone()
        if result is None:
            return
        role = result[0]
        if not role:
            return
    return role


def set_role(sponsor_id, user_id, role, con=None):
    """Return True on success, False on failure, this updates the role of an existing user, if con given does not commit
          Trying to change role of user_id of 1 is a failure - cannot change role of special user Admin"""
    if not user_id:
        return False
    if user_id == 1:
        return False
    if role not in ('GUEST', 'MEMBER', 'ADMIN'):
        return False
    if con is None:
        try:
            con = open_database()
            result = set_role(sponsor_id, user_id, role, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        try:
            cur = con.cursor()
            if role != 'ADMIN':
                cur.execute("delete from admins where user_id = %s", (user_id,))

            if role == 'GUEST':
                # setting a user as guest requires the users email and membership number to be deleted
                cur.execute("update users set role = %s, email = %s, member = %s, guests = %s where user_id = %s", (role, None, "0000", 0, user_id))
                # create an expire datetime of 10 days away at mid day
                ten_days = datetime.utcnow() + timedelta(days=10)
                expire_time = datetime(ten_days.year, ten_days.month, ten_days.day, hour=12)
                cur.execute("insert into guests (USER_ID, SPONSOR_ID, exp_date) values (%s, %s, %s)", (user_id, sponsor_id, expire_time))
            else:
                cur.execute("delete from guests where user_id = %s", (user_id,))
                # any role change resets number of guests which can be created to zero
                cur.execute("update users set role = %s, guests = %s where user_id = %s", (role, 0, user_id))
        except:
            return False
    return True


def get_email(user_id, con=None):
    "Return email for user, return None on failure"
    if not user_id:
        return
    if con is None:
        con = open_database()
        email = get_email(user_id, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select email from users where user_id = %s", (user_id,))
        result = cur.fetchone()
        if result is None:
            return
        email = result[0]
        if not email:
            return
    return email


def set_email(user_id, email, con=None):
    "Return True on success, False on failure, this updates the email of an existing user, if con given does not commit"
    if not user_id:
        return False
    if con is None:
        try:
            con = open_database()
            result = set_email(user_id, email, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        try:
            cur = con.cursor()
            cur.execute("update users set email = %s where user_id = %s and role != %s", (email, user_id, 'GUEST'))
        except:
            return False
    return True


def get_user_from_id(user_id, con=None):
    "Return (username, role, email, member) or None on failure"
    if con is None:
        con = open_database()
        user = get_user_from_id(user_id, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select username, role, email, member from users where user_id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return
    return user


def get_user_from_username(username, con=None):
    "Return (user_id, role, email, member) or None on failure"
    if con is None:
        con = open_database()
        user = get_user_from_username(username, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select user_id, role, email, member from users where username = %s", (username,))
        user = cur.fetchone()
        if not user:
            return
    return user


def set_message(username, message, con=None):
    "Return string of timestamp, user and message on success, False on failure, this inserts the message, if con given, does not commit"
    if (not message) or (not username):
        return False

    thistime = datetime.utcnow()
    try:
        if con is None:
            con = open_database()
            result = set_message(username, message, con)
            if result:
                con.commit()
            con.close()
        else:
            cur = con.cursor()
            cur.execute("insert into messages (mess_id, message, time, username) values (default, %s, %s, %s)", (message, thistime, username))
            cur.close()
            result = thistime.strftime("%d %b %Y %H:%M:%S") + "\nFrom  " + username + "\n" + message
    except:
        return False
    return result


def get_all_messages(con=None):
    "Return string containing all messages return None on failure"
    if con is None:
        con = open_database()
        m_string = get_all_messages(con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select message, time, username from messages order by mess_id DESC")
        m_string = ''
        for m in cur:
            m_string += m[1].strftime("%d %b %Y %H:%M:%S") + "\nFrom  " + m[2] + "\n" + m[0] + "\n\n"
    return m_string


def get_users(limit=None, offset=None, names=True, con=None):
    "Return list of lists [user_id, username, role, membership number] apart from Admin user with user id 1"
    if con is None:
        con = open_database()
        u_list = get_users(limit, offset, names, con)
        con.close()
    else:
        cur = con.cursor()
        if names:
            if limit is None:
                cur.execute("select user_id, username, role, member from users  where user_id != 1 order by username")
            elif offset is None:
                cur.execute("select user_id, username, role, member from users where user_id != 1 order by username limit %s", (limit,))
            else:
                cur.execute("select user_id, username, role, member from users where user_id != 1 order by username  limit %s offset %s", (limit, offset))
        else:
            if limit is None:
                cur.execute("select user_id, username, role, member from users where user_id != 1 order by cast (member as integer),username")
            elif offset is None:
                cur.execute("select user_id, username, role, member from users where user_id != 1 order by cast (member as integer), username limit %s", (limit,))
            else:
                cur.execute("select user_id, username, role, member from users where user_id != 1 order by cast (member as integer),username  limit %s offset %s", (limit, offset))
        u_list = []
        for u in cur:
            user_id = u[0]
            username = u[1]
            role = u[2]
            if u[3]:
                member = u[3]
            else:
                member = ''
            u_list.append([user_id, username, role, member])
    return u_list


def delete_user_id(user_id, con=None):
    """Delete user with given user_id. Return True on success, False on failure, if con given does not commit
          Trying to delete user_id of 1 is a failure - cannot delete special user Admin"""
    if not user_id:
        return False
    if user_id == 1:
        return False
    if con is None:
        try:
            con = open_database()
            result = delete_user_id(user_id, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        try:
            cur = con.cursor()
            cur.execute("delete from users where user_id = %s", (user_id,))
            cur.execute("delete from slots where user_id = %s", (user_id,))
        except:
            return False
    return True


def set_username(user_id, new_username, con=None):
    """Return True on success, False on failure, this updates an existing user, if con given does not commit
          Trying to change name of user_id of 1 is a failure - cannot alter special user Admin"""
    if (not user_id) or (not new_username):
        return False
    if user_id == 1:
        return False
    if con is None:
        try:
            con = open_database()
            result = set_username(user_id, new_username, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        try:
            cur = con.cursor()
            cur.execute("update users set username = %s where user_id = %s", (new_username, user_id))
        except:
            return False
    return True


def set_membership_number(user_id, new_member, con=None):
    "Return True on success, False on failure, this updates an existing user, if con given does not commit"
    if not user_id:
        return False
    if con is None:
        try:
            con = open_database()
            result = set_membership_number(user_id, new_member, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        try:
            cur = con.cursor()
            cur.execute("update users set member = %s where user_id = %s and role != %s", (new_member, user_id, 'GUEST'))
        except:
            return False
    return True


def set_pin(project, user_id, new_pin, con=None):
    "Return True on success, False on failure, this updates an existing admin, if con given does not commit"
    if not user_id:
        return False
    if con is None:
        try:
            con = open_database()
            result = set_pin(project, user_id, new_pin, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        # The seed for each hash will consist of project + user_id + pair numbers
        part_seed = project + str(user_id)
        pin1_2 = hash_pin(new_pin[0] + new_pin[1], seed=part_seed+'1')
        pin1_3 = hash_pin(new_pin[0] + new_pin[2], seed=part_seed+'2')
        pin1_4 = hash_pin(new_pin[0] + new_pin[3], seed=part_seed+'3')
        pin2_3 = hash_pin(new_pin[1] + new_pin[2], seed=part_seed+'4')
        pin2_4 = hash_pin(new_pin[1] + new_pin[3], seed=part_seed+'5')
        pin3_4 = hash_pin(new_pin[2] + new_pin[3], seed=part_seed+'6')
        try:
            cur = con.cursor()
            cur.execute("""insert into admins (user_id, pin1_2, pin1_3, pin1_4, pin2_3, pin2_4, pin3_4) values (%s, %s, %s, %s, %s, %s, %s)
                           on conflict (user_id) do update set pin1_2 = %s, pin1_3 = %s, pin1_4 = %s, pin2_3 = %s, pin2_4 = %s, pin3_4 = %s""",
                        (user_id, pin1_2, pin1_3, pin1_4, pin2_3, pin2_4, pin3_4, pin1_2, pin1_3, pin1_4, pin2_3, pin2_4, pin3_4))
        except:
            return False
    return True


def get_admin(user_id, con=None):
    "Return admin row as a list on success, None on failure"
    if not user_id:
        return
    if con is None:
        con = open_database()
        result = get_admin(user_id, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select * from admins where user_id = %s", (user_id,))
        result = cur.fetchone()
        if not result:
            return
        # result is
        # user_id, pin1_2, pin1_3, pin1_4, pin2_3, pin2_4, pin3_4
        # set result as list rather than tuple, so it can be changed
        result = list(result)
    return result


def make_admin(project, sponsor_id, user_id, con=None):
    """Return PIN on success, None on failure, this creates a new admin, if the given user is not already an admin
          and generates a PIN for him.    If con given does not commit"""
    if not user_id:
        return
    # This function is not available for special user Admin
    if user_id == 1:
        return
    if con is None:
        try:
            con = open_database()
            result = make_admin(project, sponsor_id, user_id, con)
            if result:
                con.commit()
            con.close()
        except:
            return
        return result
    # generate a pin
    new_pin = ''.join(random.choice(_CHARSPUNCT) for x in range(4))
    if not set_pin(project, user_id, new_pin, con):
        return
    if not set_role(sponsor_id, user_id, 'ADMIN', con):
        return
    return new_pin


def get_administrators(con=None):
    """Get all admins (username, member, user_id) apart from special user Admin
           Returns None on failure or if none found"""
    if con is None:
        try:
            con = open_database()
            result = get_administrators(con)
            con.close()
        except:
            return
        return result
    cur = con.cursor()
    cur.execute("select username, member, user_id from users where role = %s and user_id != 1 ORDER BY username ASC", ("ADMIN",))
    result = cur.fetchall()
    if not result:
        return
    return result


# slot status integers
# 0 = Not booked
# 1 = booked by given user id
# 2 = disabled


def get_slot_status(slot, con=None):
    """Given a Slot object, returns (status_integer, user_id), user_id will be None if not booked
       returns None on failure"""
    if con is None:
        try:
            con = open_database()
            result = get_slot_status(slot, con)
            con.close()
        except:
            return
        return result
    starttime = slot.starttime
    cur = con.cursor()
    cur.execute("select status, user_id from slots where starttime = %s", (starttime,))
    status_id = cur.fetchone()
    if status_id is None:
        return (0, None)
    return status_id


def disable_slot(slot, con=None):
    """Return True on success, False on failure, if con given does not commit"""
    if not slot:
        return False
    if con is None:
        try:
            con = open_database()
            result = disable_slot(slot, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    try:
        # create or update slot with status 2 for disabled
        cur = con.cursor()
        cur.execute("""insert into slots (starttime, status, user_id) values (%s, %s, %s)
                       on conflict (starttime) do update set status = %s, user_id = %s""",
                     (slot.starttime, 2, None, 2, None))
    except:
        return False
    return True


def book_slot(slot, user_id, con=None):
    "Return True on success, False on failure, if con given does not commit"
    if (not user_id) or (not slot):
        return False
    if con is None:
        try:
            con = open_database()
            result = book_slot(slot, user_id, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    status_id = get_slot_status(slot, con)
    if not status_id:
        return False
    try:
        # create or update slot with status 1 for booked
        cur = con.cursor()
        cur.execute("""insert into slots (starttime, status, user_id) values (%s, %s, %s)
                     on conflict (starttime) do update set status = %s, user_id = %s""", (slot.starttime, 1, user_id, 1, user_id))
    except:
        return False
    return True


def delete_slot(slot, con=None):
    """Delete slot. Return True on success, False on failure, if con given does not commit"""
    if con is None:
        try:
            con = open_database()
            result = delete_slot(slot, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        try:
            cur = con.cursor()
            cur.execute("delete from slots where starttime = %s", (slot.starttime,))
        except:
            return False
    return True


def get_users_sessions(starttime, endtime, user_id, con=None):
    """starttime, endtime are datetime objects, returns each session booked by
       the user between these times as a list of slot startimes, if none found
       returns empty tuple, on failure returns None"""
    if not user_id:
        return
    if con is None:
        try:
            con = open_database()
            result = get_users_sessions(starttime, endtime, user_id, con)
            con.close()
        except:
            return
        return result
    cur = con.cursor()
    cur.execute("select starttime from slots where starttime >= %s and starttime <= %s and status = 1 and user_id = %s", (starttime, endtime, user_id))
    result = cur.fetchall()
    if not result:
        return []
    return [ t[0] for t in result ]


def get_users_next_session(starttime, user_id, con=None):
    """starttime is a datetime objects, returns next session booked by
       the user from starttime on as a slot startimes, if none found
       returns None"""
    if not user_id:
        return
    if con is None:
        try:
            con = open_database()
            result = get_users_next_session(starttime, user_id, con)
            con.close()
        except:
            return
        return result
    cur = con.cursor()
    cur.execute("select starttime from slots where starttime >= %s and status = 1 and user_id = %s order by starttime", (starttime, user_id))
    result = cur.fetchall()
    # result is a list of tuples, and could be [()]
    if not result:
        return
    if not result[0]:
        return
    return result[0][0]



def get_sessions(con=None):
    "Return sessions, True if enabled, False if not, return None on failure"
    if con is None:
        con = open_database()
        result = get_sessions(con)
        con.close()
        return result
    cur = con.cursor()
    cur.execute("select sessions from serversettings where server_id = '1'")
    result = cur.fetchone()
    if not result:
        return None
    return bool(result[0])


def set_sessions(sessions, con=None):
    "Return True on success, False on failure, this updates the sessions enabled flag, if con given does not commit"
    if con is None:
        try:
            con = open_database()
            result = set_sessions(sessions, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    try:
        if sessions:
            session_flag = 1
        else:
            session_flag = 0
        cur = con.cursor()
        cur.execute("update serversettings set sessions = %s where server_id = '1'", (session_flag,))
    except:
        return False
    return True


def get_text(variable_name, con=None):
    "Return variable_text for given variable_name, return None on failure"
    if not variable_name:
        return
    if con is None:
        con = open_database()
        variable_text = get_text(variable_name, con)
        con.close()
    else:
        cur = con.cursor()
        cur.execute("select variable_text from variabletext where variable_name = %s", (variable_name,))
        result = cur.fetchone()
        if result is None:
            return
        variable_text = result[0]
        if not variable_text:
            return
    return variable_text


def set_text(variable_name, variable_text, con=None):
    "Return True on success, False on failure, this sets the text of a variable_name, if con given does not commit"
    if not variable_name:
        return False
    if con is None:
        try:
            con = open_database()
            result = set_text(variable_name, variable_text, con)
            if result:
                con.commit()
            con.close()
            return result
        except:
            return False
    else:
        try:
            cur = con.cursor()
            cur.execute("""insert into variabletext (variable_name, variable_text) values (%s, %s)
                           on conflict (variable_name) do update set variable_text = %s""", (variable_name, variable_text, variable_text))
        except:
            return False
    return True
    
    
