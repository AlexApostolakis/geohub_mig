'''
Created on 6 Dec 2017

@author: arcgisadmin
'''
from environment import Environment
from datetime import datetime, timedelta
import os
import sys
import time
import traceback
from notifications import notification
from notifications import alerts
import subprocess
import re
import publishing
from step_utils import steputils
from serviceevent import servicerequest
from logs import applog
import psycopg2.extras

class manageserver(object):
    def __init__(self):
        self.env=Environment()
        self.status={0:"Service is running",1:"Service is stopped", 2:"Service too slow, hung or has abnormally stopped ", 3:"Service is running but OS Task commands fail. Proceed to server reboot ASAP"}
        self.hunglimit=900
        self.checkOSinterval=300
        self.sn=notification(self.env)
        self.lastOScheck=datetime.now()-timedelta(seconds=self.checkOSinterval)
        self.OSCheck=True
        lognumst=""
        lognum=0
        while os.path.isfile(os.path.join(self.env.logs,"managesrv%s.log"%lognumst)):
            lognum+=1
            lognumst=str(lognum)
        logname="managesrv%s"%lognumst
        self.mglog = applog(self.env).opengenlog(logname)
        self.debug = self.env.debugmanage
    
    def get_alivetime(self, chtype='db'):
        alivetime=None
        if chtype == 'file':
            if os.path.isfile(self.env.logs+self.env.runfile):
                secs=0
                while secs<5:
                    try:
                        with open(self.env.logs+self.env.runfile, "r") as run_file:
                            timest=run_file.read()
                            run_file.close()
                        alivetime=datetime.strptime(timest[:19], '%Y-%m-%d %H:%M:%S')
                    except:
                        secs+=1
                        if secs==5:
                            print "Check error:"+traceback.format_exc()
                        if run_file:
                            run_file.close()
                        time.sleep(1)
        elif chtype == 'db':
            curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
            try:
                sql="select lastupdate from serveralive"
                curs.execute(sql)
                lastupdate = curs.fetchone()['lastupdate']
                alivetime=lastupdate
                timest=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                sql="update serveralive set lastcheck='%s'"%datetime.now()
                curs.execute(sql)
                self.env.conn.postgr.commit()
                curs.close()
            except:
                curs.close()
            
        return alivetime
        

    def check_server_status(self):
        alivetime=self.get_alivetime()
        if not alivetime:
            return 1
        
        #_checkOS = self.check_os_commands()
        #self.OSCheck =_checkOS if _checkOS in [True, False] else self.OSCheck
          
        if alivetime+timedelta(seconds=self.hunglimit)<datetime.now():
            return 2
        elif not self.OSCheck :
            return 3
        else:
            return 0
    
    def loopcheck(self):
        prevstat=stat=-1
        print 'Root Path: %s'%self.env.rootpath
        print 'Service metadata database: %s'%self.env.conn.pg_dbname
        print 'Archiving path: %s'%self.env.archiveroot
        print 'Publishing path: %s'%self.env.publishfolder

        print 'Checking server...'
        sleepsecs=5
        while True:
            time.sleep(sleepsecs)
            stat=self.check_server_status()
            if stat!=prevstat:
                print "%s"%datetime.now().strftime('%d-%m-%Y %H:%M:%S')+" : "+self.status[stat]
                if stat in [2,3]:
                    self.sn.send_notification("server","error",self.status[stat],self.status[stat])
                else:
                    self.sn.send_notification("server","info",self.status[stat],self.status[stat])
            prevstat=stat
            sleepsecs = sleepsecs+5 if sleepsecs<60 else sleepsecs
            if self.debug:
                self.mglog.debug("Checking server status")
            
    def stop_server(self):
        stat=self.check_server_status()
        if stat in [1,2]:
            print 'Server is not running or hung'
            return
        print 'Stopping server.\n'+\
              'According processing stage it could take several minutes\n'+\
              'If stop fails after 5 minutes, check system.log'
        with open(os.path.join(self.env.logs,self.env.stopfile), "w") as stop_file:
            stop_file.write("%s"%datetime.now())
            stop_file.close()
        stat=self.check_server_status()
        countsecs=0
        while stat!=1 and countsecs<300:
            time.sleep(5)
            countsecs+=1
            stat=self.check_server_status()
        if stat==1:
            print 'Server is stopped'
        else:
            print 'Failed to stop server or '

    def clean_server(self, chtype='db'):
        print 'Reset server for starting...'
        serverok='Server ok for start'
        servernotreset='Server not need reset'
        if chtype=='file':
            filest=os.path.join(self.env.logs,self.env.runfile)
            if os.path.isfile(filest):
                os.remove(filest)
                print serverok
            else:
                print servernotreset
        elif chtype=='db':
            curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
            try:
                sql="select lastupdate from serveralive"
                curs.execute(sql)
                lastupdate = curs.fetchone()['lastupdate']
                if lastupdate:
                    sql="update serveralive set lastupdate=null"
                    curs.execute(sql)
                    self.env.conn.postgr.commit()
                    print serverok
                else:
                    print servernotreset
                curs.close()
            except:
                curs.close()
        
            
    def check_os_commands(self):
        
        '''
        Check if tasklist , taskkill os commands are working normally
        '''
        #si = subprocess.STARTUPINFO()
        #si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            if self.lastOScheck+timedelta(seconds=self.checkOSinterval)>datetime.now():
                return -1
            self.lastOScheck=datetime.now()
            out = subprocess.check_output(["tasklist"])
            if re.search("Image Name", out) :
                return True
            else:
                return False
        except:
            return False


    def publish_outputs(self, ev_id = None, pubtype='ifg', status='archived'):
        where_cl = "output_status='%s' and service_id=%d"%(status,ev_id) if ev_id else "output_status='%s'"%status
        selected_outputs=self.su.get_outputs(None, order = None, where_cl = where_cl)
        for sel_output in selected_outputs:
            output_config=servicerequest(self.env).get_output_config(sel_output['id'],self.mglog)
            outdir=output_config[self.env.ifg_pathIFG]
            if status in [self.env.OUT_STATUS_ARCHIVED, self.env.OUT_STATUS_DELETED]:
                finaloutdir=outdir.replace(self.env.rootpath,self.env.archiveroot)
            else:
                finaloutdir=outdir
            outpubdir=outdir.replace(self.env.datapath, self.env.publishfolder)
            if not os.path.exists(outpubdir):
                infomess='Publishing output id %d\nOutput source folder: %s'%(sel_output['id'],finaloutdir)
                print infomess
                self.mglog.info(infomess)
                try:
                    publishing.Publish(sel_output[0], finaloutdir, output_config[self.env.ifg_publish], fileset=pubtype, env=self.env, log=self.mglog, archive = True, notify =False, overwrite = False)
                except:
                    self.mglog.error("Publish output id %d failed:\n"%sel_output['id']+traceback.format_exc())

        
    def publish_archived_outputs(self, ev_id = None, pubtype='ifg'):
        try:
            self.su=steputils(self.env,self.mglog)
            for status in [self.env.OUT_STATUS_ARCHIVED, self.env.OUT_STATUS_DELETED]:
                self.publish_outputs(ev_id, pubtype, status)
                
        except:
            self.mglog.error("Publish output failed:\n"+traceback.format_exc())
            
    def publish_finished_outputs(self, ev_id = None, pubtype='ifg'):
        try:
            self.su=steputils(self.env,self.mglog)
            self.publish_outputs(ev_id, pubtype, self.env.OUT_STATUS_READY)
        except:
            self.mglog.error("Publish output failed:\n"+traceback.format_exc())
        
def main(argv):
    ms=manageserver()
    if argv[1]=='check':
        ms.loopcheck()
    elif argv[1]=='stop':
        ms.stop_server()
    elif argv[1]=='clean':
        ms.clean_server()
    elif argv[1]=='pubarch' and len(argv)==2:
        ms.publish_archived_outputs()
    elif argv[1]=='pubarch' and len(argv)==3:
        ms.publish_archived_outputs(int(argv[2]))
    elif argv[1]=='pubarch' and len(argv)==4:
        ms.publish_archived_outputs(int(argv[2]), argv[3])
    elif argv[1]=='pubfin' and len(argv)==3:
        ms.publish_finished_outputs(int(argv[2]))
    elif argv[1]=='pubfin' and len(argv)==4:
        ms.publish_finished_outputs(int(argv[2]), argv[3])
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))

