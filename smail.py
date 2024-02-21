'''
Created on 26 Nov 2017

@author: arcgisadmin
'''
# Import smtplib for the actual sending function
import smtplib
import traceback

# Import the email modules we'll need
from email.mime.text import MIMEText


# Create a text/plain message
msg = MIMEText("test")

me='a.apostolakis@yahoo.gr'
you='alex.apostolakis@technocontrol.gr'
# me == the sender's email address
# you == the recipient's email address
msg['Subject'] = 'test title'
msg['From'] = me
msg['To'] = you

# Send the message via our own SMTP server, but don't include the
# envelope header.
try:
    s = smtplib.SMTP('mail.technoesis.gr')
    s.login("smtp@technoesis.gr", "sent1nell0c0s")
    s.sendmail(me, [you], msg.as_string())
    s.quit()
except:
    traceback.print_exc()
    print "Error: unable to send email"
