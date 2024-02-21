'''
Created on 11 Aug 2018

Contains class with methods to handle autoifg API commands
@author: Alex Apostolakis
'''

from ftplib import FTP, all_errors
import traceback
import requests
import json
from serviceevent import servicerequest
import os
import re

class ApiCommand(object):
    def __init__(self,env,log):
        '''
        Initiates environment and log 
        '''
        self.env=env
        self.log=log
        
    def getFTPfile(self, ftpdomain, user, password, folder, filename):
        '''
        gets file from FTP server
        '''

        try:
            ftp = FTP(ftpdomain)     
            ftp.login(user,password)
            ftp.cwd(folder)
            with open( self.env.configpath, 'wb' ) as f :
                ftp.retrbinary('RETR %s' % filename, f.write)
                f.close()
            ftp.close()
        except:
            raise
            return
            
    def readCommand(self):
        '''
        read API command from FTP server
        '''

        sess=requests.session()

        try:
            uri=self.env.webAPIdomain+'/manageevent.php?login=Sam&command=getcommand'
            response=sess.get(uri)
            if response.status_code==200: 
                return json.loads(response.content)
            else:
                return None
            
        except:
            errmess="http request to server %s failed:\n"%self.env.webAPIdomain+traceback.format_exc()
            self.log.warning(errmess)  
            return None
    
    def executeCommand(self):
        try:
            cmd = self.readCommand()
            if not cmd or not cmd['login'].upper()==(re.sub('\W+','', self.env.rootpath)).upper():
                return
            event=servicerequest(self.env)
            if cmd['command']=='start':
                sids=event.get_service_ids(self.env.EV_DETECTED)
                if int(cmd['service_id']) in sids:
                    event.set_service(self.env.EV_DETECTED, int(cmd['service_id']), initlog=False, smartlog=self.log)
                    event.update_service(self.env.EV_NEW)
                    self.log.info("Executed command to Start Service : %s"%cmd['service_id'])
                sids=event.get_service_ids(self.env.EV_PAUSED)
                if int(cmd['service_id']) in sids:
                    event.set_service(self.env.EV_PAUSED, int(cmd['service_id']), initlog=False, smartlog=self.log)
                    event.update_service(self.env.EV_PROCESS)
                    self.log.info("Executed command to Start Service : %s"%cmd['service_id'])
            elif cmd['command']=='pause':
                sids=event.get_service_ids(self.env.EV_PROCESS)
                if int(cmd['service_id']) in sids:
                    event.set_service(self.env.EV_PROCESS, int(cmd['service_id']), initlog=False, smartlog=self.log)
                    event.update_service(self.env.EV_PAUSED)
                    self.log.info("Executed command to Pause Service : %s"%cmd['service_id'])
        except:
            self.log.warning('webAPI command failed:\n'+traceback.format_exc())
    


 

