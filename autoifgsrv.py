'''

Copyright (C) Alex Apostolakis - All Rights Reserved
Unauthorized copying of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Alex Apostolakis a.apostolakis@yahoo.gr, alex.apostolakis@technoesis.gr,  August 2017

This is the file that contains the class of the main service loop 
and starts the service and controls the running of the steps

@author: Alex Apostolakis 
'''


import sys
from osgeo import gdal, ogr, osr
import psycopg2
import psycopg2.extras
import zipfile
import time
import searchimages
import publishing
import geomtools
import shutil
import traceback
import subprocess
import os, fnmatch
import ConfigParser
from shutil import rmtree
import logging
from serviceevent import servicerequest
import json
from serviceprocess import step_process
from environment import Environment
from datetime import datetime,timedelta
from step_utils import steputils
from logs import applog
from notifications import notification
from notifications import alerts
from msvcrt import getch,kbhit
from manage_srv import manageserver
from eventdetection import EventDetection
import re
from apicommands import ApiCommand
from fileutils import fileutils
import psutil
import multiprocessing as mp
#from urllib3.contrib import pyopenssl

class deleteutils(object):
    def __init__(self, directory, pattern, listtype, master_slave, procstatus=None):
        self.directory=directory 
        self.pattern=pattern
        self.listtype=listtype
        self.procstatus=procstatus
        self.env=Environment()
        su=steputils(self.env)
        output_id=int(mp.current_process().name.split('_')[1])
        output_config=servicerequest(self.env).get_output_config(output_id, None)
        if master_slave=='master' and not su.inputinuse(output_config[self.env.ifg_masterid]):
            self.delete_files()
        elif master_slave=='slave' and not su.inputinuse(output_config[self.env.ifg_slaveid]):
            self.delete_files()
        else:
            procstatus[1].put('Input is still in use. No deletion')
            procstatus[0].put(self.env.STEP_STATUS_FAILED)

    def delete_files(self):
        procstatus=self.procstatus
        fu=fileutils()
        try:
            for f in fu.find_files(self.directory,self.pattern,self.listtype):
                if os.path.isfile(f):
                    procstatus[1].put('Removing file %s'%f)
                    procstatus[2].put('Removing file %s'%f)
                    os.remove(f)
                else:
                    procstatus[1].put('File %s does not exist'%f)
            procstatus[0].put(self.env.STEP_STATUS_COMPLETED)
        except:
            procstatus[1].put('ERROR: '+traceback.format_exc())
            procstatus[0].put(self.env.STEP_STATUS_FAILED)
            

