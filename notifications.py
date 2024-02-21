'''
Created on 26 Nov 2017

@author: Alex Apostolakis

Class for handling notifications
'''
# Import smtplib for the actual sending function
import smtplib
import traceback
import psycopg2
import psycopg2.extras
import json
from datetime import datetime
from datetime import timedelta
import os

# Import the email modules we'll need
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


class notification(object):
    
    ''' Notification engine class '''

    def __init__(self,env,log=None):
        self.env=env
        self.log=log


    def send_email(self,title, message, recipient, attachments=None):
        ''' Send email '''

        try:
            if not attachments:
                msg = MIMEText(message,'plain','UTF-8')
            else:
                msg = MIMEMultipart()
                msg.attach(MIMEText(message))

            sender='GeoHub'
            msg['Subject'] = title
            msg['From'] = sender
            msg['To'] = recipient
            
            for f in attachments or []:
                with open(f, "rb") as fil:
                    part = MIMEApplication(fil.read(), Name=os.path.basename(f))
                # After the file is closed
                part['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(f)
                msg.attach(part)
            
            s = smtplib.SMTP(self.env.smtphost+":"+self.env.smtpport)
            s.starttls()  
            s.login(self.env.smtpuser, self.env.smtppass)
            s.sendmail(sender, [recipient], msg.as_string())
            s.quit()
            
        except:
            if self.log:
                self.log.error('Unable to send email:'+traceback.format_exc())
            raise
          
    def send_notification(self, group, messtype, message,titlesuf='', titlepref='', attachments=[]):
        
        ''' Send notification to the right recipients '''

        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            sql="select * from users where registered=true"
            curs.execute(sql)
            user=curs.fetchone()
            while user:
                notifdict=json.loads(user['notifications'])
                recipient=user['email']
                if group in notifdict and messtype in notifdict[group] and user['registered']:
                    _titlesuf=' : '+titlesuf if titlesuf else titlesuf
                    self.send_email(titlepref+" ["+group+","+messtype+"]"+_titlesuf, message, recipient, attachments)
                user=curs.fetchone()
            curs.close()
        except:
            if self.log:
                self.log.error('Send Notification error:'+traceback.format_exc())
            curs.close()
            raise

class alerts(object):
    
    ''' Alert engine Class '''
    
    def __init__(self,env,log=None,dictfile=None):
        self.env=env
        self.log=log
        self.group='ALERT'
        try:
            if not dictfile:
                self.dictfile=os.path.join(self.env.logs,'alerts.json')
            else:
                self.dictfile=dictfile
            if not os.path.isfile(self.dictfile):
                self.saveAlerts({'alerts':[]})
            self.alertdict=self.loadAlerts()
            self.alerts=self.alertdict['alerts']
            self.notif=notification(env,log)
        except:
            if log:
                self.log.error('Error in initialize alerts'+traceback.format_exc())
        
    def saveAlerts(self,alertsdict):
        ''' Serialize Alerts '''
        
        try:
            with open(self.dictfile, 'w') as fp:
                json.dump(alertsdict, fp, cls=DateTimeEncoder)
                fp.close()
        except:
            if self.log:
                self.log.error('Error saving alerts file'+traceback.format_exc())

            
    def loadAlerts(self):
        
        ''' Deserialize Alerts '''
 
        try:
            if os.path.isfile(self.dictfile):
                with open(self.dictfile) as f:
                    alertdict = json.load(f)
                    return alertdict
            else:
                self.log.error('Alerts file %s do not exists'%self.dictfile)
                raise
        except:
            if self.log:
                self.log.error('Error reading alerts file'+traceback.format_exc())
        

    def alert_on(self, messtype, message,titlesuf, titlepref='', replay = 60, logalert = True):
        
        ''' Notify for alert, append if new or update if changed '''
        
        _newalert={'messtype':messtype, 'message':message,'titlesuf':titlesuf, 'titlepref':titlepref, 'replay':replay, 'logalert' : logalert}
        
        #append new alert to list
        if len(filter(lambda alert: alert['titlesuf'] == titlesuf, self.alerts))==0:
            lastnotif=datetime.now()-timedelta(minutes=replay+1)
            _newalert['lastnotif']=lastnotif.isoformat()
            self.alerts.append(_newalert)
            self.saveAlerts(self.alertdict)
        
        _alert=filter(lambda alert: alert['titlesuf'] == titlesuf, self.alerts)[0]
        
        #check if alert params are updated
        savedict=False
        prmkeys=[k for k in _alert if k!='lastnotif']
        for key in prmkeys:
            if _alert[key]!=_newalert[key]:
                _alert[key]=_newalert[key]
                savedict=True
        self.saveAlerts(self.alertdict) if savedict else None
        
        #notify for alert
        if datetime.now()-datetime.strptime(_alert['lastnotif'][:19], '%Y-%m-%dT%H:%M:%S')>timedelta(minutes=_alert['replay']):
            self.notif.send_notification(self.group, messtype, message,'ON:'+titlesuf, titlepref)
            if logalert and self.log:
                self.log.info('ALERT ON: %s',message)
            _alert['lastnotif']=datetime.now().isoformat()
            self.saveAlerts(self.alertdict)
                
        self.alert_auto_clean()
      
    def alert_off(self, titlesuf, silent = False):
        
        ''' Notify for alert off, remove from list '''

        alertsoff=filter(lambda alert: alert['titlesuf'] == titlesuf, self.alerts)
        if len(alertsoff)>0:
            alertoff=alertsoff[0]
            if not silent:
                self.notif.send_notification(self.group, alertoff['messtype'], alertoff['message'],'OFF:'+alertoff['titlesuf'], alertoff['titlepref'])
            if alertoff['logalert'] and self.log:
                self.log.info('ALERT OFF: %s',alertoff['message'])
            for _alertoff in alertsoff:
                self.alerts.remove(_alertoff)
            self.saveAlerts(self.alertdict)
            
    def alert_auto_clean(self):
        
        ''' Auto-clean long time saved alerts '''
        
        for _alert in self.alerts:
            if datetime.now()-datetime.strptime(_alert['lastnotif'][:19],'%Y-%m-%dT%H:%M:%S')>timedelta(minutes=2*_alert['replay']+1):
                self.alert_off(_alert['titlesuf'],True)
            
class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)
        

