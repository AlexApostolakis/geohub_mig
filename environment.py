'''
Created on 11 Oct 2017

@author: alex
'''

import sys
import traceback
import os
import ConfigParser
import logging
import json
import psycopg2
import select
from datetime import datetime
from distutils.util import strtobool

class Environment(object):
    
    def __init__(self, openconn=True):

        self.DEBUG=True if os.environ.has_key("GEOHUBDEBUG") else False
        self.inipath=os.getcwd() if not os.environ.has_key("GEOHUBROOT") else os.path.join(os.environ['GEOHUBROOT'],"config")
        self.Config = ConfigParser.ConfigParser()
        self.mglog=None
        try:
            self.Config.read(self.inipath+"/ifgconfig.ini")
    
            Paths=self.ConfigSectionMap("Paths")
            self.rootpath=os.environ['GEOHUBROOT'] if os.environ.has_key("GEOHUBROOT") else Paths['rootpath']
            self.rootpath=self.rootpath+os.sep if self.rootpath[-1]!=os.sep else self.rootpath

            self.configpath=self.rootpath+Paths['configpath']
            self.datapath=self.rootpath+Paths['datapath']
            self.eventsdir = Paths['datapath']
            self.sentinel1path=self.rootpath+Paths['sentinel1path']
            self.logs=self.rootpath+Paths['logs']
            self.processlog=Paths['processlog']
            self.processed_trigger=self.rootpath+Paths['processed']
            self.orbitspath=self.rootpath+Paths['orbits']
            self.sentinelunzip=Paths['sentinelunzip']
            
            
            Filenames=self.ConfigSectionMap("Filenames")
            
            self.eventfile=Filenames['eventfile']
            self.stopfile=Filenames['stopfile']
            self.runfile=Filenames['runfile']
            self.idl_pathconfig=Filenames['idl_pathconfig']
            self.idl_configini=Filenames['idl_configini']
            self.idl_python_config=Filenames['idl_python_config']
            
            if openconn:
                self.conn = Connections(self.ConfigSectionMap("dbconnection"))
            
            Copernicushubs=self.ConfigSectionMap("Copernicushubs")
            #hubs=Copernicushubs['hubs']
            i=1;self.colhubs=[]
            hubskey='hubs'+str(i)
            while hubskey in Copernicushubs:
                print(json.loads(Copernicushubs[hubskey]))
                self.colhubs+=json.loads(Copernicushubs[hubskey])
                i+=1
                hubskey='hubs'+str(i)

            #self.colhubs=json.loads(hubs)
            #self.orbitshub=Copernicushubs['orbitshub']
            States=self.ConfigSectionMap("Status")
            self.EV_NEW=States['ev_trigger']
            self.EV_READY=States['ev_ready']
            self.EV_PROCESS=States['ev_process']
            self.EV_RESET=States['ev_reset']
            self.EV_DETECTED=States['ev_detected']
            self.EV_PAUSED=States['ev_paused']

            
            self.OUT_STATUS_SEARCHING=States['out_searching']
            self.OUT_STATUS_NEW=States['out_new']
            self.OUT_STATUS_PROCESSING=States['out_processing']
            self.OUT_STATUS_READY=States['out_ready']
            self.OUT_STATUS_ARCHIVING=States['out_archiving']
            self.OUT_STATUS_ARCHIVED=States['out_archived']
            self.OUT_STATUS_DELETED=States['out_deleted']
            self.OUT_OFF_LINE_SATUSES=[self.OUT_STATUS_ARCHIVING, self.OUT_STATUS_ARCHIVED, self.OUT_STATUS_DELETED]

            self.INP_STATUS_SEARCHING=States['inp_searching']
            self.INP_STATUS_NEW=States['inp_new']
            self.INP_STATUS_DOWNLOADING=States['inp_downloading']
            self.INP_STATUS_AVAILABLE=States['inp_available']
            
            self.STEP_STATUS_WAIT=States['step_wait']
            self.STEP_STATUS_PROCESSING=States['step_processing']
            self.STEP_STATUS_COMPLETED=States['step_completed']
            self.STEP_STATUS_FAILED=States['step_failed']
            self.STEP_STATUS_RESET=States['step_reset']
            self.STEP_STATUS_KILL=States['step_kill']
            self.STEP_STATUS_CANCEL=States['step_cancel']
            self.STEP_STATUS_PROCESS_STARTED=States['step_procrunning']
            self.STEP_STATUS_ARCHIVING=States['step_archiving']
            self.STEP_STATUS_ARCHIVED=States['step_archived']

 
            self.logger=None
            
            ifgservice=self.ConfigSectionMap("IFG service")
            self.ifg_pastperiod=int(ifgservice['pastperiod'])
            self.ifg_searchperiods=int(ifgservice['searchperiods'])
            self.ifg_searchmaxperiods=int(ifgservice['maxsearchperiods'])
            self.ifg_repassing=int(ifgservice['repassing'])
            self.ifg_filters=ifgservice['filters']
            self.ifg_tilesearchrange=int(ifgservice['tilesearchrange'])
            self.ifg_paircondition=ifgservice['paircondition']
            self.ifg_masterroipercent=float(ifgservice['masterroipercent'])
            self.ifg_inpsplit=ifgservice['inpsplit'].strip()
            self.ifg_checkslow=int(ifgservice['checkslow'])
            self.ifg_checkfast=int(ifgservice['checkfast'])
            self.ifg_fastsearchperiod=int(ifgservice['fastsearchperiod'])

            #parameters
            self.ifg_pathmaster=ifgservice['pathmaster']
            self.ifg_pathslave=ifgservice['pathslave']
            self.ifg_filemaster=ifgservice['filemaster']
            self.ifg_fileslave=ifgservice['fileslave']
            self.ifg_pathorbitmaster=ifgservice['pathorbitmaster']
            self.ifg_fileorbitmaster=ifgservice['fileorbitmaster']
            self.ifg_pathorbitslave=ifgservice['pathorbitslave']
            self.ifg_fileorbitslave=ifgservice['fileorbitslave']
            self.ifg_pathDEM=ifgservice['pathdem']
            self.ifg_pathIFG=ifgservice['pathifg']
            self.ifg_configXML=ifgservice['configxml']
            self.ifg_xmlprofile=ifgservice['xmlprofile']
            self.ifg_defaultxmlprofile=ifgservice["defaultxmlprofile"]
            self.ifg_masterid=ifgservice['masterid']
            self.ifg_slaveid=ifgservice['slaveid']
            self.ifg_outputid=ifgservice['outputid']
            self.ifg_pathuncompressed=ifgservice['pathuncompressed']
            self.ifg_publish=ifgservice['publish']
            self.ifg_eventid=ifgservice['eventid']
            
            types=self.ConfigSectionMap("Types")
            self.OUT_TYPE_IFG=types['out_ifg']
            
            resources=self.ConfigSectionMap("Resources")
            self.res_procnum=json.loads(resources['procnum'])
            self.max_res_priority={}
            for resname, priorities in self.res_procnum.items() :
                self.max_res_priority[resname]=int(max(priorities.keys()))
            self.killproc=strtobool(resources['killproc'])
            self.stepretries=int(resources['stepretries'])
            self.bestdownloadbytes=int(resources['bestdownloadbytes'])
            self.slowdownloadbytes=int(resources['slowdownloadbytes'])
            self.slowdownloadtime=int(resources['slowdownloadtime'])
            self.mediumdownloadbytes=int(resources['mediumdownloadbytes'])
            self.mediumdownloadtime=int(resources['mediumdownloadtime'])

            notifications=self.ConfigSectionMap("Notifications")
            self.smtphost=notifications['smtphost']
            self.smtpuser=notifications['smtpuser']
            self.smtppass=notifications['smtppass']
            self.smtpport=notifications['smtpport']

            events=self.ConfigSectionMap("Event")
            self.minmagnitude=float(events['minmagnitude'])
            self.minmagnitudegreece=float(events['minmagnitudegreece'])
            self.minmagnitudeworld=float(events['minmagnitudeworld'])
            self.eventpastrange=int(events['eventpastrange'])
            self.eventfileprefix=events['eventfileprefix']
            self.rectcornerdist=int(events['rectcornerdist'])
            self.eventcheckinterval=int(events['checkinterval'])
            self.autostartpastdays=int(events['autostartpastdays'])

            archive=self.ConfigSectionMap("Archive")
            self.freespacetrigger=int(archive['freespacetrigger'])
            self.freespacelimit=int(archive['freespacelimit'])
            self.oldnesstrigger=int(archive['oldnesstrigger'])
            self.archiveroot=os.environ['GEOHUBARCHROOT'] if os.environ.has_key("GEOHUBARCHROOT") else archive['archiveroot']
            self.archiveroot=self.archiveroot+os.sep if self.archiveroot[-1]!=os.sep else self.archiveroot
            self.lowstoragealertinterval=int(archive['lowstoragealertinterval'])
            self.deletearchiveddays=int(archive['deletearchiveddays'])
            
            publishing=self.ConfigSectionMap("Publishing")
            self.publishfolder=os.environ['PUBLISHROOT'] if os.environ.has_key("PUBLISHROOT") else publishing['publishfolder']
            self.publishfolder=self.publishfolder+os.sep if self.publishfolder[-1]!=os.sep else self.publishfolder
            self.pub_highres_ifg = publishing['highres_ifg']
            self.pub_humbnail = publishing['thumbnail']
            self.pub_kml = publishing['kml']
            self.pub_lowres_ifg = publishing['lowres_ifg']
            #self.ftpdomain = publishing['ftpdomain']
            #self.ftpfolder = publishing['ftpfolder']
            #self.ftpuser = publishing['ftpuser']
            #self.ftppass = publishing['ftppass']
            #self.ftpfiles = strtobool(publishing['ftpfiles'])
            #self.copyfiles = strtobool(publishing['copyfiles'])
            #self.skiplargeftp = strtobool(publishing['skiplargeftp'])
            self.publishpreviewpage = publishing['publishpreviewpage']
            #self.webinterfacedb = eval(publishing['webinterfacedb'])

            i=1;self.ftppublishers=[]
            ftpskey='ftp'+str(i)
            while ftpskey in publishing:
                self.ftppublishers+=json.loads(publishing[ftpskey])
                i+=1
                ftpskey='ftp'+str(i)
            
            webAPI=self.ConfigSectionMap("webAPI")
            self.webAPIdomain = webAPI['webapidomain']
            self.webAPIstart = webAPI['webapistart']
            self.webAPIpause = webAPI['webapipause']
            self.webAPItimeinterval = int(webAPI['webapitimeinterval'])
            
            Debug=self.ConfigSectionMap("Debug")
            self.debugservice = eval(Debug['debugservice'])
            self.debugmanage = eval(Debug['debugmanage'])
            
            #globals
            self.hubnotif=None
            self.hubmess=None
            self.orbitnotif=None
            self.eventerrornotif=None
            
            self.process_stop_mess='Process Stopped'
            self.process_start_mess='Process Start'
            
            os.environ['PYTHONWARNINGS']="ignore:Unverified HTTPS request"
 
        except:
            print 'Configuration Missing. Exiting...'
            traceback.print_exc()
            sys.exit()

        
    def ConfigSectionMap(self,section):        
        confdict = {}
        options = self.Config.options(section)
        for option in options:
            try:
                confdict[option] = self.Config.get(section, option)
                #if confdict[option] == -1:
                    #DebugPrint("skip: %s" % option)
            except:
                print 'Configuration Missing. Exiting...'
                sys.exit()
                #confdict[option] = None
        return confdict
            