class Looper(object):
    ''' Main Service Loop '''     

    def __init__(self,startarg=None):
        print 'Loading environment...'
        
        self.env=Environment()
        self.threads=[]
        self.archivethreads={}
        self.archiving_output_id=None

        self.alog=applog(self.env)
        self.mglog=self.alog.opengenlog()
        self.startarg=startarg

        sys.excepthook = self.log_except_hook
        self.mglog.info('Initiating service...')
        self.su=steputils(self.env,self.mglog)
        self.sn=notification(self.env,self.mglog)
        if not os.path.exists(self.env.rootpath):
            os.makedirs(self.env.rootpath)
        if not os.path.exists(self.env.configpath):
            os.makedirs(self.env.configpath)
        if not os.path.exists(self.env.datapath):
            os.makedirs(self.env.datapath)
        if not os.path.exists(self.env.sentinel1path):
            os.makedirs(self.env.sentinel1path)
        if not os.path.exists(self.env.logs):
            os.makedirs(self.env.logs)
        if not os.path.exists(self.env.logs):
            os.makedirs(self.env.logs)
        if not os.path.exists(self.env.processed_trigger):
            os.makedirs(self.env.processed_trigger)
        if not os.path.exists(self.env.orbitspath):
            os.makedirs(self.env.orbitspath)

        self.al=alerts(self.env,self.mglog)
        print 'Root Path: %s'%self.env.rootpath
        self.mglog.info('Root Path: %s'%self.env.rootpath)
        print 'Service metadata database: %s'%self.env.conn.pg_dbname
        self.mglog.info('Service metadata database: %s'%self.env.conn.pg_dbname)
        
        
    def log_except_hook(self,*exc_info):
        ''' Log Unhandled exceptions to system log '''

        text = "".join(traceback.format_exception(*exc_info))
        self.mglog.error("Unhandled exception: %s", text)

    def check_stop_status(self):
        
        ''' Check if stop command activated (if stop file trigger exists) '''
    
        if os.path.isfile(self.env.logs+self.env.stopfile):
            os.remove(self.env.logs+self.env.stopfile)
            return True
        else:
            return False
    
    
    def print_instructions(self):    
        print "----------------------------------------------"
        print "DON'T CLOSE THIS WINDOW AND DON'T PRESS Ctrl-C"
        print "Press 'ESC' key for quit options."
        print "----------------------------------------------"
        
    def stop_on_escape(self):
        if kbhit():
            key = ord(getch())
            if key == 27:
                if raw_input("\nReally quit? (y/n)> ").lower().startswith('y'):
                    for resource in self.env.res_procnum:
                        print 'terminate %s processes'%resource 
                        self.terminate_all(resource)
                    print 'Service stopped'
                    self.mglog.info('Service stopped')
                    sys.exit(0)
                    
    def check_already_running(self):
        
        ''' Check if service already running '''

        cs=manageserver()
        stat=cs.check_server_status()
        if stat==0:
            mst='%s already. Exiting...'%cs.status[stat]
            self.mglog.info(mst)
            print mst
            sys.exit(1)
        elif stat==2:
            #if raw_input("%s. Force start? (y/n)> "%cs.status[stat]).lower().startswith('n'):
            mst='%s in a previous session.\nCheck task manager for hung processes and clean logs to start.\nExiting...'%cs.status[stat]
            self.mglog.info(mst)
            print mst
            sys.exit(1)

                   
    def stop_on_stopstatus(self):
        
        ''' Stop server if stop command activated  '''

        if self.check_stop_status():
            #terminate scheduled processes from steps
            for resource in self.env.res_procnum:
                self.mglog.info('terminate %s processes'%resource)
                self.terminate_all(resource)
            #terminate archive copies
            for archivekey in self.archivethreads:
                self.mglog.info('terminate archive processes')
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.archivethreads[archivekey].pid)])
            self.mglog.info('Service stopped')
            runfilepath=os.path.join(self.env.logs,self.env.runfile)
            if os.path.isfile(runfilepath):
                os.remove(runfilepath)
            curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
            try:
                sql="update serveralive set lastupdate=null"
                curs.execute(sql)
                self.env.conn.postgr.commit()
                curs.close()
            except:
                curs.close()
            sys.exit(0)
            
    def manage_steps(self):
        self.store_process_time()
        self.cleanthreads()
        self.check_steps_status()
        
        fs = self.get_freeSpace(self.env.rootpath[0:2])
        archtitle="Low space on processing storage"
        if (fs and fs>=self.env.freespacetrigger*1024*1024*1024.0*0.8): #Don't start new steps if low space
            self.step_runner()
            self.al.alert_off(archtitle)
        else:
            self.al.alert_on('storage', "Processing folder has limited space. Not starting new steps until automatic archiving frees enough space", archtitle, \
                             replay=self.env.lowstoragealertinterval, logalert=True)
        self.update_steps()
        
    def run_archive(self, lastArchivedCheck):
        if datetime.now()-lastArchivedCheck>timedelta(seconds=self.env.eventcheckinterval):
            self.archive()
            self.delete_archived()
            self.delete_archived_dirs()
            if self.env.DEBUG:
                self.mglog.debug("Delete Empty Input Directories")
            #Delete all empty folders from inputs
            fileutils().removeEmptyFolders(self.env.sentinel1path)
            lastArchivedCheck=datetime.now()
        return lastArchivedCheck
 
    def loopforever(self):

        ''' Run main Loop  '''

        firstrun=True
        
        self.check_already_running()

        if self.startarg=='clean':
            print 'Cleanup Started'
            self.mglog.info('Cleanup Started')
            self.clean_sat_input()
            return
        
        print 'Service Started'
        self.mglog.info('Service Started')
        lasteventcheck=datetime.now()-timedelta(seconds=self.env.eventcheckinterval+10)
        lastwebAPIcall=datetime.now()-timedelta(seconds=self.env.webAPItimeinterval+10)
        lastArchivedCheck=datetime.now()-timedelta(seconds=self.env.eventcheckinterval+10)


        #self.print_instructions()
       
        while True:

            self.alog.update_server_status('Server running')
 
            #self.stop_on_escape()
            self.stop_on_stopstatus()

            # check for new events
            if datetime.now()-lasteventcheck>timedelta(seconds=self.env.eventcheckinterval):
                ed=EventDetection(self.env,self.mglog)
                #qs=ed.get_last_quakes_usgs()
                #ed.store_last_quakes_usgs(qs)
                qs=ed.get_last_quakes_emsc()
                ed.store_last_quakes_emsc(qs)
            
            # execute web API commands    
            if datetime.now()-lastwebAPIcall>timedelta(seconds=self.env.webAPItimeinterval):
                lastwebAPIcall=datetime.now()
                ApiCommand(self.env,self.mglog).executeCommand()

           
            eventcheck=servicerequest(self.env)
            eventcheck.init_service(self.mglog)
            eventcheck.closelog()
            
            nsid = 0
            prevnsid = -1
            all_reset_ids=[]
            while prevnsid<nsid:
                prevnsid = nsid
                reset_event=servicerequest(self.env)
                sid=reset_event.set_service(self.env.EV_RESET, smartlog=self.mglog)
                if sid:
                    #self.terminate_service_threads(sid)
                    #self.cleanthreads()
                    if not sid in all_reset_ids:
                        all_reset_ids.append(sid)
                        nsid = len(all_reset_ids)
                    reset_event.reset_service(sid)
                    reset_event.closelog()
                    reset_event = None


            autostartlist = []
            if datetime.now()-lasteventcheck>timedelta(seconds=self.env.eventcheckinterval):
                lasteventcheck=datetime.now()
                #automatically turn status to "requested" if automatic processing criteria are met
                autoevent=servicerequest(self.env)
                #wheresql = "request_date>NOW() - INTERVAL '%d DAYS'"%self.env.autostartpastdays
                wheresql = "request_date>NOW() - INTERVAL '%d DAYS' and not status='%s'"%(self.env.autostartpastdays,self.env.EV_RESET)
                sids = autoevent.get_service_ids(self.env.EV_DETECTED, wheresql)
                for sid in sids:
                    autoevent.set_service('%',sid, initlog=False, smartlog=self.mglog)
                    if autoevent.automatic_event_start(self.mglog):
                        autostartlist.append(sid)
            
            event=servicerequest(self.env)
            sids=event.get_service_ids(self.env.EV_NEW)+event.get_service_ids(self.env.EV_PROCESS)
            for sid in sids: 
                event.set_service('%',sid, smartlog=self.mglog)
                ev_status=event.sr['status']
                if ev_status==self.env.EV_NEW:
                    if sid not in autostartlist:
                        title="%s - %s"%(event.sr['name'],event.sr['date'])
                        mess="Start Processing Event: \n\n"+\
                        event.event_properties_message(event.sr['name'], '%s'%event.sr['date'], event.sr['magnitude'], event.sr['epicenter_depth'], event.sr['epicenter'])
                        self.sn.send_notification("event","new",mess,title)
                elif ev_status==self.env.EV_PROCESS:
                    ev_status=event.check_update_service()
                if ev_status!=self.env.EV_READY:
                    checkminutes=self.env.ifg_checkslow if event.next_product_time()>datetime.utcnow() else self.env.ifg_checkfast
                    if event.sr['status']==self.env.EV_NEW or event.sr['last_check']+timedelta(minutes=checkminutes)<datetime.now() or firstrun:
                        if self.env.DEBUG:
                            self.mglog.debug('Find Outputs for service %s %d'%(event.sr['name'], event.sr['id']))
                        event.find_outputs()
                        event.update_service(self.env.EV_PROCESS)
                        event.update_service(datetime.now(), 'last_check')
                self.stop_on_stopstatus()
                self.manage_steps()
                lastArchivedCheck=self.run_archive(lastArchivedCheck)
                event.closelog()
            if self.env.DEBUG:
                self.mglog.debug('Finished Services Check')

            event=None
            
            time.sleep(5)
            
            self.manage_steps()
            lastArchivedCheck=self.run_archive(lastArchivedCheck)
            
            time.sleep(5)
            
            firstrun=False
         
    def store_process_time(self):
        
        ''' Store average process time to metadata database '''
        
        try:
            curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql="update steps s set meantime=mt.mean from "+\
                "(select step_id,avg(end_time-start_time) mean from steps_execution where status='%s' "%(self.env.STEP_STATUS_COMPLETED)+\
                "and start_time is not null and end_time is not null group by step_id order by step_id) mt "+\
                "where s.id=mt.step_id"
            curs.execute(sql)
            self.env.conn.postgr.commit()
            sql="update steps s set meantime='00:01' where meantime is null"
            curs.execute(sql)
            self.env.conn.postgr.commit()
        except:
            self.mglog.warning("Steps Mean time update failed:\n"+traceback.format_exc())
        finally:
            curs.close()
    
    def get_notif_data(self,step):     
        
        ''' Get data to form Notification '''
   
        _ev=servicerequest(self.env)
        _ev.set_service('%', step['service_id'], False, smartlog=self.mglog)
        service="%s - %s"%(_ev.sr['name'],_ev.sr['date'])
        outname,co_pre=_ev.get_output_name(step['output_id'])
        return service, outname, co_pre
    
    def get_step_log_data(self,step):     
        
        ''' Get data from step log '''
   
        i=1
  
    def send_step_notif(self, step, ntype):
    
        ''' Send step notification '''
        
        service,outname,co_pre=self.get_notif_data(step)
        titlesuf='%s, %s output id [%d]'%(step['name'], co_pre, step['output_id'])
        titlepref='%s'%(service)
        
        if ntype=="Step started":
            #notify step started
            mess='Step "%s" of %s output "%s" started at %s\n\nEstimate end at: %s'%(step['name'],co_pre,outname,datetime.now(),datetime.now()+step['meantime'])
            self.sn.send_notification("Step started",str(step['step_id']),mess, titlesuf,titlepref)
        elif ntype=="Step finished":
            #notify finished
            notifmess='Step "%s" of %s output "%s" finished at %s'%(step['name'],co_pre,outname,step['end_time'])
            self.sn.send_notification("Step finished",str(step['step_id']),notifmess, titlesuf,titlepref)
        elif ntype== "Step cancelled":
            #notify cancelled
            notifmess='Step "%s" of %s output "%s" cancelled.\n\n'%(step['name'],co_pre,outname)
            logmess=self.su.get_step_log_str(step['output_id'],step['step_id'])
            attachments=[]
            if logmess:
                logname_res=re.search('(?<=##Logs : ).*', logmess)
                logname = logname_res.group(0) if logname_res else None
                notifmess+=logmess
                attachments=[logname] if logname and os.path.exists(logname) else []
            self.sn.send_notification("Step cancelled",str(step['step_id']), notifmess, titlesuf, titlepref, attachments=attachments)
              
    def execute_step(self,step):
        
        ''' Execute a service step '''

        try:
            params=json.loads(step['params'])
            sp=step_process(self.env, step['output_id'],step['step_id'])
            if params['system']=='python':
                sp.init_pyprocess(eval(step['command']), step['dyn_params'].split())
            elif params['system']=='os':
                env=None
                if "idl.exe" in step['command']:
                    servicerequest(self.env).store_idl_config()
                    idl_env = os.environ.copy()
                    #cwd=os.getcwd()
                    dir_path = os.path.dirname(os.path.realpath(__file__))
                    idl_env["IDL_PATH"]="<IDL_DEFAULT>;"+os.path.join(dir_path,"idl_code;")
                    idl_env["GEOHUBROOT"]=self.env.rootpath
                    env=idl_env
                    #secs=servicerequest(self.env).store_output_config(step['output_id'])
                    #if secs>=20:
                    #    self.su.update_step_log(step['output_id'],step['step_id'],step['step_status'],"Force store file %s"%self.env.idl_pathconfig)
                sp.init_osprocess(step['command'], step['dyn_params'].split(),env)
            if sp.py_process:
                self.su.update_step_log(step['output_id'],step['step_id'],step['step_status'],self.env.process_start_mess)
                self.su.update_step(step['output_id'],step['step_id'], datetime.now(), 'start_time')
                self.su.update_step(step['output_id'], step['step_id'], self.env.STEP_STATUS_PROCESSING)
                self.threads.append(sp)
                #notify step started
                self.send_step_notif(step, "Step started")
                '''
                service,outname,co_pre=self.get_notif_data(step)
                titlesuf='%s, %s output id [%d]'%(step['name'], co_pre, step['output_id'])
                titlepref='%s'%(service)
                mess='Step "%s" of %s output "%s" started at %s\n\nEstimate end at: %s'%(step['name'],co_pre,outname,datetime.now(),datetime.now()+step['meantime'])
                self.sn.send_notification("Step started",str(step['step_id']),mess, titlesuf,titlepref)
                '''
            else:
                self.su.update_step_log(step['output_id'],step['step_id'],step['step_status'],"Step failed to start")
        except:
            #traceback.print_exc()
            self.su.update_step_log(step['output_id'],step['step_id'], step['step_status'], traceback.format_exc())
            self.mglog.error("Run step %d,%d failed:\n"%(step['output_id'],step['step_id'])+traceback.format_exc())

    def process_count(self, resource, priority=None):
        
        ''' Count all threads. If 'priority' if specified it counts threads of the specific priority '''
        
        count=0
        for thread in self.threads:
            check_prority=(thread.get_step()['priority']<=priority) if priority else True
            if thread.get_step()['resource']==resource and check_prority:
                count+=1
        return count
                
    def terminate_all(self, resource):
        
        ''' Terminates all threads or a specific resource '''

        for thread in self.threads:
            if thread.get_step()['resource']==resource:
                thread.terminate()
                
    def terminate_service_threads(self, sid):
        
        ''' Terminates all threads or a specific service '''
        
        for thread in self.threads:
            if thread.get_step()['service_id']==sid:
                thread.terminate()
                
    def terminate_non_p1(self, resource, thread_term_num=None):
        
        ''' Terminates all non priority 1 threads '''
        
        thread_term_num=100000 if not thread_term_num else thread_term_num
        if thread_term_num==0:
            return
        thread_term_count=0
        for thread in self.threads:
            tstep=thread.get_step()
            if tstep['resource']==resource and tstep['priority']>1:
                thread.terminate()
                step=thread.get_step()
                self.su.update_step_log(step['output_id'],step['step_id'],step['step_status'],"Step execution terminated by higher priority step")
                thread_term_count+=1
                if thread_term_count>=thread_term_num:
                    break

            
    def done_prereq(self, step):
        
        ''' Check if prerequisite steps of a step are executed '''

        prereq_done=True
        if not step['prereq_steps']:
            return prereq_done
        try:
            curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql="select * from steps_execution where step_id in (%s) and output_id=%d"%(step['prereq_steps'],step['output_id'])
            curs.execute(sql)
            prereq=curs.fetchone()
            while prereq:
                if prereq['status']!=self.env.STEP_STATUS_COMPLETED:
                    prereq_done=False
                    break
                prereq=curs.fetchone()
        except:
            self.mglog.error("Prerequisites check failed:\n"+traceback.format_exc())
        curs.close()
        return prereq_done
    
    def is_resource_available(self, resource, out_priority, step_priority, terminate=True, allpriorities=True):

        ''' 
        Check if a 'resource' is available in order to run a step
        In case of priority 1 step it terminates all non priority 1 to free resources 
        '''
        
        priority=self.env.max_res_priority[resource] if out_priority>self.env.max_res_priority[resource] else out_priority
        proc_count=self.process_count(resource) if allpriorities else self.process_count(resource,priority)
            
        if priority==1 and self.process_count(resource,1)<self.env.res_procnum[resource]["1"] and terminate and step_priority==1:
            thread_term_num = max(0, proc_count - self.env.res_procnum[resource]["1"] + 1)
            if thread_term_num>0:
                self.terminate_non_p1(resource,thread_term_num)
                self.cleanthreads()
            return True
        elif priority==1 and proc_count<self.env.res_procnum[resource]["1"] and terminate and step_priority!=1:
            return True
        elif priority==1 and proc_count<self.env.res_procnum[resource]["1"] and not terminate:
            return True
        elif priority>1 and proc_count<self.env.res_procnum[resource][str(priority)] and self.is_resource_available(resource, priority-1, step_priority, False, False):
            return True
        else:
            return False

    def has_processing_conflict(self, step_id, output_id, steprec):
        
        ''' 
        Checks a step before starting it for processing conflicts with steps running.
        Avoids to run the same step twice and checks if a step accesses the same input files with running steps 
        '''

        term_threads=[]
        for thread in self.threads:
            if thread.step_id==step_id and thread.output_id==output_id:
                return True
            inps=steprec['inputs'].split(self.env.ifg_inpsplit)
            threadstep=thread.get_step()
            threadinps=threadstep['inputs'].split(self.env.ifg_inpsplit)
            if threadstep['resource']==steprec['resource'] and threadstep['output_id']!=output_id:
                for inp in inps:
                    if inp in threadinps:
                        if self.env.killproc:
                            if steprec['step_priority']==1 and (threadstep['step_priority']>1 or (steprec['priority']==1 and threadstep['priority']>1)): 
                                term_threads.append(thread) # append to list with conflict threads of lower priority
                                break
                            else:
                                return True
                        else:
                            return True
        for thread in term_threads: #terminate conflict threads with lower than 1 priority
            thread.terminate()
            self.su.update_step_log(threadstep['output_id'],threadstep['step_id'],threadstep['step_status'],\
                                    "Step terminated by higher priority step (out=%d, step=%d) with processing conflict"%(output_id,step_id))
        if len(term_threads)>0:
            self.cleanthreads()
        return False

    def step_runner(self):
        
        '''
        Collects the steps that should run in the right order and starts a step if conditions are met 
        '''

        if self.env.DEBUG:
            self.mglog.debug("Step runner")
        #self.cleanthreads()
        #self.check_steps_status()
        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        sql="select *, se.status step_status,cast(s.params::json->>'priority' as integer) step_priority, so.priority priority, sr.name event_name, s.name as name "+ \
        " from steps_execution se join service_output so on se.output_id=so.id join steps s on se.step_id=s.id"+ \
        " join service_request sr on sr.id = so.service_id"+ \
        " where se.status in ('%s','%s')"%(self.env.STEP_STATUS_WAIT,self.env.STEP_STATUS_FAILED)+ \
        " and sr.status like '%s'"%self.env.EV_PROCESS+ \
        " order by step_priority, so.priority, so.id, se.step_id"
        curs.execute(sql)
        step=curs.fetchone()
        while step:
            if step['enabled'] and self.validate_history(step) and self.done_prereq(step) and not self.has_processing_conflict(step['step_id'],step['output_id'],step):
                if self.is_resource_available(step['resource'],step['priority'],step['step_priority'],terminate=self.env.killproc):
                    self.execute_step(step)
            step=curs.fetchone()
        curs.close()
        #self.update_steps()
            
    def validate_history(self, step):
        
        '''
        Check if a step with same parameters with the one specified by 'step' is running or is completed  
        '''

        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            #sql="select * from steps_execution where step_id=%d and dyn_params='%s' and status in ('%s','%s')"\
            #%(step['step_id'],step['dyn_params'],self.env.STEP_STATUS_PROCESSING,self.env.STEP_STATUS_COMPLETED)
            sql="select * from steps_execution se join steps s on se.step_id=s.id where command='%s' and dyn_params='%s' and status in ('%s','%s')"\
            %(step['command'],step['dyn_params'],self.env.STEP_STATUS_PROCESSING,self.env.STEP_STATUS_COMPLETED)
            curs.execute(sql)
            if curs.rowcount>0:
                stepcmp=curs.fetchone()
                if stepcmp['status']==self.env.STEP_STATUS_COMPLETED: #an identical step is completed
                    self.su.update_step(step['output_id'], step['step_id'], self.env.STEP_STATUS_COMPLETED)
                    self.su.update_step_log(step['output_id'], step['step_id'], self.env.STEP_STATUS_COMPLETED,\
                                         'Already Completed by step : output %d step %d'%(stepcmp['output_id'], stepcmp['step_id']))
                #if status is "processing" an identical step is running. Just waiting for it to finish
                return False
            else:
                return True
        except:
            self.mglog.error("Check step history failed:\n"+traceback.format_exc())
        curs.close()


    def update_steps(self):
        
        '''
        Updates metadata database with information collected from threads about running steps.
        Steps progress and logging information are updated
        '''

        for thread in self.threads:
            if thread.is_alive():
                mess=thread.get_message()
                while mess:
                    self.su.update_step_log(thread.output_id,thread.step_id,thread.get_step()['step_status'],mess)
                    mess=thread.get_message()
                mess=thread.get_progress()
                progress=mess
                while mess:
                    mess=thread.get_progress()
                    progress=mess if mess else progress
                if progress:
                    self.su.update_step(thread.output_id,thread.step_id, progress, 'progress')
 
    def cleanthreads(self):
        
        '''
        Cleans stopped threads and checks for reset or cancel commands for a step. 
        Updates metadata database with steps logging and status information.
        '''
        
        i=len(self.threads)-1
        try:
            while i >= 0:
                if not self.threads[i].is_alive():
                    stepstatus=self.threads[i].get_status()
                    if stepstatus not in (self.env.STEP_STATUS_COMPLETED, self.env.STEP_STATUS_FAILED):
                        #self.su.update_step_log(self.threads[i].output_id,self.threads[i].step_id, stepstatus,\
                        #                        "ERROR: Process terminated abnormally")
                        mess="ERROR: Process terminated abnormally"
                        self.su.update_step(self.threads[i].output_id,self.threads[i].step_id, self.env.STEP_STATUS_FAILED)
                    else:
                        mess=self.threads[i].get_message()
                        newmess=mess
                        while newmess:
                            newmess=self.threads[i].get_message()
                            if newmess:
                                mess+="\n\n"+newmess
                    upd='%s:\n%s'%(self.env.process_stop_mess,mess) if mess else self.env.process_stop_mess
                    self.su.update_step_log(self.threads[i].output_id,self.threads[i].step_id, stepstatus,upd)
                    if stepstatus:
                        self.su.update_step(self.threads[i].output_id,self.threads[i].step_id, stepstatus)
                        if stepstatus==self.env.STEP_STATUS_COMPLETED:
                            self.su.update_step(self.threads[i].output_id,self.threads[i].step_id, 'NULL','progress')
                            self.su.update_step(self.threads[i].output_id,self.threads[i].step_id, datetime.now(), 'end_time')
 
                            #notify finished
                            step=self.threads[i].get_step()
                            self.send_step_notif(step, "Step finished")

                    del self.threads[i]
                    i=len(self.threads)-1
                elif self.threads[i].get_step()['step_status'] in (self.env.STEP_STATUS_RESET, self.env.STEP_STATUS_KILL):
                    _stat=self.threads[i].get_step()['step_status']
                    self.su.update_step_log(self.threads[i].output_id,self.threads[i].step_id,_stat,"Attempt to terminate step")
                    self.threads[i].terminate()
                    time.sleep(10)
                    if not self.threads[i].is_alive():
                        if _stat==self.env.STEP_STATUS_RESET:
                            self.su.update_step_log(self.threads[i].output_id,self.threads[i].step_id,_stat,"Step task terminated. Reset to Wait")
                            self.su.update_step(self.threads[i].output_id,self.threads[i].step_id, self.env.STEP_STATUS_WAIT)
                        else:
                            self.su.update_step_log(self.threads[i].output_id,self.threads[i].step_id,_stat,"Step task terminated. Set to Cancel")
                            self.su.update_step(self.threads[i].output_id,self.threads[i].step_id, self.env.STEP_STATUS_CANCEL)
                        del self.threads[i]
                        i=len(self.threads)-1
                    else:
                        self.su.update_step_log(self.threads[i].output_id,self.threads[i].step_id,_stat,"Attempt to terminate step failed")
                        i=i-1
                else:
                    i=i-1
                #l=len(self.threads)
            '''
            while any(not thread.is_alive() for thread in self.threads):
                for _thread in self.threads:
                    if not _thread.is_alive():
                        self.threads.remove(_thread)
            '''
        except:
            #traceback.print_exc()
            self.mglog.error("Clean threads status failed:\n"+traceback.format_exc())

            
    def check_steps_status(self):
        '''
        Checks steps metadata for abnormal states, restart failed steps, handles step kill or reset commands
        '''
        
        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        curslog=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)

        try:
            #processing steps
            sql="select * from steps_execution where status='%s'"%(self.env.STEP_STATUS_PROCESSING)
            curs.execute(sql)
            step=curs.fetchone()
            while step:
                if not any(thread for thread in self.threads if thread.output_id == step['output_id'] and thread.step_id == step['step_id']):
                    self.su.update_step(step['output_id'],step['step_id'], self.env.STEP_STATUS_WAIT)
                    self.su.update_step_log(step['output_id'],step['step_id'],step['status'],"Step was probably interrupted. Reset to wait status")
                step=curs.fetchone()

            #failed steps
            sql="select *,se.status step_status from steps_execution se join service_output so on se.output_id=so.id join steps s on se.step_id=s.id where se.status='%s'"\
            %(self.env.STEP_STATUS_FAILED)
            curs.execute(sql)
            step=curs.fetchone()
            while step:
                sql="select count(*) cnt from steps_log where output_id=%d and step_id=%d and status='%s' and message like '%%%s%%'"\
                %(step['output_id'],step['step_id'],self.env.STEP_STATUS_FAILED,self.env.process_stop_mess)
                curslog.execute(sql)
                if curslog.rowcount>0:
                    cntfailed=curslog.fetchone()['cnt']
                    if cntfailed>=self.env.stepretries:
                        self.su.update_step(step['output_id'],step['step_id'], self.env.STEP_STATUS_CANCEL)
                        self.su.update_step_log(step['output_id'],step['step_id'],self.env.STEP_STATUS_CANCEL,"Step cancelled after %d retries"%self.env.stepretries)
                        
                        #notify cancelled
                        self.send_step_notif(step, "Step cancelled")
                        
                step=curs.fetchone()
            
            #reset steps
            sql="select * from steps_execution where status in('%s', '%s')"%(self.env.STEP_STATUS_RESET, self.env.STEP_STATUS_KILL)
            curs.execute(sql)
            step=curs.fetchone()
            while step:
                running=[thread for thread in self.threads if thread.output_id == step['output_id'] and thread.step_id == step['step_id']]
                if len(running)==0:
                    if step['status']==self.env.STEP_STATUS_RESET:
                        self.su.update_step_log(step['output_id'],step['step_id'],step['status'],"Reset step to wait status")
                        self.su.update_step(step['output_id'],step['step_id'], self.env.STEP_STATUS_WAIT)
                    else:
                        self.su.update_step_log(step['output_id'],step['step_id'],step['status'],"Set step to Cancel status")
                        self.su.update_step(step['output_id'],step['step_id'], self.env.STEP_STATUS_CANCEL)
                step=curs.fetchone()

        except:
            #traceback.print_exc()
            self.mglog.error("Check steps status failed:\n"+traceback.format_exc())
        curs.close()
        curslog.close()
        
    def get_freeSpace(self,drive):
        '''
        Return the free space of a drive (Windows command)
        '''
        
        try:
            totusefree = psutil.disk_usage(drive)
            return totusefree[2]
        except:
            self.mglog.error("Free space calc error:\n"+traceback.format_exc())
            return None 
        
    def update_archiving_status(self, archivekeys):
        
        '''
        Updates archiving status of output and archive threads
        '''
        
        archiving_output=self.su.get_output(None, order="se2.end_time",where_cl="output_status='%s'"%self.env.OUT_STATUS_ARCHIVING)
        if archiving_output:
            if any(archivekey in self.archivethreads for archivekey in archivekeys) and self.archiving_output_id==archiving_output["id"]:
                self.su.update_output(archiving_output['id'], self.env.OUT_STATUS_ARCHIVED)
                archsteps=self.su.get_steps("output_id=%d"%archiving_output['id'])
                for step_r in archsteps:
                    self.su.update_step(archiving_output['id'],step_r[0],self.env.STEP_STATUS_ARCHIVED)
                self.archivethreads={}
                self.mglog.info("Finished Archiving output id:%d"%archiving_output['id'])

            else:
                self.su.update_output(archiving_output['id'], self.env.OUT_STATUS_READY)
                self.mglog.info("Some problem occurred archiving output id:%d"%archiving_output['id'])

    def check_archived_status(self):
        
        '''
        Checks if the archived outputs are really moved from production storage
        '''
        
        archived_outputs=self.su.get_outputs(None, order=None, where_cl="output_status='%s'"%self.env.OUT_STATUS_ARCHIVED)
        for archived_output in archived_outputs:
            output_config=servicerequest(self.env).get_output_config(archived_output['id'],self.mglog)
            if (os.path.exists(output_config[self.env.ifg_pathmaster]) and not self.su.inputinuse(output_config[self.env.ifg_masterid])) or \
               (os.path.exists(output_config[self.env.ifg_pathslave]) and not self.su.inputinuse(output_config[self.env.ifg_slaveid])) :
                itest=1
                '''
                Check if there is actually another output that will archive inputs
                self.su.update_output(archived_output['id'], self.env.OUT_STATUS_READY)
                self.mglog.info("Archiving sat inputs of output id:%d not completed. Maybe it was locked by other output"%archived_output['id'])
                '''
            if os.path.exists(output_config[self.env.ifg_pathIFG]):
                self.su.update_output(archived_output['id'], self.env.OUT_STATUS_READY)
                self.mglog.info("Archiving for output id:%d was not completed."%archived_output['id'])
                
    def delete_archived_dirs(self):
        '''
        Checks if all outputs of a service is archived and deletes directories
        '''
        
        curs1=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        curs2=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)

        try:
            if self.env.DEBUG:
                self.mglog.debug("Delete Archive Directories")
                
            #sql="select id from service_request sr where exists (select * from service_output so where sr.id=so.service_id) "+\
            #"and not exists (select * from service_output so where sr.id=so.service_id and output_status<>'archived')"
            sql="select id from service_request sr where status='%s'"%self.env.EV_READY
     
            curs1.execute(sql)
            
            archived_service_id = curs1.fetchone()
            while archived_service_id:
                sql2="select * from service_output where service_id=%d and output_status not in ('%s','%s')"\
                %(archived_service_id['id'], self.env.OUT_STATUS_ARCHIVED, self.env.OUT_STATUS_DELETED)
                curs2.execute(sql2)
                if curs2.rowcount==0: #all outputs are archived or deleted
                    sql2="select id from service_output where service_id=%d limit 1"%archived_service_id['id']
                    curs2.execute(sql2)
                    archived_output_id = curs2.fetchone()
                    output_config=servicerequest(self.env).get_output_config(archived_output_id['id'],self.mglog)
                    delete_event_dir=os.path.dirname(os.path.dirname(output_config[self.env.ifg_pathIFG]))
                    if os.path.exists(delete_event_dir):
                        shutil.rmtree(delete_event_dir)
                archived_service_id = curs1.fetchone()
        except:
            self.mglog.error("Delete Archived dirs Error:\n"+traceback.format_exc())
                
        curs1.close()
        curs2.close()
        
    def archive(self):
        
        '''
        Moves outputs to an archive storage when there is limited space on production storage 
        or there are "old" outputs present in production storage  
        '''

        try:
            if self.env.DEBUG:
                self.mglog.debug("Archive")
            
            bfs=self.get_freeSpace(self.env.archiveroot[0:2])

            archtitle="Archiving storage problem"            
            if not os.path.exists(self.env.archiveroot) or not bfs or bfs<self.env.freespacelimit*1024*1024*1024:
                self.al.alert_on('storage', "Archive folder %s is missing or has limited space"%self.env.archiveroot, archtitle, \
                                 replay=self.env.lowstoragealertinterval, logalert=True)
            else:
                self.al.alert_off(archtitle)
            
            fs = self.get_freeSpace(self.env.rootpath[0:2])
            archivekeys=["master","slave","ifg"]

            archive_not_running=all(self.archivethreads[archivekey].poll() is not None for archivekey in self.archivethreads)

            if archive_not_running:
                #check the last output in "archiving" status and update status to "archived" or "finished" if archiving interrupted
                self.update_archiving_status(archivekeys)
    
                #check if archived really moved
                self.check_archived_status()
            
                #start new archiving
                oldest_output=self.su.get_output(None, order="se2.end_time",where_cl="output_status='%s'"%self.env.OUT_STATUS_READY)
                if oldest_output and oldest_output['out_end'] and ((fs and fs<self.env.freespacetrigger*1024*1024*1024) or \
                    datetime.now()-oldest_output['out_end']>timedelta(days=self.env.oldnesstrigger))\
                     and archive_not_running:
                    
                    self.archiving_output_id=oldest_output['id']
                    
                    self.mglog.info("Archiving output id:%d"%oldest_output['id'])
                    output_config=servicerequest(self.env).get_output_config(oldest_output['id'],self.mglog)
        
                    self.su.update_output(oldest_output['id'], self.env.OUT_STATUS_ARCHIVING)
                    archsteps=self.su.get_steps("output_id=%d"%oldest_output['id'])
                    for step_r in archsteps:
                        self.su.update_step(oldest_output['id'],step_r[0],self.env.STEP_STATUS_ARCHIVING) 
                        
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                    #archive master
                    if not self.su.inputinuse(output_config[self.env.ifg_masterid]):
                        move_path_master=output_config[self.env.ifg_pathmaster].replace(self.env.rootpath,self.env.archiveroot)
                        move_master_cmd=["robocopy",output_config[self.env.ifg_pathmaster],move_path_master,"/e","/move","/is","/np","/nfl","/unilog+:%srb_master.log"%self.env.logs]
                        self.archivethreads["master"] = subprocess.Popen(move_master_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=si)
    
                    #archive slave
                    if not self.su.inputinuse(output_config[self.env.ifg_slaveid]):
                        move_path_slave=output_config[self.env.ifg_pathslave].replace(self.env.rootpath,self.env.archiveroot)
                        move_slave_cmd=["robocopy",output_config[self.env.ifg_pathslave],move_path_slave,"/e","/move","/is","/np","/nfl","/unilog+:%srb_slave.log"%self.env.logs]
                        self.archivethreads["slave"] = subprocess.Popen(move_slave_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=si)
    
                    #archive interferogram
                    move_ifg=os.path.split(output_config[self.env.ifg_pathIFG])[0].replace(self.env.rootpath,self.env.archiveroot)
                    move_ifg_cmd=["robocopy",os.path.split(output_config[self.env.ifg_pathIFG])[0],move_ifg,"/e","/move","/is","/np","/nfl","/unilog+:%srb_ifg.log"%self.env.logs]
                    self.archivethreads["ifg"] = subprocess.Popen(move_ifg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=si)
        except:
            self.mglog.error("Archive Error:\n"+traceback.format_exc())
            
        return None
    
    def delete_directory(self, directory):
        shutil.rmtree(directory)
        #delete_dir_cmd=["cmd","/c","rmdir","/Q","/S",directory]
        #return subprocess.call(delete_dir_cmd)
        
    def delete_empty_directory(self, directory):
        if os.path.exists(directory) and len(os.listdir(directory))==0:
            self.delete_directory(directory)
            self.mglog.info("Deleted empty directory %s"%directory)
        #delete_dir_cmd=["cmd","/c","rmdir","/Q","/S",directory]
        #return subprocess.call(delete_dir_cmd)
    
    def delete_archived(self):
        
        '''
        Deletes outputs archive outputs when there is limited space on archive storage 
        or there are "old" archive outputs present in archive storage  
        '''

        try:
            if self.env.DEBUG:
                self.mglog.debug("Delete Archive")
            
            bfs=self.get_freeSpace(self.env.archiveroot[0:2])

            archtitle="Archiving storage not exists"            
            if not os.path.exists(self.env.archiveroot):
                self.al.alert_on('storage', "Archive folder %s is missing"%self.env.archiveroot, archtitle, \
                                 replay=self.env.lowstoragealertinterval, logalert=True)
                return
            else:
                self.al.alert_off(archtitle)

            #start new deleting
            oldest_output=self.su.get_output(None, order="se2.end_time",where_cl="output_status='%s'"%self.env.OUT_STATUS_ARCHIVED)
            if oldest_output and oldest_output['out_end'] and ((bfs and bfs<self.env.freespacelimit*1024*1024*1024) or \
                datetime.now()-oldest_output['out_end']>timedelta(days=self.env.deletearchiveddays)):
                
                self.mglog.info("Deleting Archived output id:%d"%oldest_output['id'])
                output_config=servicerequest(self.env).get_output_config(oldest_output['id'],self.mglog)
                
                #si = subprocess.STARTUPINFO()
                #si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
                #delete master
                move_path_master=output_config[self.env.ifg_pathmaster].replace(self.env.rootpath,self.env.archiveroot)
                if os.path.exists(move_path_master):
                    self.delete_directory(move_path_master)
                    
                monthdir=os.path.dirname(move_path_master)
                self.delete_empty_directory(monthdir)
                yeardir=os.path.dirname(monthdir)
                self.delete_empty_directory(yeardir)

                #delete slave
                move_path_slave=output_config[self.env.ifg_pathslave].replace(self.env.rootpath,self.env.archiveroot)
                if os.path.exists(move_path_slave):
                    self.delete_directory(move_path_slave)
                monthdir=os.path.dirname(move_path_slave)
                self.delete_empty_directory(monthdir)
                yeardir=os.path.dirname(monthdir)
                self.delete_empty_directory(yeardir)
                

                #delete interferogram
                move_ifg=os.path.split(output_config[self.env.ifg_pathIFG])[0].replace(self.env.rootpath,self.env.archiveroot)
                if os.path.exists(move_ifg):
                    self.delete_directory(move_ifg)
                
                self.su.update_output(oldest_output['id'], self.env.OUT_STATUS_DELETED)
                
                eventdir=os.path.dirname(move_ifg)
                self.delete_empty_directory(eventdir)
            
                self.mglog.info("Finished Deleting Archived output id:%d"%oldest_output['id'])

        except:
            self.mglog.error("Delete Archived Error:\n"+traceback.format_exc())
        
        return None   
            
    def clean_sat_input(self):
        '''
        Delete satellite input processed files and input records for inputs that do not exist in any service output record
        '''
    
        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        try:
            sql="select product_id from satellite_input si where not exists (select * from service_output so where so.inputs like '%%' || si.product_id || '%%')"
            curs.execute(sql)
            req=curs.fetchone()
            
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
            
            while req:
                dbprod=searchimages.dbProduct(self.env)
                dbprod.set_product(req['product_id'])
                product_folder=dbprod.get_product_dest()
                
                #delete sat input folder
                if os.path.exists(product_folder):
                    self.mglog.info("Deleting unused input %s",product_folder)
                    shutil.rmtree(product_folder)
                
                req=curs.fetchone()
        
            sql="delete from satellite_input si where not exists (select * from service_output so where so.inputs like '%%' || si.product_id || '%%')"
            curs.execute(sql)
            self.env.conn.postgr.commit()
        
        except:
            self.mglog.error("Clean Sattelite Inputs error:\n"+traceback.format_exc())
            
        curs.close()
        
    def copy_output(self, out_id1, out_id2):
        
        output1_config=servicerequest(self.env).get_output_config(out_id1,self.mglog)
        output2_config=servicerequest(self.env).get_output_config(out_id2,self.mglog)

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        #copy interferogram
        orig_ifg=os.path.split(output1_config[self.env.ifg_pathIFG])[0]
        copy_ifg=os.path.split(output2_config[self.env.ifg_pathIFG])[0]
        copy_ifg_cmd=["robocopy",orig_ifg,copy_ifg,"/e","/is","/np","/nfl","/unilog+:%cp_ifg.log"%self.env.logs]
        self.copythreads["ifg"] = subprocess.Popen(copy_ifg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=si)    
           
def main(argv):
    
    if len(argv)==1:
        lp=Looper(argv[0])
    else:
        lp=Looper()
    lp.loopforever()
     
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
