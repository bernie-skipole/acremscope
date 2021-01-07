##################################
#
# This function checks the users attempt to log in
#
##################################


import random

from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import database_ops, redis_ops


def create_login_page(skicall):
    """Sets a hidden random number in the login form, which is only valid for four minutes
       This expires the login page, and also makes it difficult to script login calls"""

    # function redis_ops.two_min_numbers returns two random numbers
    # one valid for the current two minute time slot, one valid for the previous
    # two minute time slot.  Four sets of such random numbers are available
    # specified by argument rndset which should be 0 to 3
    # This login form uses rndset 0
    rnd1, rnd2 = redis_ops.two_min_numbers(rndset=0, rconn=skicall.proj_data.get("rconn_0"))
    if rnd1 is None:
        raise ServerError(message = "Database access failure")

    skicall.page_data['loginform', 'hidden_field1'] = str(rnd1)

    # When the form is submitted, the received number will be checked
    return


def check_login(skicall):
    """The user fills in the username and password widgets on the login template page and
         then submits the data to the responder which calls this function.
         This checks username and password against the member database and raises failpage
         if username and password are not ok, if ok populates call_data"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Called by responder id 5002

    call_data['loggedin'] = False
    call_data['authenticated'] = False

    username = call_data['username', 'input_text']
    password = call_data['password', 'input_text']
    str_rnd = call_data['loginform', 'hidden_field1']

    # check hidden random number is still valid
    if not str_rnd:
        raise FailPage(message = "Invalid input")
    try:
        int_rnd = int(str_rnd)
    except:
        raise FailPage(message = "Invalid input")

    rnd = redis_ops.two_min_numbers(rndset=0, rconn=skicall.proj_data.get("rconn_0"))
    # rnd is a tuple of two valid random numbers
    # rnd[0] for the current 2 minute time slot
    # rnd[1] for the previous 2 minute time slot
    # int_rnd must be one of these to be valid
    if rnd[0] is None:
        raise ServerError(message = "Database access failure")
    if int_rnd not in rnd:
        raise FailPage(message = "Login page expired, please try again.")
    
    if not username:
        raise FailPage(message= "Login fail: missing username", widget='loginform')
    if not password:
        raise FailPage(message= "Login fail: missing password", widget='loginform')
    if not database_ops.check_password(skicall.project, username, password):
        raise FailPage(message= "Login fail: invalid username-password", widget='loginform')

    # password ok, get user information
    user = database_ops.get_user_from_username(username)
    # user is a tuple of (user_id, role, email, member) or None if the username is not found

    if user is None:
        # something wrong, unable to get user information
        raise FailPage(message= "Login Fail: unable to retrieve user details", widget='loginform')

    # login ok, populate call_data and return
    call_data['user_id'] = user[0]
    call_data['role'] =  user[1]
    call_data['username'] =  username
    call_data['loggedin'] =  True
