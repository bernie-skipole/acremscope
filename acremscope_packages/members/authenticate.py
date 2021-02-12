##################################
#
# These functions checks the administrative
# user's attempt to authenticate with a PIN, and
# if ok, sets the users status to authenticated
#
##################################


import random

from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import database_ops, redis_ops

# These functions require a list of the id numbers of the admin call pages
# which after authentication the call can be diverted to

_DIVERT = (3001,   # setup call
           8100,   # set pin pcall
           9001)   # tests call



def fill_input_pin(skicall):
    "Fills the page in which admin user sets a PIN which is to be tested"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # called by responder 5515

    user_id  = call_data['user_id']

    # Check for locked out due to too many failed tries
    tries = redis_ops.get_tries(user_id, skicall.proj_data.get("rconn_3"), skicall.proj_data.get("rconn"))
    if tries is None:
        raise FailPage(message="Invalid user")
    if tries > 3:
        raise FailPage(message= "Authentication locked out.")

    # Generate a random number, unique to the cookie, and set it into radius
    # and also as an hidden field in the form, so it is submitted when the user submits
    # a PIN and will be checked against the radius database.
    rnd_number = redis_ops.set_rnd(call_data.get('cookie'), skicall.proj_data.get("rconn_1"), skicall.proj_data.get("rconn"))
    if rnd_number is None:
        raise FailPage(message="Failure accessing the database")
    page_data['input_pin', 'hidden_field1'] = str(rnd_number)

    # As the call to this page is diverted from calling an admin function
    # we need the original page to call again after authentication,
    # so store this original requested page as a further hidden_field
    # However this only applies to specific pages
    diverted_page = call_data["called_ident"][1]
    if diverted_page in _DIVERT:
        page_data['input_pin', 'hidden_field2'] = str(diverted_page )

    # function redis_ops.two_min_numbers returns two random numbers
    # one valid for the current two minute time slot, one valid for the previous
    # two minute time slot.  Four sets of such random numbers are available
    # specified by argument rndset which should be 0 to 3
    # This login form uses rndset 1
    rnd1, rnd2 = redis_ops.two_min_numbers(rndset=1, skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    if rnd1 is None:
        raise ServerError(message = "Database access failure")
    page_data['input_pin', 'hidden_field3'] = str(rnd1)

    # When the form is submitted, the received number will be checked against another call
    # to database_ops.timed_random_numbers, and if it is equal to either of them, it is within
    # a valid timeout period.

    # Get the pair of pin characters to be requested
    pair = redis_ops.get_pair(call_data.get('cookie'), skicall.proj_data.get("rconn_1"), skicall.proj_data.get("rconn"))
    if not pair:
        raise FailPage(message="Failure accessing database")

    if pair == 1:
        page_data['input_text','para_text'] = "Please input the first and second characters of your PIN:"
        page_data['input_pin', 'pin1'] = True
        page_data['input_pin', 'pin2'] = True
        page_data['input_pin', 'pin3'] = False
        page_data['input_pin', 'pin4'] = False
    elif pair == 2:
        page_data['input_text','para_text'] = "Please input the first and third characters of your PIN:"
        page_data['input_pin', 'pin1'] = True
        page_data['input_pin', 'pin2'] = False
        page_data['input_pin', 'pin3'] = True
        page_data['input_pin', 'pin4'] = False
    elif pair == 3:
        page_data['input_text','para_text'] = "Please input the first and fourth characters of your PIN:"
        page_data['input_pin', 'pin1'] = True
        page_data['input_pin', 'pin2'] = False
        page_data['input_pin', 'pin3'] = False
        page_data['input_pin', 'pin4'] = True
    elif pair == 4:
        page_data['input_text','para_text'] = "Please input the second and third characters of your PIN:"
        page_data['input_pin', 'pin1'] = False
        page_data['input_pin', 'pin2'] = True
        page_data['input_pin', 'pin3'] = True
        page_data['input_pin', 'pin4'] = False
    elif pair == 5:
        page_data['input_text','para_text'] = "Please input the second and fourth characters of your PIN:"
        page_data['input_pin', 'pin1'] = False
        page_data['input_pin', 'pin2'] = True
        page_data['input_pin', 'pin3'] = False
        page_data['input_pin', 'pin4'] = True
    elif pair == 6:
        page_data['input_text','para_text'] = "Please input the third and fourth characters of your PIN:"
        page_data['input_pin', 'pin1'] = False
        page_data['input_pin', 'pin2'] = False
        page_data['input_pin', 'pin3'] = True
        page_data['input_pin', 'pin4'] = True
    else:
        raise FailPage(message="Failure accessing database")


def check_pin(skicall):
    "Checks submitted PIN"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # called by responder 5021

    user_id  = call_data['user_id']
    diverted_page = None

    call_data['authenticated'] = False

    admin = database_ops.get_admin(user_id)
    if not admin:
        raise FailPage(message="Invalid user")
    # admin is a list of 
    # user_id, pin1_2, pin1_3, pin1_4, pin2_3, pin2_4, pin3_4


    try:
        # Increment tries and check for locked out due to too many failed tries
        tries = redis_ops.increment_try(user_id, skicall.proj_data.get("rconn_3"), skicall.proj_data.get("rconn"))
        if tries is None:
            raise FailPage(message="Invalid user")
        if tries > 3:
            raise FailPage(message= "Authentication locked out. Please try again after an hour.")
        # Test saved random number
        rnd_number = redis_ops.get_rnd(call_data.get('cookie'), skicall.proj_data.get("rconn_1"), skicall.proj_data.get("rconn"))
        if rnd_number is None:
            raise FailPage(message= "Invalid input")
        # Test received hidden_field1 is the same as the rnd_number in the radius database
        if rnd_number != int(call_data['input_pin','hidden_field1']):
            raise FailPage(message= "Invalid input")
        # check timed random number
        str_rnd = call_data['input_pin','hidden_field3']
        # check hidden random number is still valid
        if not str_rnd:
            raise FailPage(message = "Invalid input")
        try:
            int_rnd = int(str_rnd)
        except:
            raise FailPage(message = "Invalid input")
        rnd = redis_ops.two_min_numbers(rndset=1, skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
        # rnd is a tuple of two valid random numbers
        # rnd[0] for the current 2 minute time slot
        # rnd[1] for the previous 2 minute time slot
        # int_rnd must be one of these to be valid
        if rnd[0] is None:
            raise ServerError(message = "Database access failure")
        if int_rnd not in rnd:
            raise FailPage(message = "PIN page expired, please try again.")

        # If diverted page is present, check it is valid
        if (('input_pin', 'hidden_field2') in call_data) and call_data[('input_pin', 'hidden_field2')] :
            try:
                diverted_page = int(call_data[('input_pin', 'hidden_field2')])
            except:
                raise FailPage(message= "Invalid input")
            # Allowed values of pages to go to
            if diverted_page not in _DIVERT:
                raise FailPage(message= "Invalid input")
        # get pair of pin characters to be tested
        pair = redis_ops.get_pair(call_data.get('cookie'), skicall.proj_data.get("rconn_1"), skicall.proj_data.get("rconn"))
        seed = call_data['project'] + str(user_id) + str(pair)
        if pair == 1:
            if call_data['input_pin', 'pin3'] or call_data['input_pin', 'pin4']:
                raise FailPage(message= "Invalid PIN")
            pin1_2 = database_ops.hash_pin(call_data['input_pin', 'pin1'] + call_data['input_pin', 'pin2'], seed)
            if pin1_2 != admin[1]:
                raise FailPage(message= "Invalid PIN")
        elif pair == 2:
            if call_data['input_pin', 'pin2'] or call_data['input_pin', 'pin4']:
                raise FailPage(message= "Invalid PIN")
            pin1_3 = database_ops.hash_pin(call_data['input_pin', 'pin1'] + call_data['input_pin', 'pin3'], seed)
            if pin1_3 != admin[2]:
                raise FailPage(message= "Invalid PIN")
        elif pair == 3:
            if call_data['input_pin', 'pin2'] or call_data['input_pin', 'pin3']:
                raise FailPage(message= "Invalid PIN")
            pin1_4 = database_ops.hash_pin(call_data['input_pin', 'pin1'] + call_data['input_pin', 'pin4'], seed)
            if pin1_4 != admin[3]:
                raise FailPage(message= "Invalid PIN")
        elif pair == 4:
            if call_data['input_pin', 'pin1'] or call_data['input_pin', 'pin4']:
                raise FailPage(message= "Invalid PIN")
            pin2_3 = database_ops.hash_pin(call_data['input_pin', 'pin2'] + call_data['input_pin', 'pin3'], seed)
            if pin2_3 != admin[4]:
                raise FailPage(message= "Invalid PIN")
        elif pair == 5:
            if call_data['input_pin', 'pin1'] or call_data['input_pin', 'pin3']:
                raise FailPage(message= "Invalid PIN")
            pin2_4 = database_ops.hash_pin(call_data['input_pin', 'pin2'] + call_data['input_pin', 'pin4'], seed)
            if pin2_4 != admin[5]:
                raise FailPage(message= "Invalid PIN")
        elif pair == 6:
            if call_data['input_pin', 'pin1'] or call_data['input_pin', 'pin2']:
                raise FailPage(message= "Invalid PIN")
            pin3_4 = database_ops.hash_pin(call_data['input_pin', 'pin3'] + call_data['input_pin', 'pin4'], seed)
            if pin3_4 != admin[6]:
                raise FailPage(message= "Invalid PIN")
        else:
            raise FailPage(message= "Authentication Failed")
        # user is authenticated
        ### changed to redis
        if not redis_ops.set_authenticated(call_data['cookie'], user_id, skicall.proj_data.get('rconn_2'), skicall.proj_data.get('rconn')):
            # failed to set authenticated to True
            raise FailPage(message= "Unable to set Authenticate")
        # clears number of tries
        redis_ops.clear_tries(user_id, skicall.proj_data.get('rconn_3'), skicall.proj_data.get('rconn'))
        call_data['authenticated'] = True
    except FailPage:
        raise
    except:
        raise FailPage(message= "Invalid input")
    if diverted_page:
        raise GoTo(target=diverted_page, clear_submitted=True, clear_page_data=True)
        
