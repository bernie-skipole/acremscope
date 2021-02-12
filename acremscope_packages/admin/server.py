
############################
#
# Sets server parameters
#
############################

import os

from skipole import FailPage, GoTo, ValidateError, ServerError

from .. import sun, database_ops, redis_ops, cfg


def create_index(skicall):
    "Fills in the setup index page"

    # called by responder 3001
    skicall.page_data['setup_buttons', 'nav_links'] = [['3010','Add Member', True, ''],
                                                        ['editusers','Edit Users', True, ''],
                                                        ['editsessions','Sessions Control', True, ''],
                                                        ['3020','Server', True, ''],
                                                        ['3301','Web Settings', True, ''],
                                                        ['setpin','New PIN', True, '']
                                                       ]

    # if the current slot is booked, test mode is not available
    if skicall.call_data["booked_user_id"] is not None:
        skicall.page_data['teststatus', 'show'] = True
        skicall.page_data['teststatus', 'para_text'] = "The current slot is booked, Test Mode is not available"
        return

    # check test mode
    if skicall.call_data["test_mode"]:
        # This user has test mode
        skicall.page_data['setup_buttons', 'nav_links'].append(['test_mode','UnSet Test Mode', True, ''])
        skicall.page_data['teststatus', 'show'] = True
        skicall.page_data['teststatus', 'para_text'] = "You have Test Mode Enabled"
        return

    user_id = redis_ops.get_test_mode_user(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    if user_id is None:
        # No user has test mode
        skicall.page_data['setup_buttons', 'nav_links'].append(['test_mode','Set Test Mode', True, ''])
    else:
        # get the username
        user = database_ops.get_user_from_id(user_id)
        skicall.page_data['teststatus', 'show'] = True
        if user is None:
            skicall.page_data['teststatus', 'para_text'] = "user id %s has Test Mode, but username not known." % (user_id,)
        else:
            skicall.page_data['teststatus', 'para_text'] = "Test Mode is not available to you. It has been set by %s" % (user[0],)



def server_settings(skicall):
    """Populates the server settings page"""

    page_data = skicall.page_data

    # called by responder 3020

    ##### SMTP settings
    smtpserver = database_ops.get_emailserver()
    if not smtpserver:
        raise FailPage('Database access failure.')
    emailserver, no_reply, starttls = smtpserver
    if emailserver:
        page_data['emailserver', 'input_text'] = emailserver
    if no_reply:
        page_data['no_reply', 'input_text'] = no_reply
    if starttls:
        page_data['starttls', 'checked'] = True
    else:
        page_data['starttls', 'checked'] = False
    userpass = database_ops.get_emailuserpass()
    if not userpass:
        emailusername = ''
        emailpassword = ''
    else:
        emailusername, emailpassword = userpass
    if emailusername:
        page_data['emailuser', 'input_text'] = emailusername
    if emailpassword:
        page_data['emailpassword', 'input_text'] = emailpassword
    ######## event log
    event_list = redis_ops.get_log_info(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    if not event_list:
        page_data['logtext', 'pre_text'] = "Awaiting events"
    else:
        page_data['logtext', 'pre_text'] = "\n".join(event_list)



def set_server_email_settings(skicall):
    """Sets the smtp settings in the database"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    # called by responder 3021

    try:
        emailuser = call_data['emailuser', 'input_text']
        emailpassword = call_data['emailpassword', 'input_text']
        emailserver = call_data['emailserver', 'input_text']
        no_reply = call_data['no_reply', 'input_text']
        starttls = call_data['starttls', 'checkbox']
    except:
        raise FailPage('Invalid settings.', widget = 'emailsettings')
    if starttls == 'checked':
        starttls = True
    else:
        starttls = False
    if database_ops.set_emailserver(emailuser, emailpassword, emailserver, no_reply, starttls):
        page_data['emailsettings', 'show_para'] = True
    else:
        raise FailPage('Unable to set smtp server settings into database', widget = 'emailsettings')



def add_message(skicall):
    "Adds a message"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # called by responder 3002

    try:
        message = call_data['setstatus','input_text']
        username = call_data['username']
    except:
        raise FailPage('Invalid settings.')

    # store message in database, and get the message, with timestamp and username

    payload = database_ops.set_message(username, message)

    if payload:
        page_data['showresult', 'para_text'] = """The status message has been set."""
        page_data['showresult', 'show'] = True
    else:
        raise FailPage("Database access failure")



#############################################################
#
# Sets system text strings
#
#############################################################


def system_strings(skicall):
    """Sets system strings into the system strings input fields"""

    page_data = skicall.page_data

    org_name = database_ops.get_text('org_name')
    if not org_name:
        org_name = "Remote Telescope"
    page_data['org_name', 'input_text'] = org_name

    header_text = database_ops.get_text('header_text')
    if not header_text:
        header_text = "Remote Telescope"
    page_data['header_text', 'input_text'] = header_text

    home_text = database_ops.get_text('home_text')
    if not home_text:
        home_text = "Remote Telescope"
    page_data['home_text', 'input_text'] = home_text


def set_system_strings(skicall):
    """Sets system strings into the database"""

    call_data = skicall.call_data
    page_data = skicall.page_data

    if (('org_name', 'input_text') in call_data) and call_data['org_name', 'input_text']:
        database_ops.set_text('org_name', call_data['org_name', 'input_text'])
        page_data['org_result', 'para_text'] = """The organization name has been set."""
        page_data['org_result', 'show'] = True

    if (('header_text', 'input_text') in call_data) and call_data['header_text', 'input_text']:
        database_ops.set_text('header_text', call_data['header_text', 'input_text'])
        page_data['header_result', 'para_text'] = """The header text has been set."""
        page_data['header_result', 'show'] = True

    if (('home_text', 'input_text') in call_data) and call_data['home_text', 'input_text']:
        database_ops.set_text('home_text', call_data['home_text', 'input_text'])
        page_data['home_result', 'para_text'] = """The home page text has been set."""
        page_data['home_result', 'show'] = True



#############################################################
#
# Uploads a new image file and gives it name site_image.jpg
#
#############################################################

def upload_site_image(skicall):
    "Uploads an image file"

    call_data = skicall.call_data
    page_data = skicall.page_data

    # Called by responder ????

    if (('site_image','action') not in call_data) or (not call_data['site_image','action']):
        raise FailPage("Invalid file.", widget = 'site_image' )

    servedfiles_dir = cfg.get_servedfiles_directory()

    site_image = os.path.join(servedfiles_dir, 'public_images', 'site_image.jpg')
    site_image_bak = os.path.join(servedfiles_dir, 'public_images', 'site_image_bak.jpg')

    # if backup file exists, delete it
    if os.path.isfile(site_image_bak):
        os.remove(site_image_bak)

    # move file site_image to site_image_bak
    if os.path.isfile(site_image):
        os.rename(site_image, site_image_bak)

    try:
        image_file = call_data['site_image','action']
        # save uploaded file as site_image
        with open(site_image, "wb") as f:
            f.write(image_file)
    except:
        # recover backup file
        try:
            if os.path.isfile(site_image):
                os.remove(site_image)
            # move backup back
            if os.path.isfile(site_image_bak):
                os.rename(site_image_bak, site_image)
        except:
            pass
        raise FailPage('Image load failed.', widget = 'site_image')

    page_data['showresult', 'para_text'] = """The site image has been installed
and will be displayed on the public home page."""
    page_data['showresult', 'show'] = True


def set_test_mode(skicall):
    "Sets or unsets the test mode"
    if skicall.call_data["booked_user_id"] is not None:
        # the current slot is booked, no test mode functionality is available
        return

    # check test mode
    if skicall.call_data["test_mode"]:
        # This user has test mode, so remove it
        if redis_ops.delete_test_mode(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn")):
            skicall.call_data["test_mode"] = False
            skicall.page_data['teststatus', 'show'] = True
            skicall.page_data['teststatus', 'para_text'] = "Test Mode Disabled"
        return

    # so the request is to get test mode, however another admin may have it

    user_id = redis_ops.get_test_mode_user(skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
    if user_id is None:
        # No other admin has test mode, so it can be set
        if redis_ops.set_test_mode(skicall.call_data['user_id'], skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn")):
            # this user has been set with test mode
            skicall.call_data["test_mode"] = True
            # This sets the control user, and resets the chart view
            redis_ops.set_control_user(skicall.call_data['user_id'], skicall.proj_data.get("rconn_0"), skicall.proj_data.get("rconn"))
        else:
            skicall.page_data['teststatus', 'show'] = True
            skicall.page_data['teststatus', 'para_text'] = "Failed to set test mode"