class Connections(object):
    def __init__(self, connargs):
        
        self.pg_dbname=os.environ['GEOHUBDB'] if os.environ.has_key("GEOHUBDB") else connargs['pg_dbname']
        self.pg_user=connargs['pg_user']
        self.pg_password=connargs['pg_password']
        self.pg_host=connargs['pg_host']
        self.pg_port=connargs['pg_port']
        
        self.postgr = psycopg2.connect(dbname=self.pg_dbname,
                                    user=self.pg_user,
                                    password=self.pg_password,
                                    host=self.pg_host, 
                                    port=self.pg_port)        
    '''
        self.postgr_a = psycopg2.connect(dbname=self.pg_dbname,
                                    user=self.pg_user,
                                    password=self.pg_password,
                                    host=self.pg_host, 
                                    port=self.pg_port,
                                    async=1)
    
    def wait(self):
        conn=self.postgr_a
        while 1:
            state = conn.poll()
            if state == psycopg2.extensions.POLL_OK:
                break
            elif state == psycopg2.extensions.POLL_WRITE:
                select.select([], [conn.fileno()], [])
            elif state == psycopg2.extensions.POLL_READ:
                select.select([conn.fileno()], [], [])
            else:
                raise psycopg2.OperationalError("poll() returned %s" % state)  
    '''
