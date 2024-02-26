'''

Copyright (C) Alex Apostolakis - All Rights Reserved
Written by Alex Apostolakis a.apostolakis@yahoo.gr, alex.apostolakis@technoesis.gr,  April 2017

This file contain the class that initiates the service and searches for the Interferogram pairs

The service requests are started based on the event information files that are located in the confiuration folder.
There are of two possible formats: The automated event detection system or the python-qgis interface.
The user in order to create a custom service request that does not come from either the detection system or the Qgis interface 
can manually create an event information file of either format.  


@author: Alex Apostolakis 
'''

from datetime import datetime, timedelta
import geomtools
import traceback
import os
import logging
import psycopg2
import psycopg2.extras
from searchimages import ProductTracer, dbProduct
from shutil import copyfile
import operator
from osgeo import gdal, ogr, osr
import json
import requests
from requests import packages
import re
import time
from step_utils import steputils as su
from notifications import notification
from logs import applog
from fileutils import fileutils
from base64 import b64decode
from shapely import wkt
import math
#import urllib3

class servicerequest:
    '''
    It initiates the service, searches for the Interferogram pairs, creates service metadata
    '''
    def __init__(self,env):
        '''
        initiates environment and class scope variables
        '''
        self.env=env
        self.inputid='id'
        self.dbinputid='product_id'
        self.pairtypes={'1 co-seismic': 'i1.sensing_start<=coalesce(i2.sensing_start,i1.sensing_start)', '2 pre-seismic':'i1.sensing_start>coalesce(i2.sensing_start,i1.sensing_start)'}
        self.log=None
        self.alog=applog(env)
        self.sn=None
        self.systemlog=None
        #urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def insert_event(self,eventregion,eventdatest,status,rect_wkt2D,request_params,systemlog,magnitude=None, epicenter=None, depth=None):
        '''
        inserts event in service_request table
        '''
        curs = self.env.conn.postgr.cursor()
        try:            
            now=datetime.now()

            mag_st1=mag_st2=epi_st1=epi_st2=depth_st1=depth_st2=""
            if not magnitude is None:
                mag_st1=",magnitude"
                mag_st2=",%s"%magnitude
            if not epicenter is None:
                epi_st1=",epicenter"
                epi_st2=",'%s'"%epicenter
            if not depth is None:
                depth_st1=",epicenter_depth"
                depth_st2=",'%s'"%depth
            
            sql="insert into service_request (name, date, status,request_date,search_poly,request_params%s%s%s) "%(mag_st1,epi_st1,depth_st1) + \
            "values ('%s', '%s','%s','%s',ST_GeomFromText('%s', 4326), '%s'%s%s%s)"\
            %(eventregion.replace("'","''"),eventdatest,status,now,rect_wkt2D,request_params,mag_st2,epi_st2,depth_st2)
            curs.execute(sql)
            self.env.conn.postgr.commit()
            sql="select max(id) from service_request"
            curs.execute(sql)
            midrec = curs.fetchone()
            return midrec[0]
        except:
            #traceback.print_exc()
            systemlog.warning("Insert new event failed:\n"+traceback.format_exc())
        curs.close()
        
        
    def update_event(self, eventregion,eventdatest,rect_wkt2D,request_params,systemlog,magnitude=None, epicenter=None, depth=None, id=None):
        '''
        updates event in service_request table
        '''
        curs = self.env.conn.postgr.cursor()
        try:            
            now=datetime.now()
            
            qid=json.loads(request_params)['qid']
            mag_st1=mag_st2=epi_st1=epi_st2=depth_st1=depth_st2=""
            if not magnitude is None:
                mag_st1=",magnitude=%s"%magnitude
            if not epicenter is None:
                epi_st1=",epicenter='%s'"%epicenter
            if not depth is None:
                depth_st1=",epicenter_depth='%s'"%depth
                
            if id:
                where=" where id=%d"%id
            else:
                where=" where request_params::json->>'qid'='%s'"%qid
            
            sql="update service_request set name='%s', date='%s', request_date='%s',search_poly=ST_GeomFromText('%s', 4326), request_params='%s'%s%s%s"\
            %(eventregion.replace("'","''"),eventdatest,now,rect_wkt2D,request_params,mag_st1,epi_st1,depth_st1)+where

            curs.execute(sql)
            self.env.conn.postgr.commit()
            return self.event_exists(qid, systemlog)
        except:
            #traceback.print_exc()
            systemlog.warning("Update new event failed:\n"+traceback.format_exc())
        curs.close()
    
    def get_event_record(self, qid=None, id=None):
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if qid:
            sql = "select * from service_request where request_params::json->>'qid'='%s'"%qid
        elif id:
            sql = "select * from service_request where id=%d"%id
        curs.execute(sql)
        rec = curs.fetchone()
        return rec
    
    def automatic_event_start(self, systemlog):
        point = ogr.CreateGeometryFromWkt(self.sr['epicenter'])
        inland, distfromland = geomtools.geomtools.point_inland_check(point)
        try:
            depth = self.sr['epicenter_depth'] if self.sr['epicenter_depth']>1.0 else 1.0
            magdepthcoef = ((self.sr['magnitude']-self.env.minmagnitudeworld)*11+self.env.minmagnitudeworld)/depth
            if inland and self.sr['magnitude']>5.5 and magdepthcoef>=0.5:
                self.update_service(self.env.EV_NEW)
                mess="Detected event meets criteria for processing. Automatic processing start for event: \n\n"
                mess+=self.event_properties_message(self.sr['name'], '%s'%self.sr['date'], self.sr['magnitude'], self.sr['epicenter_depth'], self.sr['epicenter'])
                title="%s - %s"%(self.sr['name'], self.sr['date'])
                self.sn.send_notification("event","autostart",mess,title)
                return True
            else:
                return False
        except:
            systemlog.error("Event auto start check failed:\n"+traceback.format_exc())
            return False

    def event_exists(self, qid, systemlog):
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql = "select count(*) c from service_request where request_params::json->>'qid'='%s'"%qid
        try:
            curs.execute(sql)
            rec = curs.fetchone()
            if rec["c"]==0:
                return None
            sql = "select * from service_request where request_params::json->>'qid'='%s'"%qid
            curs.execute(sql)
            rec = curs.fetchone()
            if rec is not None:
                id=rec["id"]
            else:
                id=None
        except:
            systemlog.warning("Fail to search for event with qid %s:\n"%qid+traceback.format_exc())
            id=None
        curs.close()
        return id
    
    def move_trigger(self,eventpath,eventfile,eventregion,eventdate, systemlog, newevent = False):
        
        '''
        moves trigger file to processed location
        '''

        try:            
            if not os.path.exists(self.env.processed_trigger):
                os.makedirs(self.env.processed_trigger)
            eventfname=os.path.join(eventpath,eventfile)
            proc_eventfname=self.env.processed_trigger+os.path.splitext(eventfile)[0]+"_"+self.get_eventname(eventregion,eventdate)+os.path.splitext(eventfile)[1]
            if not newevent and os.path.exists(proc_eventfname):
                copyfile(proc_eventfname, os.path.join(os.path.dirname(proc_eventfname),"old_"+os.path.basename(proc_eventfname)))
            copyfile(eventfname,proc_eventfname)
            os.remove(eventfname)
        except:
            #traceback.print_exc()
            systemlog.error("Trigger file move failed:\n"+traceback.format_exc())
            raise

    def init_trigger(self,systemlog):
        
        '''
        Initiates a service in 'requested' status from trigger file from python-qgis interface 
        '''

        self.ok=False
        self.log=None
        
        try:
            eventparams=self.get_eventparams()
            
            if eventparams:
                eventregion=eventparams[0]
                eventdatest=eventparams[1]
                eventdate=datetime.strptime(eventdatest, '%Y-%m-%d %H:%M:%S')
                
                rectcorners=[]
                for i in range(2,4):
                    p=[float(x) for x in eventparams[i].translate(None, "()").split(',')]
                    rectcorners.append(p)
                rect_coords=geomtools.geomtools.rectangle_coords(rectcorners[0],rectcorners[1])
                rect_wkt, rect= geomtools.geomtools.create_polygon(rect_coords)
                rect.FlattenTo2D()
                rect_wkt2D=rect.ExportToWkt()
                
                request_params_dict = {}
                request_params_dict[self.env.ifg_xmlprofile]=eventparams[4]
                request_params_dict['pastperiod']=self.env.ifg_pastperiod
                request_params_dict['repassing']=self.env.ifg_repassing
                request_params=json.dumps(request_params_dict)
    
                #insert event in event table
                self.insert_event(eventregion,eventdatest,self.env.EV_NEW,rect_wkt2D,request_params,systemlog)
                
                #create event folder
                try:
                    eventfolder=self.get_eventfolder(eventregion,eventdate)            
                    #eventfolder=self.env.datapath+self.eventregion+"_"+datetime.strftime(eventdate, "%Y%m%d%H%M%S")
                    if not os.path.exists(eventfolder):
                        os.makedirs(eventfolder)
                except:
                    systemlog.warning("Event folder creation error:\n"+traceback.format_exc())
                    raise
                
                #init event log
                if not self.log:
                    self.openlog(eventfolder)
                self.ok=True

                #move trigger file
                self.move_trigger(self.env.configpath,self.env.eventfile,eventregion,eventdate,systemlog)
        except:
            systemlog.warning("Trigger Event initiation failed:\n"+traceback.format_exc())
            raise
    
    def get_detected_AOI(self,wktpoint, rectcornerdist=None):
        
        '''
        Creates a rectangle around the event point 
        '''
        #km/long deg (2*pi/360) * r_earth * cos(theta)
        #km/lat deg 111
        newlat = 0.0089
        rectcornerdist=self.env.rectcornerdist if not rectcornerdist else rectcornerdist
        #WKTexp, geom=geomtools.geomtools.convert_geom(wktpoint, 4326, meterEPSG)
        geom = ogr.CreateGeometryFromWkt(wktpoint)
        dlat = rectcornerdist*0.0000089
        dlong =  rectcornerdist*0.0000089 / math.cos(geom.GetPoint(0)[1] * 0.018)

        leftcorner = ogr.Geometry(ogr.wkbPoint)
        leftcorner.AddPoint(geom.GetPoint(0)[0]-dlong, geom.GetPoint(0)[1]-dlat)
        #lcWKT, leftcorner=geomtools.geomtools.convert_geom(leftcorner_xy.ExportToWkt(),meterEPSG, 4326)
        rightcorner = ogr.Geometry(ogr.wkbPoint)
        rightcorner.AddPoint(geom.GetPoint(0)[0]+dlong, geom.GetPoint(0)[1]+dlat)
        #rcWKT, rightcorner=geomtools.geomtools.convert_geom(rightcorner_xy.ExportToWkt(),meterEPSG, 4326)
        rect_coords=geomtools.geomtools.rectangle_coords(leftcorner.GetPoint(0),rightcorner.GetPoint(0))
        rect_wkt, rect= geomtools.geomtools.create_polygon(rect_coords)
        rect.FlattenTo2D()
        return rect    
    
    def formAPICommand(self, command, sid):
        '''
        form API command
        '''

        #//localhost/ifgwebapi/manageevent.php?login=Sam&command=start&service_id=33
        cleanrootpath = re.sub('\W+','', self.env.rootpath )
        return self.env.webAPIdomain + "/manageevent.php?login=%s&command=%s&service_id=%d"%(cleanrootpath,command,sid)
    
    def event_properties_message(self, eventname, eventdatetime, eventmag, eventdepth, eventlocationwkt):
        eventdate=datetime.strptime(eventdatetime, '%Y-%m-%d %H:%M:%S')
        location_geom = ogr.CreateGeometryFromWkt(eventlocationwkt)
        location=location_geom.GetPoint()
        mess="Name: %s\nDate: %s\nMagnitude: %s\nDepth: %s\nLocation: %s ,%s"\
        %(eventname,eventdate,eventmag,eventdepth,location[0],location[1])
        #http://maps.google.com/maps?q=35.128061,-106.535561&ll=35.126517,-106.535131&z=17
        googlelink="http://maps.google.com/maps?q=%s,%s&ll=%s,%s&z=5"%(location[1],location[0],location[1],location[0])
        mess+="\nLink to Google maps: %s"%googlelink
        return mess
 
    def detected_event_notif(self, sid, eventdata, eventdate, newevent, systemlog):
        title="%s - %s"%(eventdata["name"],eventdate)
        if newevent:
            mess="New Event Detected:"+"\n"+'-'*40+"\n"
        else:
            mess="Event Updated:"+"\n"+'-'*40+"\n"
        mess+=self.event_properties_message(eventdata["name"], eventdata["time"], eventdata["magnitude"], eventdata["depth"], eventdata["epicenter"])
        #http://maps.google.com/maps?q=35.128061,-106.535561&ll=35.126517,-106.535131&z=17
        #googlelink="http://maps.google.com/maps?q=%s,%s&ll=%s,%s&z=5"%(location[1],location[0],location[1],location[0])
        #mess+="\nLink to Google maps: %s"%googlelink
        if newevent:
            mess+="\n\nTo start processing the event click on the link below:\n"
            mess+=self.formAPICommand('start', sid)
            mess+="\n\nTo stop the event processing click on the link below:\n"
            mess+=self.formAPICommand('pause', sid)
            mess+="\n\nAlternatively to start processing the event change its status to '%s' from '%s' in service_request table"%(self.env.EV_NEW,self.env.EV_DETECTED)
        notification(self.env,systemlog).send_notification("event","detected",mess,title)
        
    def duplicate_event(self, eventdata):
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql = "select id from service_request where name='%s' and date='%s'"%(eventdata['name'].replace("'", "''"),eventdata['time'])
        curs.execute(sql)
        rec = curs.fetchone()
        if rec is not None:
            return rec['id']
        else:
            return False
        
        
    def init_detected_event(self,eventfname,systemlog):
        
        '''
        Initiates a service in 'detected' status based on automated event detection files 
        '''

        try:
            if not os.path.isfile(eventfname):
                systemlog.error("Detected Event file %s is missing"%eventfname)
                return
            with open(eventfname, "r") as eventfile:
                eventdata_st = eventfile.read()
                eventfile.close()
            eventdata=json.loads(eventdata_st)
            
            rectdist = math.pow((eventdata["magnitude"]-self.env.minmagnitudeworld)*86.5,2)+self.env.rectcornerdist
            rect=self.get_detected_AOI(eventdata["epicenter"],rectdist)
            
            request_params_dict = {}
            request_params_dict[self.env.ifg_xmlprofile]=self.env.configpath+self.env.ifg_defaultxmlprofile
            request_params_dict['pastperiod']=self.env.ifg_pastperiod
            request_params_dict['repassing']=self.env.ifg_repassing
            if 'qid' in eventdata:
                request_params_dict['qid']=eventdata['qid']
            
            #insert event in service_request table
            depth=eventdata["depth"] if "depth" in eventdata else None
            
            dupid=self.duplicate_event(eventdata)
            if "qid" in eventdata and (self.event_exists(eventdata["qid"], systemlog) is not None or dupid):
                if dupid:
                    evrec=self.get_event_record(id=dupid)
                else:
                    evrec=self.get_event_record(qid=eventdata["qid"])
                saved_params=json.loads(evrec['request_params'])
                if not 'init date' in saved_params:
                    request_params_dict['init date']=evrec['date']
                else: request_params_dict['init date']=saved_params['init date']
                if not 'init region' in saved_params:
                    request_params_dict['init region']=evrec['name']
                else: request_params_dict['init region']=saved_params['init region']
                request_params=json.dumps(request_params_dict)
                sid=self.update_event(eventdata["name"],eventdata["time"],rect.ExportToWkt(),request_params,systemlog,\
                              eventdata["magnitude"],eventdata["epicenter"],depth,dupid)
                newevent=False
            else:
                request_params_dict['init date']=eventdata["time"]
                request_params_dict['init region']=eventdata["name"].replace("'","''")
                request_params=json.dumps(request_params_dict)
                sid = self.insert_event(eventdata["name"],eventdata["time"],self.env.EV_DETECTED,rect.ExportToWkt(),request_params,systemlog,\
                              eventdata["magnitude"],eventdata["epicenter"],depth)
                newevent=True
            if sid is None:
                systemlog.error("Fail to get service ID for Event %s %s"%(eventdata["name"],eventdata["time"]))
                return
            #move trigger file to processed
            #eventdate=datetime.strptime(eventdata["time"], '%Y-%m-%d %H:%M:%S')
            eventdate=datetime.strptime(request_params_dict['init date'], '%Y-%m-%d %H:%M:%S')
            #evnamesafe="".join([c for c in eventdata["name"] if re.match(r'\w', c)])
            #self.move_trigger(os.path.split(eventfname)[0]+os.sep,os.path.split(eventfname)[1],eventdata["name"],eventdate,systemlog,newevent)
            self.move_trigger(os.path.split(eventfname)[0]+os.sep,os.path.split(eventfname)[1],request_params_dict['init region'],eventdate,systemlog,newevent)

            request_params_dict['init region']
            '''
            location_geom = ogr.CreateGeometryFromWkt(eventdata["epicenter"])
            location=location_geom.GetPoint()
            '''
            self.detected_event_notif(sid, eventdata, eventdate, newevent, systemlog)
        except:
            systemlog.error("Detected Event initiation failed:\n"+traceback.format_exc())
    
    def init_service(self,systemlog):
        '''
        Initiates service requests in case event information files exist in configuration location
        '''

        self.init_trigger(systemlog)
        for fname in fileutils().find_files(self.env.configpath,self.env.eventfileprefix+'*',"list"):
            self.init_detected_event(fname,systemlog)
        self.systemlog=systemlog
           
           
    def get_eventparams(self):
        '''
        Get parameters from qgis interface file
        '''
        try:
            eventfname=self.env.configpath+self.env.eventfile
            if os.path.isfile(eventfname):
                with open(eventfname, "r") as eventfile: 
                    tmpparams = eventfile.readlines()
                    eventparams=[l.strip('\n\r') for l in tmpparams]
                return eventparams
            else:
                return None
                
        except:
            #self.mglog.warning("Event file problem:\n"+traceback.format_exc())
            raise
            
        return None

    def get_eventfolder(self,eventregion,eventdate):
        '''
        Returns service request processing folder for IFGs
        '''

        return self.env.datapath+self.get_eventname(eventregion,eventdate)
    
    def get_eventname(self,eventregion,eventdate, log = None):
        '''
        Returns the service request safe name for folder.
        '''
        init_eventregion=eventregion
        init_eventdate=eventdate
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql="select * from service_request where name='%s' and date='%s'"%(eventregion,eventdate)
        try:
            curs.execute(sql)
            rs = curs.fetchone()
            nrows=curs.rowcount
            curs.close()
            if nrows>0:
                if 'init region' in rs['request_params']:
                    init_eventregion=json.loads(rs['request_params'])['init region']
                if 'init date' in rs['request_params']:
                    init_eventdate=datetime.strptime(json.loads(rs['request_params'])['init date'], '%Y-%m-%d %H:%M:%S')
        except:
            if log:
                log.warning("Unable to get event from service request table\n"+traceback.format_exc())
        evnamesafe="".join([c for c in init_eventregion if re.match(r'\w', c)])
        return evnamesafe+"_"+datetime.strftime(init_eventdate, "%Y%m%d%H%M%S")
        
    def openlog(self, eventfolder):
        '''
        Creates or initiates the service request log
        '''

        try:
            if not os.path.exists(eventfolder):
                os.makedirs(eventfolder)
            logfname=os.path.join(eventfolder,self.env.processlog+".log")
            formatter=logging.Formatter('%(asctime)s %(levelname)s : %(message)s')
            fileh = logging.FileHandler(logfname, 'a')
            fileh.setFormatter(formatter)
            self.log = logging.getLogger()
            self.log.addHandler(fileh)
            self.log.setLevel(logging.DEBUG)
            logging.getLogger('requests').setLevel(logging.CRITICAL)

        except:
            #traceback.print_exc()
            #self.mglog.error("Event Log file problem:\n"+traceback.format_exc())
            raise
    
    def closelog(self):
        '''
        Closes the service request log
        '''

        if self.log:
            handlers = self.log.handlers[:]
            for handler in handlers:
                handler.close()
                self.log.removeHandler(handler)
                self.log=None
        
    def set_service(self,status, rs_id=None, initlog=True, smartlog=None):
        '''
        Sets the service attributes of the service event class reading them from the service_request table
        '''

        where="and id=%d"%rs_id if rs_id else ""
        sql="select *,ST_AsText(search_poly) as roi from service_request where status like '%s' %s order by request_date"%(status,where)
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            curs.execute(sql)
            self.sr = curs.fetchone()
            nrows=curs.rowcount
            curs.close()
            if nrows>0:
                paramsdict=json.loads(self.sr['request_params'])
                self.sr_pastperiod=paramsdict['pastperiod'] if 'pastperiod' in paramsdict else self.env.ifg_pastperiod
                self.sr_repassing=paramsdict['repassing'] if 'repassing' in paramsdict else self.env.ifg_repassing
                self.sr_mostrecentperiod=self.sr_pastperiod
                if not self.log and initlog:
                    self.openlog(self.get_eventfolder(self.sr['name'], self.sr['date']))
                    self.sn=notification(self.env,self.log)
                else:
                    self.sn=notification(self.env)
                return self.sr['id']
            else:
                return None
        except:
            smartlog.error("Unable to set service:\n"+traceback.format_exc())
            return None
        
    def get_service_ids(self, status, where = None):
        
        '''
        Returns a list with the service request ids of a specific status
        '''

        where =  "" if where is None else " and %s"%where
        sql="select * from service_request where status like '%s' %s order by request_date"%(status,where)
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        curs.execute(sql)
        sr = curs.fetchone()
        sidlist=[]
        while sr:
            sidlist.append(sr['id'])
            sr = curs.fetchone()
        return sidlist
    
    def check_update_service(self):
        
        '''
        Automatically updates service request status and params
        '''
        
        offlinestatuses = "'"+"' ,'".join(self.env.OUT_OFF_LINE_SATUSES)+"'"
        sql="select * from service_output where output_status not in ('%s',%s) and service_id=%d"%\
            (self.env.OUT_STATUS_READY,offlinestatuses,self.sr['id'])
        #sql="select * from steps_execution se join service_output so on se.output_id=so.id join service_request sr on so.service_id=sr.id"+ \
        #" where se.status in ('%s','%s','%s')"%(self.env.STEP_STATUS_PROCESSING,self.env.STEP_STATUS_FAILED, self.env.STEP_STATUS_WAIT)
        curs = self.env.conn.postgr.cursor()
        curs.execute(sql)
        active_outputs = curs.rowcount
        '''
        sql="select count(*) from service_output where service_id=%d"%self.sr['id']
        curs.execute(sql)
        count=curs.fetchone()
        all_outputs = count[0]
        '''
        if active_outputs==0 and self.sr['date']+timedelta(days=self.sr_repassing*self.sr_pastperiod)<datetime.now():
            self.update_service(self.env.EV_READY)
            retval = self.env.EV_READY
        else:
            retval = self.sr['status']
            
        curs.close()
 
        #check update of params
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql="select *,ST_AsText(search_poly) as roi from service_request where id=%d"%(self.sr['id'])
        try:
            curs.execute(sql)
            srtmp = curs.fetchone()
            nrows=curs.rowcount
            if nrows>0:
                if self.sr['request_params']!=srtmp['request_params']:
                    self.update_service(srtmp.sr['request_params'],'request_params')
                    curs.execute(sql)
                    self.sr = curs.fetchone()                
                paramsdicttmp=json.loads(srtmp['request_params'])
                if 'rectcornerdist' in paramsdicttmp:
                    paramsdict=json.loads(self.sr['request_params'])
                    if ('rectcornerdist' not in paramsdict) or ('rectcornerdist' in paramsdict and paramsdict['rectcornerdist']!=paramsdicttmp['rectcornerdist']):
                        self.update_AOI()
        
        except:
            if self.log:
                self.log.error("Unable to check or update service:\n"+traceback.format_exc())
        
        curs.close()
        return retval
    
    def update_AOI(self):
        '''
        Updates service AOI
        '''

        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql="select *,ST_AsText(search_poly) as roi from service_request where id=%d"%(self.sr['id'])
        try:
            curs.execute(sql)
            srtmp = curs.fetchone()
            nrows=curs.rowcount
            if nrows>0:
                paramsdicttmp=json.loads(srtmp['request_params'])
                if 'rectcornerdist' in paramsdicttmp:
                    rect=self.get_detected_AOI(self.sr["epicenter"],paramsdicttmp['rectcornerdist'])
                    self.update_service(rect.ExportToWkb().encode('hex'),'search_poly')
                    curs.execute(sql)
                    self.sr = curs.fetchone()
        
        except:
            self.log.error("Unable to update AOI:\n"+traceback.format_exc())
        curs.close()
    
    def update_service(self,value, field='status'):
        '''
        Updates service request fields
        '''

        curs = self.env.conn.postgr.cursor()
        try:
            if field=='search_poly':
                value="ST_GeomFromWKB(decode('%s','hex'), 4326)"%value
                #value="ST_GeomFromText('%s', 4326)"%value
            else:
                value="'%s'"%value
            sql="update service_request set %s=%s where id=%d"%(field,value,self.sr['id'])
            curs.execute(sql)
            self.env.conn.postgr.commit()
        except:
            raise
        curs.close()
            
    def reset_service(self, sid=None):
        '''
        Reset service by stopping all running service steps and erasing all outputs and steps metadata
        Files created on file system must be deleted manually
        '''

        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if not sid:
            sid=self.sr['id']
        try:
            #sql="select id from service_output where service_id=%d"%sid
            sql="select * from steps_execution se join service_output so on so.id=se.output_id join service_request sr on so.service_id=sr.id where sr.id=%d and se.status in ('%s', '%s', '%s')"\
            %(sid,self.env.STEP_STATUS_PROCESSING, self.env.STEP_STATUS_KILL, self.env.STEP_STATUS_RESET)
            curs.execute(sql)
            if curs.rowcount==0:
                self.log.info("Deleting metadata for outputs and steps for service %d"%sid)
                sql="delete from steps_execution se where exists (select * from service_output so join service_request sr on so.service_id=sr.id where so.id=se.output_id and sr.id=%d)"%sid
                curs.execute(sql)
                sql="delete from service_output where service_id=%d"%sid
                curs.execute(sql)
                sql="update service_request set status='%s' where id=%d"%(self.env.EV_DETECTED,sid)
                curs.execute(sql)
            else:
                self.log.info("Stopping all processing steps for service %d"%sid)
                sql="update steps_execution se set status='%s'"%self.env.STEP_STATUS_KILL+\
                " where exists (select * from service_output so join service_request sr on so.service_id=sr.id where so.id=se.output_id and sr.id=%d and se.status<>'%s')"%(sid,self.env.STEP_STATUS_CANCEL)
                curs.execute(sql)
            self.env.conn.postgr.commit()
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Reset service %d failed:\n%s"%(sid,traceback.format_exc()))
        curs.close()
        
    def store_sat_input(self,entry):
        
        '''
        Store satellite imagery files information to satellite_input table
        '''

        succeed=True
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)

        try:
            sql="select * from satellite_input where product_id='%s'"%entry['id']
            curs.execute(sql)
            if curs.rowcount==0:
                print(entry)
                print(entry.keys())
                orbitfile=self.sat_input_orbit_file(entry)
                orbfilest = "'%s'"%orbitfile if orbitfile else 'NULL'
                sql="insert into satellite_input (product_id, name, sensing_start, sensing_stop, direction, orbit, footprint, status, params, orbit_file) " + \
                "values ('%s','%s','%s','%s','%s','%s','%s','%s','%s',%s)" \
                %(entry['id'],entry['Name'],entry['Sensing start'],entry['Sensing stop'],entry['Pass direction'],entry['Relative orbit'], \
                  entry['WKT footprint'], self.env.INP_STATUS_NEW, json.dumps(entry), orbfilest)
                curs.execute(sql)
                self.env.conn.postgr.commit()
                if self.log:
                    self.log.info("Insert New input. Input Sensing Start: %s"%entry['Sensing start'])
            else:
                satinp=curs.fetchone()
                if not satinp['orbit_file']:
                    orbitfile=self.sat_input_orbit_file(entry)
                    if orbitfile:
                        sql="update satellite_input set orbit_file='%s' where product_id='%s'"%(orbitfile,entry['id'])
                        curs.execute(sql)
                        self.env.conn.postgr.commit()
                        if self.log:
                            self.log.info("Update input orbit file. Input Sensing start: %s"%entry['Sensing start'])
            succeed=True

        except:
            #traceback.print_exc()
            if self.log:
                self.log.info("Insert new satellite input failed:\n"+traceback.format_exc())
            succeed=False
        
        finally:
            curs.close()
            return succeed
        
    def sat_input_orbit_file(self,entry):
        
        '''
        Finds precise orbits file name
        '''
        return None
        sess=requests.session()
        
        sensingstart=datetime.strptime(entry['Sensing start'][:19], '%Y-%m-%dT%H:%M:%S')
        validitystart_gt=(sensingstart-timedelta(minutes=150)).strftime("%Y-%m-%dT%H:%M:%S")
        validitystart_lt=(sensingstart-timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S")

        mission=entry['Name'][0:3]
        orbitfname=None
        messnotfound="Orbit file for '%s' not found"%entry['Name']
        mission_param="sentinel1__mission"
        starttime_param="validity_start__gt"
        endtime_param="validity_start__lt"

        try:
            uri=self.env.orbitshub+'api/v1/?product_type=AUX_RESORB'
            uriwithparams="%s&%s=%s&%s=%s&%s=%s"%(uri,mission_param,mission,starttime_param,validitystart_gt,endtime_param,validitystart_lt)
            response=sess.get(uriwithparams,verify=False)
            if response.status_code==200: 
                resorbs = json.loads(response.content)
                for resorb in resorbs['results']: #scan resorbs for right time range
                    orbitfstart=re.search("V.*_",resorb['physical_name']).group(0)[1:-1]
                    orbitfend=re.search("%s_.*EOF"%orbitfstart,resorb['physical_name']).group(0)[len(orbitfstart)+1:-4]
                    orbitdtstart=datetime.strptime(orbitfstart,'%Y%m%dT%H%M%S')
                    orbitdtend=datetime.strptime(orbitfend,'%Y%m%dT%H%M%S')
                    if sensingstart>=orbitdtstart and sensingstart<orbitdtend:
                        orbitfname=resorb['physical_name']
                        break

            if (not self.env.orbitnotif or (self.env.orbitnotif and datetime.now()>self.env.orbitnotif+timedelta(minutes=60))) and response.status_code<>200:
                mess="Response error from %s\nResponce code : %s, reason: %s\nuri: %s"%(self.env.orbitshub,response.status_code,response.reason, uriwithparams)
                self.sn.send_notification("error","orbits",mess,self.env.orbitshub)
                self.env.orbitnotif=datetime.now()
                self.log.error(mess)
            elif (not self.env.orbitnotif or (self.env.orbitnotif and datetime.now()>self.env.orbitnotif+timedelta(minutes=60))) and not orbitfname: 
                self.sn.send_notification("error","orbits",messnotfound+'\n\nuri: %s'%uriwithparams,"Orbit file search")
                self.env.orbitnotif=datetime.now()

        except:
            if self.log:
                self.log.error("Orbit file search failed:\n"+traceback.format_exc())
            if not self.env.orbitnotif or (self.env.orbitnotif and datetime.now()>self.env.orbitnotif+timedelta(minutes=60)):
                self.sn.send_notification("error","orbits","Orbit file search failed:\n"+traceback.format_exc(),"Orbit file search")
                self.env.orbitnotif=datetime.now()

        if not orbitfname:
            self.log.warning(messnotfound)
        
        sess.close()
        
        return orbitfname
    
    '''
    # Function before orbit site API and spec changes
    def sat_input_orbit_file(self,entry):
        
        #Store satellite imagery files information to satellite_input table

        sess=requests.session()
        orbitday=entry['Sensing start'][0:10]
        mission=entry['Name'][0:3]
        orbitfname=None
        messnotfound="Orbit file for '%s' not found"%entry['Name']

        try:
            uri=self.env.orbitshub
            response=sess.get("%s?mission=%s&validity_start_time=%s"%(uri,mission,orbitday),verify=False)
            #print response.content
            page=1
            while response.status_code==200: #scan all resorb pages for day
                print response.content
                for orbit in re.finditer(">%s.*EOF"%mission, response.content): #scan all files in page
                    orbitf=orbit.group(0)[1:]
                    orbitfstart=re.search("V.*_",orbitf).group(0)[1:-1]
                    orbitfend=re.search("%s_.*EOF"%orbitfstart,orbitf).group(0)[len(orbitfstart)+1:-4]
                    orbitdtstart=datetime.strptime(orbitfstart,'%Y%m%dT%H%M%S')
                    orbitdtend=datetime.strptime(orbitfend,'%Y%m%dT%H%M%S')
                    sensingstart=datetime.strptime(entry['Sensing start'][:19], '%Y-%m-%dT%H:%M:%S')
                    if sensingstart>=orbitdtstart and sensingstart<orbitdtend:
                        orbitfname=orbitf
                        return orbitfname
                page+=1
                if re.search("&page=%d"%page, response.content):
                    response=sess.get("%s?mission=%s&validity_start_time=%s&page=%d"%(uri,mission,orbitday,page),verify=False)
                else:
                    break

            if (not self.env.orbitnotif or (self.env.orbitnotif and datetime.now()>self.env.orbitnotif+timedelta(minutes=60))) and response.status_code<>200:
                mess="Response error from %s\nResponce code : %s, reason: %s"%(self.env.orbitshub,response.status_code,response.reason)
                self.sn.send_notification("error","orbits",mess,self.env.orbitshub)
                self.env.orbitnotif=datetime.now()
                self.log.error(mess)
            elif (not self.env.orbitnotif or (self.env.orbitnotif and datetime.now()>self.env.orbitnotif+timedelta(minutes=60))) and not orbitfname: 
                self.sn.send_notification("error","orbits",messnotfound,"Orbit file search")
                self.env.orbitnotif=datetime.now()

        except:
            self.log.error("Orbit file search failed:\n"+traceback.format_exc())
            if not self.env.orbitnotif or (self.env.orbitnotif and datetime.now()>self.env.orbitnotif+timedelta(minutes=60)):
                self.sn.send_notification("error","orbits","Orbit file search failed:\n"+traceback.format_exc(),"Orbit file search")
                self.env.orbitnotif=datetime.now()

        self.log.warning(messnotfound)
        return None
    '''

    def step_params(self,output, step):
        
        '''
        Forms and returns step's dynamic parameters for steps_execution table
        '''
        
        params=""
        paramkeys=self.get_output_config(output['id'],self.log)
        try:
            stepparams=json.loads(step['params'])
            if 'dyn_params' not in stepparams:
                return params
            dyn_params=json.loads(step['params'])['dyn_params']
            params=dyn_params
            for paramkey in paramkeys:
                if paramkey in dyn_params:
                    if paramkeys[paramkey]:
                        params=params.replace(paramkey,paramkeys[paramkey])
                    else: 
                        return ""
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Step parameters identification failed:\n"+traceback.format_exc())
        return params    


    def estimate_step_end(self,est_start,prevstep,freshstep,step):
        '''
        Estimates step's end time
        '''

        if  prevstep and prevstep['status']==self.env.STEP_STATUS_COMPLETED and prevstep['end_time']\
            and prevstep['end_time']+step['meantime']>datetime.now():
                est_end=prevstep['end_time']+step['meantime']
        elif freshstep['status']==self.env.STEP_STATUS_PROCESSING and freshstep['start_time']+step['meantime']>datetime.now():
            est_end=freshstep['start_time']+step['meantime']
        else:
            est_end=est_start+step['meantime']
        return est_end
       
    def clean_steps_output(self,output):
        
        '''
        Clean steps in steps_execution table that are inactive or deleted in steps table 
        '''
        
        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursdel=self.env.conn.postgr.cursor()
        try:
            sql="select step_id from steps_execution se left join steps s on se.step_id=s.id "+\
                "where type='%s' and step_id is null or activated=false and output_id=%d"%(output['type'],output['id'])
            curs.execute(sql)
            stepid=curs.fetchone()
            while stepid:
                sql="delete from steps_execution where output_id=%d and step_id=%d"%(output['id'],stepid['step_id'])
                cursdel.execute(sql)
                self.env.conn.postgr.commit()
                stepid=curs.fetchone()
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Clean steps failed:\n"+traceback.format_exc())
        curs.close()
        cursdel.close()
            
        
    def store_steps_output(self,output,est_start=datetime.now(), est_start_inter=datetime.now()):
        
        '''
        Store output steps in steps_execution table 
        '''

        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        curs2=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursins=self.env.conn.postgr.cursor()
        try:
            self.clean_steps_output(output)
            sutil=su(self.env)
            sql="select * from steps where type='%s' and activated=TRUE order by id"%output['type']
            curs.execute(sql)
            step=curs.fetchone()
            prevstep=freshstep=None
            while step:
                #if output==2003 and step['id']==95:
                #    pass
                prevstep=freshstep.copy() if freshstep else prevstep

                sqlst="select * from steps_execution where output_id=%d and step_id=%d"%(output['id'],step['id'])
                curs2.execute(sqlst)
                if curs2.rowcount==0:
                    sql="insert into steps_execution (step_id, output_id, status, enabled) "+ \
                        "values (%d,%d,'%s',false)" \
                       %(step['id'],output['id'],self.env.STEP_STATUS_WAIT)
                    cursins.execute(sql)
                    self.env.conn.postgr.commit()
                    
                curs2.execute(sqlst)
                freshstep=curs2.fetchone()
                params=self.step_params(output,step)
                if params and freshstep['dyn_params']!=params:
                    sutil.update_step(output['id'], step['id'], params, 'dyn_params','enabled=true')
                elif params and not freshstep['enabled']:
                    sutil.update_step(output['id'], step['id'], freshstep['status'], 'status','enabled=true')
                elif not params:
                    sutil.update_step(output['id'], step['id'], 'NULL', 'dyn_params','enabled=false')

                curs2.execute(sqlst)
                freshstep=curs2.fetchone()
                if freshstep['enabled'] and freshstep['status'] not in [self.env.STEP_STATUS_COMPLETED,self.env.STEP_STATUS_CANCEL]:
                    est_end=self.estimate_step_end(est_start,prevstep,freshstep,step)
                    sutil.update_step(output['id'], step['id'], est_end, 'estimate_end')
                    est_start=est_end
                elif not freshstep['enabled']:
                    est_end_inter=self.estimate_step_end(est_start_inter,prevstep,freshstep,step)
                    sutil.update_step(output['id'], step['id'], est_end_inter, 'estimate_end')
                    est_start_inter=est_end_inter
                else:
                    sutil.update_step(output['id'], step['id'], 'NULL', 'estimate_end')
                
                step=curs.fetchone()
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Insert steps failed:\n"+traceback.format_exc())
            raise
        curs.close()
        curs2.close()
        cursins.close()
        
    def utc_to_local(self,utc_datetime):
        '''
        Converts UTC to local time 
        '''

        now_timestamp = time.time()
        offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
        return utc_datetime + offset
    
    def strptime_m(self, datetime_string, format_string):
        '''
        Parse time with milliseconds or not 
        '''
        dtlist = datetime_string.strip().split(".")
        dt_no_ms=dtlist[0]
        mSecs=dtlist[1] if len(dtlist)>1 else None
       
        dt = datetime.strptime(dt_no_ms[:19], format_string)
        fullDateTime = dt + timedelta(milliseconds = int(mSecs)) if mSecs else dt
        
        return fullDateTime

    def estimate_output_start(self,output, prev_out_estim_end, prev_out_estim_end_inter):
        '''
        estimates output start time
        '''
        
        if not output['i2sens']:
            repassdays=self.find_probable_repassing(output['inp1'])
            ingestdelay=self.estimate_ingestion_delay(output['inp1'])
            estim_start_inter=self.utc_to_local(output['i1sens'])+timedelta(days=repassdays)+ingestdelay
            while estim_start_inter<self.sr['date']:
                estim_start_inter+=timedelta(days=repassdays)
            estim_start_inter=prev_out_estim_end_inter if estim_start_inter<prev_out_estim_end_inter else estim_start_inter
        else:
            estim_start_inter=prev_out_estim_end_inter
        estim_start=prev_out_estim_end
        return estim_start, estim_start_inter
        
    def estimate_output_end(self,output, enabled):
        '''
        estimates output end time
        '''

        curs2=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        prev_est_end=None
        #output estimate end
        sql="select estimate_end, end_time, status from steps_execution where output_id=%d and "%output['id']+\
        "step_id=(select max(step_id) from steps_execution where output_id='%d' and enabled=%s)"%(output['id'],enabled)
        curs2.execute(sql)
        est_end_rec=curs2.fetchone()
        if est_end_rec:
            if est_end_rec['status'] not in [self.env.STEP_STATUS_COMPLETED, self.env.STEP_STATUS_CANCEL]  or not est_end_rec['end_time']:
                prev_est_end=est_end_rec['estimate_end'] 
            else: 
                prev_est_end=est_end_rec['end_time']
        if prev_est_end:
            prev_est_end=datetime.now() if prev_est_end<datetime.now() else prev_est_end
        else:
            prev_est_end=datetime.now()
        curs2.close()
        
        return prev_est_end
    
    def check_update_output(self,output):
        '''
        Automatic update of output status
        '''
        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql="select * from steps_execution where output_id=%d and status not in ('%s','%s')"\
        %(output['id'],self.env.STEP_STATUS_COMPLETED,self.env.STEP_STATUS_CANCEL)
        curs.execute(sql)
        if curs.rowcount==0:
            su(self.env).update_output(output['id'],self.env.OUT_STATUS_READY)
        elif output['output_status'] not in self.env.OUT_OFF_LINE_SATUSES+[self.env.OUT_STATUS_PROCESSING]:
            offlinestatuses = "'"+"' ,'".join(self.env.OUT_OFF_LINE_SATUSES)+"'"
            sql="select * from steps_execution where output_id=%d and status in (%s)"\
            %(output['id'],offlinestatuses)
            curs.execute(sql)
            if curs.rowcount==0:
                su(self.env).update_output(output['id'],self.env.OUT_STATUS_PROCESSING)
           
    def create_output_notif(self,output, est_start, estim_start_inter, prev_est_end, prev_est_end_inter):
        '''
        Prepares notification information for new output
        '''

        est_end=max(prev_est_end_inter,prev_est_end)
        _est_start=min(est_start,est_end)
        if output['slave']:
            slave_st=output['slave']
        else:
            slavepassdays=self.find_probable_repassing(output['inp1'])
            slavesensing=self.utc_to_local(output['i1sens'])+timedelta(days=slavepassdays)
            while slavesensing<self.sr['date']:
                slavesensing+=timedelta(days=slavepassdays)
            slave_st=u"Not Available, Sensing time expected at %s, Ingestion time estimated at %s"\
            %(slavesensing.strftime('%Y-%m-%d %H:%M'),estim_start_inter.strftime('%Y-%m-%d %H:%M'))
        co_pre="co-seismic" if not output['i2sens'] or output['i1sens']<output['i2sens'] else "pre-seismic"
        mess="New %s Output ID:%d, priority: %d for service request: %s %s\n%s\n"\
        %(co_pre, output['id'],output['priority'],self.sr['name'],self.sr['date'],'-'*100)+\
        "Orbit: %s, Direction: %s\nMaster: %s\nSlave: %s\nEstimate Start: %s\nEstimate End: %s\n"\
        %(output['orbit'],output['direction'],output['master'],slave_st.encode('utf-8'),_est_start.strftime('%Y-%m-%d %H:%M'),est_end.strftime('%Y-%m-%d %H:%M'))
        return mess

    def store_steps(self,sid=None):
        '''
        Stores steps in steps_execution table for all outputs of the event
        '''

        if not sid:
            sid=self.sr['id']
        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            '''
            sql="select sum(meantime) outmeantime from steps where type='%s' and activated=true"%self.env.OUT_TYPE_IFG
            curs.execute(sql)
            m_rec=curs.fetchone()
            meanouttime=m_rec['outmeantime']
            '''

            sql="select so.id id, type, output_status, (regexp_split_to_array(inputs, '%s'))[1] inp1, "%self.env.ifg_inpsplit+\
                "s1.sensing_start i1sens, s2.sensing_start i2sens, s1.name master, s2.name slave, priority, s1.orbit orbit, s1.direction direction "+\
                "from service_output so "+\
                "join satellite_input s1 on s1.product_id=(regexp_split_to_array(inputs, '%s'))[1] "%self.env.ifg_inpsplit+\
                "left outer join satellite_input s2 on s2.product_id=(regexp_split_to_array(inputs, '%s'))[2] "%self.env.ifg_inpsplit+\
                "where service_id=%d order by so.priority"%sid
            curs.execute(sql)
            output=curs.fetchone()

            prev_est_end=prev_est_end_inter=datetime.now()
            alloutputsmess=''
            while output: 
                self.check_update_output(output)
                if output['output_status'] not in [self.env.OUT_STATUS_READY]+self.env.OUT_OFF_LINE_SATUSES:
                
                    #output estimate start
                    est_start, estim_start_inter=self.estimate_output_start(output,prev_est_end, prev_est_end_inter)
    
                    self.store_steps_output(output,est_start, estim_start_inter)
                    
                    #output estimate end
                    prev_est_end=self.estimate_output_end(output,"true")
                    _prev_est_end_inter=prev_est_end_inter
                    prev_est_end_inter=self.estimate_output_end(output,"false")
                    prev_est_end_inter=_prev_est_end_inter if not prev_est_end_inter else prev_est_end_inter
                    
                    if output['output_status']==self.env.OUT_STATUS_NEW:
                        mess=self.create_output_notif(output, est_start, estim_start_inter,prev_est_end, prev_est_end_inter)
                        cr="\n\n" if alloutputsmess else ""
                        alloutputsmess+=cr+mess
                self.check_update_output(output)
                output=curs.fetchone()
            title='Service request: %s - %s'%(self.sr['name'],self.sr['date'])
            if alloutputsmess:
                self.sn.send_notification("output","new",alloutputsmess,title)
                #print '-'*100+"\n"+title+"\n"+alloutputsmess
        except:
            #traceback.print_exc()
            if self.log:
                self.log.error("Insert steps failed:\n"+traceback.format_exc())
            raise
        curs.close()
    
    def get_output(self,output_id):
        '''
        Returns output properties of specific output and sets to the class the service properties of this output
        '''

        output=None
        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            sql="select * from service_output where id=%d"%output_id
            curs.execute(sql)
            if curs.rowcount>0 :
                output=curs.fetchone()
                self.set_service('%',output['service_id'],False,self.log)
        except:
            #traceback.print_exc()
            if self.log:
                self.log.error("Output not retrieved :\n"+traceback.format_exc())
            raise
        curs.close()
        return output
        
    def get_output_inputs(self,ifg_output):
        '''
        Returns input files of specific output
        '''
        master=slave=""
        prods=ifg_output['inputs'].split(self.env.ifg_inpsplit)
        master=prods[0]
        if len(prods)>1:
            slave=prods[1]
        return master, slave
        
    def get_output_name(self,output_id):
        '''
        Forms and returns output name for notification
        '''

        ifg_output=self.get_output(output_id)
        master,slave=self.get_output_inputs(ifg_output)
        m_dbprod=dbProduct(self.env)
        m_dbprod.set_product(master)
        master_st="Master:"+datetime.strftime(m_dbprod.dbdata['sensing_start'],'%Y-%m-%d %H:%M:%S')
        slave_st="SLAVE NOT AVAILABLE "
        if slave:
            s_dbprod=dbProduct(self.env)
            s_dbprod.set_product(slave)
            slave_st="Slave:"+datetime.strftime(s_dbprod.dbdata['sensing_start'],'%Y-%m-%d %H:%M:%S')
        outname= master_st+ " " + slave_st+" orbit:"+m_dbprod.dbdata['orbit'] +" direction:"+m_dbprod.dbdata['direction']
        if not slave or m_dbprod.dbdata['sensing_start']<s_dbprod.dbdata['sensing_start']:
            co_pre='co-seismic'
        else:
            co_pre='pre-seismic'
        return outname,co_pre
  
    def get_output_config(self,output_id, log):
        '''
        Returns configuration properties of specific output in a dictionary
        '''

        ifg_output=self.get_output(output_id)
        master,slave=self.get_output_inputs(ifg_output)
        if not hasattr(self, 'sr'):
            self.set_service('%',ifg_output['service_id'], False, log)
        m_dbprod=dbProduct(self.env)
        m_dbprod.set_product(master)
        m_folder=m_dbprod.get_product_dest()
        m_file=m_dbprod.dbdata['name']
        m_orbitfolder=m_dbprod.get_orbit_dest()
        m_orbitfile=m_dbprod.dbdata['orbit_file']
        #dem_folder=os.path.join(m_folder,"DEM")
        xmlfile=json.loads(self.sr['request_params'])[self.env.ifg_xmlprofile]
        
        s_folder=s_file=s_orbitfolder=s_orbitfile=ifg_folder=""
        
        try:
            publish_state = json.loads(ifg_output['params'])['publish']
        except:
            publish_state = 'Do nothing'
        
        if slave:
            s_dbprod=dbProduct(self.env)
            s_dbprod.set_product(slave)
            s_folder=s_dbprod.get_product_dest()
            s_file=s_dbprod.dbdata['name']
            s_orbitfolder=s_dbprod.get_orbit_dest()
            s_orbitfile=s_dbprod.dbdata['orbit_file']
            
            ifgtype='co_'if m_dbprod.dbdata['sensing_start']<s_dbprod.dbdata['sensing_start'] else 'pre_'
                        
            ifg_folder=os.path.join(self.get_eventfolder(self.sr['name'], self.sr['date']), \
                       ifgtype+\
                       datetime.strftime(m_dbprod.dbdata['sensing_start'],'%Y%m%d%H%M%S') + "_" + \
                       datetime.strftime(s_dbprod.dbdata['sensing_start'],'%Y%m%d%H%M%S') + "_" + \
                        m_dbprod.dbdata['orbit'] +"_"+m_dbprod.dbdata['direction'],"ifg")
                       
        outconfigdict={}
        outconfigdict[self.env.ifg_pathmaster]=m_folder
        outconfigdict[self.env.ifg_filemaster]=m_file
        outconfigdict[self.env.ifg_pathslave]=s_folder
        outconfigdict[self.env.ifg_fileslave]=s_file

        outconfigdict[self.env.ifg_pathorbitmaster]=m_orbitfolder
        outconfigdict[self.env.ifg_fileorbitmaster]=m_orbitfile

        outconfigdict[self.env.ifg_pathorbitslave]=s_orbitfolder
        outconfigdict[self.env.ifg_fileorbitslave]=s_orbitfile

        #outconfigdict[self.env.ifg_pathDEM]=dem_folder
        outconfigdict[self.env.ifg_pathIFG]=ifg_folder
        outconfigdict[self.env.ifg_configXML]=xmlfile
        outconfigdict[self.env.ifg_masterid]=master
        outconfigdict[self.env.ifg_slaveid]=slave
        outconfigdict[self.env.ifg_outputid]=str(output_id)
        outconfigdict[self.env.ifg_pathuncompressed]=self.env.sentinelunzip                     
        outconfigdict[self.env.ifg_publish]=publish_state
        outconfigdict[self.env.ifg_eventid]=str(self.sr['id'])
                      
        return outconfigdict
    
    
    def store_idl_config(self):
        '''
        Updates IDL configuration file
        '''

        idlrootconfig=self.env.configpath+self.env.idl_python_config
        if not os.path.exists(idlrootconfig) or os.path.getmtime(idlrootconfig)<os.path.getmtime(self.env.idl_configini):
            with open(self.env.idl_configini, "r") as idl_ini: 
                idl_ini_st=idl_ini.read()
                idl_ini.close()
            iniconfigdict=json.loads(idl_ini_st)
            iniconfigdict['uncompressed_dir']=self.env.sentinelunzip
            iniconfigdict['pathmaster']=self.env.ifg_pathmaster
            iniconfigdict['pathslave']=self.env.ifg_pathslave
            iniconfigdict['pathorbitmaster']=self.env.ifg_pathorbitmaster
            iniconfigdict['fileorbitmaster']=self.env.ifg_fileorbitmaster
            iniconfigdict['pathorbitslave']=self.env.ifg_pathorbitslave
            iniconfigdict['fileorbitslave']=self.env.ifg_fileorbitslave
            iniconfigdict['pathDEM']=self.env.ifg_pathDEM
            iniconfigdict['pathIFG']=self.env.ifg_pathIFG
            iniconfigdict['configXML']=self.env.ifg_configXML
            iniconfigdict['pathconfig']=self.env.configpath+self.env.idl_pathconfig
            idl_ini_st=json.dumps(iniconfigdict)
            idl_ini_conf = open(idlrootconfig, "w")
            idl_ini_conf.write(idl_ini_st)
            idl_ini_conf.close()
            idl_ini.close()
            now=datetime.now()
            tsnow = time.mktime(now.timetuple())
            os.utime(idlrootconfig, (tsnow, tsnow))

        
    def store_output_config(self,output_id):
        '''
        Store configuration file for IDL steps input (used for testing IDL code) 
        '''

        secs=0
        while os.path.exists(self.env.configpath+self.env.idl_pathconfig) and secs<20:
            secs=secs+1
            time.sleep(1)
        outconfigdict=self.get_output_config(output_id,self.log)
        with open(self.env.configpath+self.env.idl_pathconfig, "w") as config_file:
            config_st= json.dumps(outconfigdict)
            '''
            for param in sorted(outconfigdict):
                config_file.write(outconfigdict[param]+"\n")
            '''
            config_file.write(config_st)
            config_file.close()
        return secs
        
    def sql_store_output(self, otype, sid, inputids, status, params):
        curs = self.env.conn.postgr.cursor()
        try:
            sql="insert into service_output (type, service_id, inputs, output_status, params) " + \
                "values ('%s',%d,'%s','%s', '%s')" \
                %(otype, sid, inputids, status, params)
            curs.execute(sql)
            self.env.conn.postgr.commit()
        except:
            if self.log:
                self.log.warning("Insert sql failed failed:\n"+traceback.format_exc())
        curs.close()

    def store_output(self,masterentry, pair=None):
        '''
        Store output to service_output table 
        '''

        inputid=self.inputid
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        output_params={ "publish" : "yes" }
        try:
            sql="select * from service_output where service_id=%d and inputs like '%s%%' order by inputs"%(self.sr['id'],masterentry[inputid])
            curs.execute(sql)
            if not pair:
                #store input in satellite inputs
                input_stored=self.store_sat_input(masterentry)
                if not input_stored:
                    return
                #store input in ifg outputs
                if curs.rowcount==0:
                    self.sql_store_output(self.env.OUT_TYPE_IFG,self.sr['id'],masterentry[inputid],self.env.OUT_STATUS_NEW, json.dumps(output_params)) 
            else:
                #store input in satellite inputs
                input_stored=self.store_sat_input(pair)
                if not input_stored:
                    return

                #store distance to epicenter in params
                if 'epicenter distance' in pair:
                    output_params['epicenter distance']=pair['epicenter distance']
                
                #store input in ifg outputs
                inputs_st=masterentry[inputid]+self.env.ifg_inpsplit+pair[inputid]
                if curs.rowcount>0:
                    sout = curs.fetchone()
                    inps=sout['inputs'].split(self.env.ifg_inpsplit)
                    if len(inps)>1 or (len(inps)==1 and masterentry['Sensing start']>pair['Sensing start']): #1st co-seismic pair already stored or pre-seismic
                        sql="select * from service_output where service_id=%d and inputs like '%s%%'"%(self.sr['id'],inputs_st)
                        curs.execute(sql)
                        if curs.rowcount==0:
                            self.sql_store_output(self.env.OUT_TYPE_IFG,self.sr['id'],inputs_st,self.env.OUT_STATUS_NEW, json.dumps(output_params)) 
                    else: #is co-seismic
                        sql="update service_output set inputs='%s', params='%s' where service_id=%d and inputs like '%s'" \
                        %(inputs_st, json.dumps(output_params), self.sr['id'],masterentry[inputid])
                        curs.execute(sql)
                        self.env.conn.postgr.commit()
                else:
                    self.log.warning("Insert new pair failed: No master Record\n")
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Store output failed:\n"+traceback.format_exc())
        curs.close()
        
 
    def next_product_time(self,sid=None):
        '''
        Estimate and return availability time of next satellite imagery product of service (not available) 
        '''

        if not sid:
            sid=self.sr['id']
        inputid=self.dbinputid
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            sql="select outs.id,service_id,inp[1] inp1, inp[2] inp2, i1.sensing_start senstime, i2.sensing_start sens2 from (select id, service_id,regexp_split_to_array(inputs, '%s') inp from service_output) outs"\
            %(self.env.ifg_inpsplit)+ \
            " join satellite_input i1 on outs.inp[1] = i1.%s"%inputid+ \
            " left outer join satellite_input i2 on outs.inp[2] = i2.product_id"+\
            " where outs.service_id=%d"%(sid)+\
            " and i1.sensing_start<=coalesce(i2.sensing_start,i1.sensing_start)"+\
            " order by i1.sensing_start"
            curs.execute(sql)
            r_seq=curs.fetchone()
            while r_seq:
                nextpasstime=r_seq['senstime']+timedelta(days=self.find_probable_repassing(r_seq['inp1']))
                nextpassrange=nextpasstime+timedelta(minutes=self.env.ifg_fastsearchperiod)
                if nextpasstime<datetime.utcnow() and datetime.utcnow()<nextpassrange and nextpasstime>self.sr['date']:
                    return nextpasstime
                r_seq=curs.fetchone()
            return datetime.utcnow()+timedelta(days=1)
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Next product time estimation failed:\n"+traceback.format_exc())
        curs.close()

    def sql_get_output(self):
        '''
        Forms an SQL join to retrieve all properties needed for an output
        '''

        inputid=self.dbinputid
        sql="select so.id id, so.service_id sid, i1.sensing_start i1sens, i2.sensing_start i2sens,(regexp_split_to_array(inputs, '%s'))[1] inp1, "+\
             "(regexp_split_to_array(inputs, '%s'))[2] inp2, i1.orbit orbit, "+\
             "i1.footprint ms_footprint, i2.footprint sl_footprint from service_output so "\
             "join satellite_input i1 on i1.%s=(regexp_split_to_array(inputs, '%s'))[1] "%(inputid,self.env.ifg_inpsplit)+\
             "left outer join satellite_input i2 on i2.%s=(regexp_split_to_array(inputs, '%s'))[2] "%(inputid,self.env.ifg_inpsplit)
        return sql
    
    def sql_get_repassing(self,inp1=None):
        '''
        Forms SQL for find most probable re-passing time of the Sentinel-1 
        '''

        input1cond="and (regexp_split_to_array(inputs, '%s'))[1]='%s'"%(self.env.ifg_inpsplit,inp1) if inp1 else ''
        sql=self.sql_get_output()+\
            "where %s %s "%(self.pairtypes['2 pre-seismic'],input1cond)+\
            "and so.service_id=%d "%self.sr['id']+\
            "order by i1.sensing_start"
        return sql
    

    def find_probable_repassing(self,inp1):
        '''
        Estimates and returns most probable re-passing time of the Sentinel-1 for specific product 
        '''
        
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            sql=self.sql_get_repassing(inp1)
            curs.execute(sql)
            out=curs.fetchone()
            if out:
                dt=out['i1sens']-out['i2sens']
                dtdays=dt.days+int(round(dt.seconds/86400.0))
                return dtdays
            else:
                return self.sr_repassing
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Find repassing failed:\n"+traceback.format_exc())
        curs.close()
        
    def find_probable_repassing_event(self):
        '''
        Estimates and returns most probable re-passing time of the Sentinel-1 for all products for the specific service   
        '''

        repasslist=[]
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            sql=self.sql_get_repassing()
            curs.execute(sql)
            out=curs.fetchone()
            while out:
                dt=out['i1sens']-out['i2sens']
                dtdays=dt.days+int(round(dt.seconds/86400.0))
                repasslist.append(dtdays)
                out=curs.fetchone()
            if len(repasslist)>0:
                return max(set(repasslist), key=repasslist.count)
            else:
                return self.sr_repassing
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Find repassing for request failed:\n"+traceback.format_exc())
        curs.close()
        
    def estimate_ingestion_delay(self,master_id, method=1):
        '''
        Estimates the delay of imagery availability on sentinel hubs after satellite passing using different methods   
        '''

        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        delay=timedelta(hours=4)
        try:
            sql="select * from satellite_input where product_id='%s'"%master_id
            curs.execute(sql)
            dbprod=curs.fetchone()
            namefilter=",filename:%s*"%dbprod['name'][0:4] if dbprod else ""
            ptracer=ProductTracer(self.env,self.log)
            self.log.info("Estimate ingestion delay\n")
            lastproducts=[]
            lastproducts=ptracer.product_seeker(datetime.utcnow()-timedelta(minutes=60),datetime.utcnow(),self.env.ifg_filters+namefilter,datesearch="ingestiondate")
            if method==1 and len(lastproducts)>0:
                if len(lastproducts)>0:
                    delaysecs=0
                    nprods=0
                    for hubprod in lastproducts:
                        sensingstart=datetime.strptime(hubprod['Sensing start'][:19], '%Y-%m-%dT%H:%M:%S')
                        ingestion=datetime.strptime(hubprod['Ingestion date'][:19], '%Y-%m-%dT%H:%M:%S')
                        if (ingestion-sensingstart).seconds<86400:
                            delaysecs+=(ingestion-sensingstart).seconds
                            nprods+=1
                    if nprods>0:
                        delay=timedelta(seconds=int(delaysecs/nprods))
            elif method==2 or (method==1 and len(lastproducts)==0) and dbprod:
                paramsdict=json.loads(dbprod['params'])
                ingestiontime=datetime.strptime(paramsdict['Ingestion date'][:19], '%Y-%m-%dT%H:%M:%S')
                ingestiondelay=ingestiontime-dbprod['sensing_start']
                if ingestiondelay<timedelta(hours=24):
                    delay=ingestiondelay
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Find ingestion delay failed:\n"+traceback.format_exc())
        curs.close()
        return delay

    
    def set_priorities(self,sid=None):
        '''
        Sets the processing priority of the outputs of the service request   
        '''

        if not sid:
            sid=self.sr['id']
        inputid=self.dbinputid
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursupd = self.env.conn.postgr.cursor()
        try:
            repassdays=self.find_probable_repassing_event()
            priority=1
            for pairtype in sorted(self.pairtypes):
                sql="select outs.id id,service_id,inp[1] inp1, to_char(i1.sensing_start, 'YYYY-MM-DD HH24') master_sensing, outs.params::json ->> 'epicenter distance'"+ \
                " from (select id, service_id,regexp_split_to_array(inputs, '%s') inp,params from service_output) outs"%(self.env.ifg_inpsplit)+ \
                " join satellite_input i1 on outs.inp[1] = i1.%s"%inputid+ \
                " join service_request sr on outs.service_id = sr.id"+\
                " left outer join satellite_input i2 on outs.inp[2] = i2.%s"%inputid+ \
                " where outs.service_id=%d and %s order by"%(sid,self.pairtypes[pairtype])+\
                " div(cast(floor(extract(epoch from sr.date-i1.sensing_start)/86400) as int),%d),"%repassdays+ \
                " to_char(i1.sensing_start, 'YYYY-MM-DD HH24'), outs.params::json ->> 'epicenter distance', outs.id" #order by repassing period, master date, epicenter distance
                curs.execute(sql)
                r_seq=curs.fetchone()
                priority=2 if not r_seq else priority #if not r_seq no co-seismic outputs exist
                #prev_masterdate = r_seq['master_sensing'] if r_seq else datetime(2000,1,1)
                while r_seq:
                    sql="update service_output set priority=%d where id=%d"%(priority,r_seq['id']) 
                    cursupd.execute(sql)
                    r_seq=curs.fetchone()
                    if not r_seq:
                        priority+=1
                        break
                    #if r_seq['master_sensing']!=prev_masterdate:
                    priority+=1
                    #prev_masterdate=r_seq['master_sensing']
                self.env.conn.postgr.commit()
        except:
            #traceback.print_exc()
            if self.log:
                self.log.error("Priorities setting failed:\n"+traceback.format_exc())
            raise
        curs.close()
        cursupd.close()
        
        
    def masters_seeker(self,ptracer,period,period_from,period_to,orbitfilter,roi):
        '''
        Seeks 'master' imagery in the AOI for a specific period in all specified sentinel hubs 
        '''

        entries=[]
        self.log.info("\n")
        self.log.info("Search for Pre-Seismic master products from %s to %s (period: %d)\n"%(period_from,period_to,period))
        for hub in self.env.colhubs:
            # ~~~ FIX ~~~ 
            # Added sentinel in the call function for clarity and traceability
            hubentries=ptracer.product_seeker(period_from,period_to,self.env.ifg_filters,roi,hubs=[hub])
            self.alog.update_server_status('Server running')
            filtentries=self.filter_masters(hubentries, orbitfilter)
            for newentry in filtentries:
                if not any(entry['id']==newentry['id'] for entry in entries):
                    entries.append(newentry)
        return entries
    
    def find_mostrcentperiod(self, ptracer):

        '''
        Find 'master' most recent imagery in repassing periods from event 
        '''

        roi=self.sr['roi']
        repassing=self.sr_repassing
        mostrecentperiod=self.sr_mostrecentperiod

        period_from=self.sr['date']-timedelta(days=self.env.ifg_searchmaxperiods*repassing)
        period_to=self.sr['date']
            
        entriesmostrecent=self.masters_seeker(ptracer,0,period_from,period_to,"",roi)
        
        if len(entriesmostrecent)>0:
            entriesmostrecent.sort(key=operator.itemgetter('Sensing start'))
            dt=period_to-datetime.strptime(entriesmostrecent[-1]['Sensing start'][:19], '%Y-%m-%dT%H:%M:%S')
            mostrecentperiod=int(dt.days/(repassing*self.sr_pastperiod))
        
        return mostrecentperiod
       
       
    def find_masters(self,ptracer):
        '''
        Find 'master' imagery that intersects the AOI for a number of sentinel re-passing periods in the past
        Product Orbits found in more recent periods are filtered out 
        '''

        entries=[]
        pastperiod=self.sr_pastperiod
        repassing=self.sr_repassing
        mostrecentperiod=self.sr_mostrecentperiod
        roi=self.sr['roi']

        try :
            orbitfilter=[]

            period_to=self.sr['date']-timedelta(days=(mostrecentperiod+pastperiod-1)*repassing)
            period_from=self.sr['date']-timedelta(days=(mostrecentperiod+pastperiod)*repassing)
            
            for period in range(1,self.env.ifg_searchperiods+1):
                entries += self.masters_seeker(ptracer,period,period_from,period_to,orbitfilter,roi)
                
                for entry in entries:
                    if entry['Relative orbit'] not in orbitfilter:
                        orbitfilter.append(entry['Relative orbit'])
                '''
                commented out to use open search
                for entry in entries:
                    if "relativeorbitnumber:"+entry['Relative orbit']+' ' not in orbitfilter:
                    orbitfilter+=" AND NOT relativeorbitnumber:"+entry['Relative orbit']+' '
                '''
                period_to=period_from
                period_from-=timedelta(days=pastperiod*repassing)

        except:
            if self.log:
                self.log.warning("Pre-Seismic Product Seeker failed:\n"+traceback.format_exc())
        return entries

    def slaves_seeker(self,master_entry,ptracer,orbitfilter,preco,searchfrom,searchto):
        '''
        Seeks 'slave' imagery for a specific time period in all specified sentinel hubs 
        '''
        slave_entries=[]
        self.log.info("\n")
        self.log.info("Search for candidate slaves %s-seismic from %s to %s\n"%(preco,searchfrom,searchto))
        for hub in self.env.colhubs:
            candidateslaves=ptracer.product_seeker(searchfrom,searchto,self.env.ifg_filters+orbitfilter,hubs=[hub])
            self.alog.update_server_status('Server running')
            filtentries=self.filter_slaves(master_entry,candidateslaves,preco)
            for newentry in filtentries:
                if not any(slave_entry['id']==newentry['id'] for slave_entry in slave_entries):
                    slave_entries.append(newentry)
        return slave_entries
    
    def find_slaves(self,masterentry,ptracer):
        '''
        Find 'slave' imagery for co-seismic and pre-seismic pairs.
        Searches in the estimated repassdays time range for a number of sentinel re-passing periods after the master
        '''

        slave_entries=[]
        try:
            repassperiods=self.sr_pastperiod
            repassdays=self.sr_repassing
            orbitfilter=",relativeorbitnumber:"+masterentry['Relative orbit']
    
            sensingstart=datetime.strptime(masterentry['Sensing start'][:19], '%Y-%m-%dT%H:%M:%S')
            searchtime=sensingstart

            #search co-seismic slave entries
            while searchtime<self.sr['date']:
                searchtime=searchtime+timedelta(days = repassperiods*repassdays)
            searchfrom_co=searchtime-timedelta(minutes = self.env.ifg_tilesearchrange)
            searchto_co=searchtime+timedelta(minutes = self.env.ifg_tilesearchrange)
            slaves_co=[]
            while len(slaves_co)==0 and searchfrom_co<datetime.utcnow():
                slaves_co=self.slaves_seeker(masterentry,ptracer,orbitfilter,'co',searchfrom_co,searchto_co)
                searchfrom_co+=timedelta(days = repassperiods*repassdays)
                searchto_co+=timedelta(days = repassperiods*repassdays)
                
            #search pre-seismic slave entries
            searchfrom_pre=sensingstart-timedelta(days = repassperiods*repassdays)-timedelta(minutes = self.env.ifg_tilesearchrange)
            searchto_pre=sensingstart-timedelta(days = repassperiods*repassdays)+timedelta(minutes = self.env.ifg_tilesearchrange)
            slaves_pre=[]
            while len(slaves_pre)==0 and searchfrom_pre>sensingstart-timedelta(days = repassperiods*repassdays*(self.env.ifg_searchperiods), minutes=60):
                slaves_pre=self.slaves_seeker(masterentry,ptracer,orbitfilter,'pre',searchfrom_pre,searchto_pre)
                searchfrom_pre-=timedelta(days = repassperiods*repassdays)
                searchto_pre-=timedelta(days = repassperiods*repassdays)
                
            slave_entries=slaves_co+slaves_pre

        except:
            if self.log:
                self.log.error("Pair Product Seeker failed:\n"+traceback.format_exc())
        return slave_entries
    
    def get_orbits_sensing_old(self,dtype='masters'):
        
        '''
        Creates a list with newest or oldest sensing time per relative orbit 
        in masters, pre-seismic slaves or co-seismic slaves for the service output 
        '''
        
        if dtype=='masters':
            group='min'
            sens='i1sens'
            copre_and=''
        elif dtype=='slaves-pre':
            group='min'
            sens='i2sens'
            copre_and='and i1sens>coalesce(i2sens,i1sens)'
        elif dtype=='slaves-co':
            group='max'
            sens='i2sens'
            copre_and='and i1sens<=coalesce(i2sens,i1sens)'

        orbits={}
        outs_select=self.sql_get_output()
        sql="select orbit, %s(%s) sensing from (%s) outs where sid=%d %s group by orbit"%(group,sens,outs_select,self.sr['id'],copre_and)
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            curs.execute(sql)
            orb=curs.fetchone()
            while orb:
                orbits[orb['orbit']]=orb['sensing']
                orb=curs.fetchone()
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Get orbits max/min sensing failed:\n"+traceback.format_exc())
        curs.close()
        return orbits
    
    
    def get_orbits_sensing(self,dtype='masters', senstime=None, orbit=None):
        
        '''
        Creates a list with newest or oldest sensing time per relative orbit 
        in masters, pre-seismic slaves or co-seismic slaves for the service output 
        '''
        
        if dtype=='masters':
            if orbit is not None:
                copre_and="and orbit='%s'"%orbit
            else:
                copre_and=''
            mssl='ms'
        elif dtype=='slaves-pre':
            copre_and="and i1sens>coalesce(i2sens,i1sens) and i2sens is not null and i1sens='%s'"%senstime
            mssl='sl'
        elif dtype=='slaves-co':
            copre_and="and i1sens<=coalesce(i2sens,i1sens) and i2sens is not null and i1sens='%s'"%senstime
            mssl='sl'

        orbits=[]
        outs_select=self.sql_get_output()
        sql="select orbit, i1sens, i2sens, %s_footprint from (%s) outs where sid=%d %s"%(mssl,outs_select,self.sr['id'],copre_and)
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            curs.execute(sql)
            orb=curs.fetchone()
            while orb:
                orbits.append({'orbit':orb['orbit'],'i1sens':orb['i1sens'],'i2sens':orb['i2sens'],'footprint':orb['%s_footprint'%mssl]})
                orb=curs.fetchone()
        except:
            #traceback.print_exc()
            if self.log:
                self.log.warning("Get orbits sensing failed:\n"+traceback.format_exc())
        curs.close()
        return orbits
    

    def filter_masters(self,entries, orbitfilter=[]):
        '''
        Filter master entries older than existing in same orbit and masters that have small intersection with roi 
        '''
        
        try:
            #orbit_dates=self.get_orbits_sensing_old()
            existing_masters=self.get_orbits_sensing()
            groi=ogr.CreateGeometryFromWkt(self.sr['roi'])
            roiarea=groi.GetArea()
            filter_reason=''
            filteredentries=[]
            for entry in entries:
                append_entry=True
                
                for orbit in orbitfilter:
                    if entry['Relative orbit']==orbit:
                        append_entry=False
                
                #filter out older than existing master in same orbit
                '''
                sensingstart=datetime.strptime(entry['Sensing start'][:19], '%Y-%m-%dT%H:%M:%S')
                if entry['Relative orbit'] in orbit_dates:
                    if orbit_dates[entry['Relative orbit']]-sensingstart>timedelta(minutes=60):
                        append_entry=False
                '''
                        
                foot_master = wkt.loads(entry['WKT footprint'])
                for ems in existing_masters:
                    if ems['orbit']==entry['Relative orbit'] and ems['i1sens'].replace(microsecond=0)!=datetime.strptime(entry['Sensing start'][:19], '%Y-%m-%dT%H:%M:%S'):
                        foot_ems = wkt.loads(ems['footprint'])
                        foot_int = foot_master.intersection(foot_ems)
                        intarea = foot_int.area
                        emsarea = foot_ems.area
                        if intarea/emsarea>0.9:
                            append_entry=False
                            filter_reason=filter_reason+' older master exists '
                            break
                        
                #filter out masters that intersect a small portion of ROI
                if append_entry:
                    gmaster = ogr.CreateGeometryFromWkt(entry['WKT footprint'])
                    masterroiintersect=gmaster.Intersection(groi)
                    pcarea=masterroiintersect.GetArea()/roiarea
                    if pcarea<self.env.ifg_masterroipercent:
                        filter_reason=filter_reason+' master intersects a small portion of ROI '
                        append_entry=False
                    
                #filter out duplicates
                if append_entry:
                    for en2 in filteredentries:
                        if entry['Relative orbit']==en2['Relative orbit'] and entry['Sensing start']==en2['Sensing start']:
                            filter_reason=filter_reason+' master is duplicate '
                            append_entry=False
                    
                if append_entry:
                    filteredentries.append(entry)
                else: #kill steps that have as master the filtered out entry
                    stored_outputs=su(self.env).get_outputs(None, order=None, where_cl="inputs like '%s%%' and service_id=%d"%(entry['id'],self.sr['id']))
                    for so in stored_outputs:
                        killsteps = su(self.env).get_steps("output_id=%d and status in ('%s','%s')"%(so['id'], self.env.STEP_STATUS_WAIT, self.env.STEP_STATUS_PROCESSING))
                        for s in killsteps:
                            su(self.env).update_step_log(so['id'], s[0], self.env.STEP_STATUS_KILL, \
                                                         'Killed because output input (master) was filtered out at a later search, filter reason: \n%s'%filter_reason)
                            su(self.env).update_step(so['id'],s[0],self.env.STEP_STATUS_KILL)
        
        except:
            if self.log:
                self.log.warning("Filter orbit dates failed. Keeping original entries:\n"+traceback.format_exc())
            return entries

        return filteredentries

    def filter_slaves(self,entry,candidateslaves,preco):
        
        '''
        Filter slave entries according intersection with master and ROI 
        and according sensing time if others exist on same orbit 
        '''

        acceptedpairs=[]
        
        try:
            #groi=ogr.CreateGeometryFromWkt(self.sr['roi'])

            #foot1 = ogr.CreateGeometryFromWkt(entry['WKT footprint'])
            foot_master = wkt.loads(entry['WKT footprint'])
            epicenter = wkt.loads(self.sr["epicenter"])
            
            #foot1area=foot1.GetArea()

            #orbit_dates=self.get_orbits_sensing_old('slaves-%s'%preco)
            existing_slaves=self.get_orbits_sensing('slaves-%s'%preco, entry['Sensing start'])
    
            for slave in candidateslaves:
                #filter according intersection with master and ROI
                #foot2 = ogr.CreateGeometryFromWkt(slave['WKT footprint'])
                foot_slave = wkt.loads(slave['WKT footprint'])
                #f1f2intersect = foot1.Intersection(foot2)
                footifg = foot_master.intersection(foot_slave)
                pcarea=footifg.area/foot_master.area
                #pcarea=f1f2intersect.GetArea()/foot1area
                #f2roiintersect=foot2.Intersection(groi)
                paircond=eval(self.env.ifg_paircondition)
                if self.env.DEBUG:
                    mess = 'Selected: ' if paircond else 'Not Selected: '
                    if not footifg.is_empty:
                        mess+="Ifg for Master %s, Slave %s, Orbit %s contains epicenter: %s Distance: %5.2f"%\
                        (entry['Sensing start'],slave['Sensing start'],entry['Relative orbit'],footifg.contains(epicenter), footifg.distance(epicenter))
                    else:
                        mess+="No Ifg for Master %s, Slave %s, Orbit %s"%(entry['Sensing start'],slave['Sensing start'],entry['Relative orbit']) 
                    self.log.debug(mess)
                    print mess
                    
                #filter out older or newer than existing slaves in same orbit closer to master date
                '''
                non_existing_entry=True
                sensingstart=datetime.strptime(slave['Sensing start'][:19], '%Y-%m-%dT%H:%M:%S')
                if entry['Relative orbit'] in orbit_dates and orbit_dates[slave['Relative orbit']]:
                    if (preco=='pre' and orbit_dates[slave['Relative orbit']]>sensingstart+timedelta(minutes=60)) or \
                       (preco=='co' and  orbit_dates[slave['Relative orbit']]<sensingstart-timedelta(minutes=60)):
                    #if (preco=='pre' and orbit_dates[slave['Relative orbit']]>sensingstart+timedelta(seconds=20)) or \
                    #   (preco=='co' and  orbit_dates[slave['Relative orbit']]<sensingstart-timedelta(seconds=20)):
                        non_existing_entry=False
                '''
                        
                non_existing_entry=True
                if paircond:
                    for esl in existing_slaves:
                        if esl['orbit']==slave['Relative orbit']:
                            foot_esl = wkt.loads(esl['footprint'])
                            foot_int = foot_slave.intersection(foot_esl)
                            intarea = foot_int.area
                            eslarea = foot_esl.area
                            if intarea/eslarea>0.9:
                                non_existing_entry=False
                                break

                        
                #filter out duplicates
                append_entry=True
                if paircond and non_existing_entry:
                    for slave2 in acceptedpairs:
                        if slave2['Relative orbit']==slave['Relative orbit'] and slave2['Sensing start']==slave['Sensing start']:
                            append_entry=False

                if paircond and non_existing_entry and append_entry:
                    ifgepidist = -footifg.exterior.distance(epicenter) if footifg.contains(epicenter) else footifg.distance(epicenter)
                    slave['epicenter distance']=ifgepidist
                    acceptedpairs.append(slave)

        except:
            if self.log:
                self.log.error("Filter candidates failed. Keeping original entries:\n"+traceback.format_exc())
        
        return acceptedpairs

             
    def find_outputs(self):
        
        '''
        Searches, finds and stores outputs and steps for service in metadata database
        '''
        
        if not self.sr:
            return
        
        if self.env.DEBUG and self.systemlog:
            self.systemlog.debug('Find Outputs')
     
        self.update_AOI()
        
        ptracer=ProductTracer(self.env,self.log)

        # find most recent master acquired in satellite periods (eg 6 days intervals)
        self.sr_mostrecentperiod=self.find_mostrcentperiod(ptracer)
        
        # find pre-seismic master tiles
        entries=self.find_masters(ptracer)
       
        entries.sort(key=operator.itemgetter('Sensing start'))

        for entry in entries:
            self.store_output(entry)
            
        if len(entries)==0:
            return

        # find pairs
        for entry in entries:
            try :
                pairs = self.find_slaves(entry,ptracer)
                for pair in pairs:
                    self.store_output(entry, pair)
                    
            except:
                if self.log:
                    self.log.error("Pair Product Seeker failed:\n"+traceback.format_exc())
                
        #set prioriries
        self.set_priorities()
        #create steps
        self.store_steps()

 

