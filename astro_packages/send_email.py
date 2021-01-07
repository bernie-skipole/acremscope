
####################################################
#
# Consists of the sendmail function which allows the server to send an email
#
# Please note: the function may need to be directly edited
# if not compatible with the servers ISP mail service
#
####################################################


import smtplib
from email.mime.text import MIMEText

from . import database_ops



def sendmail(email, subject, message):
    "Sends an email, return True on success, False failure"

    # get smtpserver, no_reply and starttls from database for the smtp server
    smtpserversettings = database_ops.get_emailserver()
    if not smtpserversettings:
        return False
    smtpserver, no_reply, starttls = smtpserversettings

    # get username and password from database for the smtp server
    emailuserpass = database_ops.get_emailuserpass()

    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = no_reply
        msg['reply-to'] = no_reply
        msg['To'] = email
        s = smtplib.SMTP(smtpserver)
        if emailuserpass:
            if starttls:
                s.ehlo()
                s.starttls()
            s.login(*emailuserpass)
        s.sendmail(no_reply, [email], msg.as_string())
        s.quit()
    except:
        return False
    return True
