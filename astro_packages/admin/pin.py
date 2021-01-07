########################################
#
# These functions edit PINS
#
########################################



from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import database_ops


def fill_new_pin(skicall):
    """Populates the New PIN page, this is the page shown when an administrator chooses
          New PIN from the Admin page"""

    # called from responder 8100

    result = database_ops.get_administrators()

    # Fills the table of administrators, the database call returns a list of lists in the
    # format required by the widget
     # Each inner list being (username, member, user_id) apart from special user Admin
    # col 0 and 1 are the text strings to place in the first two columns of the admins table
    # col 2 is the get field contents of the button link

    if not result:
        skicall.page_data['tabletext', 'show'] = False
        skicall.page_data['admins', 'show'] = False
    else:
        skicall.page_data['admins', 'contents'] = result



def set_your_pin(skicall):
    """Given the four characters of a pin, for the current logged in user sets it"""

    # called from responder 8101

    call_data = skicall.call_data
    page_data = skicall.page_data

    username = call_data['username']
    user_id = call_data['user_id']

    pin1 = call_data['newpin','pin1']
    if not pin1 or (len(pin1) != 1):
        raise FailPage('Invalid PIN', widget = 'newpin')
    pin2 = call_data['newpin','pin2']
    if not pin2 or (len(pin2) != 1):
        raise FailPage('Invalid PIN', widget = 'newpin')
    pin3 = call_data['newpin','pin3']
    if not pin3 or (len(pin3) != 1):
        raise FailPage('Invalid PIN', widget = 'newpin')
    pin4 = call_data['newpin','pin4']
    if not pin4 or (len(pin4) != 1):
        raise FailPage('Invalid PIN', widget = 'newpin')
    if database_ops.set_pin(skicall.project, user_id, [pin1, pin2, pin3, pin4]):
        space_pin = pin1+' '+pin2+' '+pin3+' '+pin4
        page_data['showadminpin', 'para_text'] = "New PIN for user %s is\n%s" % (username, space_pin)
        page_data['showadminpin', 'hide'] = False
    else:
        raise FailPage('Unable to set new PIN into database', widget = 'newpin')



def fill_generate_pin_template(skicall):
    """Fills the template page to generate a PIN for an edited user, this page is called when a user role
          is changed to Admin"""

    # called by responder 3615

    if not 'edited_user_id' in skicall.call_data:
        raise FailPage('Invalid user')
    edited_user_id = skicall.call_data['edited_user_id']

    if edited_user_id == 1:
        raise FailPage('This function is not available for this user.')

    edited_user = database_ops.get_user_from_id(edited_user_id)
    # edited user should be (username, role, email, member)
    if not edited_user:
        raise FailPage('Invalid user')

    skicall.page_data['pagetop','para_text'] = "Set Administrative access PIN for %s" % (edited_user[0],)
    skicall.page_data['newadminpin','get_field1'] = str(edited_user_id)



def make_pin(skicall):
    """Create a PIN for an edited user and set user to Admin role"""


    # called by responders 3160 and 3170

    try:
        edited_user_id = int(skicall.call_data['newadminpin'])
    except:
        raise FailPage('Invalid edited user')

    if edited_user_id == 1:
        raise FailPage('Cannot create random PIN for Admin')

    edited_user = database_ops.get_user_from_id(edited_user_id)
    # edited user should be (username, role, email, member)
    if not edited_user:
        raise FailPage('Invalid user')

    skicall.call_data['edited_user_id'] = edited_user_id
    # generate new pin
    new_pin = database_ops.make_admin(skicall.project, skicall.call_data['user_id'], edited_user_id)
    if new_pin:
        space_pin = ' '.join( c for c in new_pin)
        skicall.page_data['showadminpin', 'para_text'] = 'New PIN for user %s is\n%s' % (edited_user[0], space_pin)
        skicall.page_data['showadminpin', 'hide'] = False
    else:
        raise FailPage('Failed database access, unable to set PIN')



