'''
Created on 8 Nov 2017

@author: Alex Apostolakis

'''
import traceback
import os
import logging
from datetime import datetime
import psycopg2.extras

class applog:
    def __init__(self,env):
        self.env=env
    
    def opengenlog(self, logname = 'system'):
        try:
            if not os.path.exists(self.env.logs):
                os.makedirs(self.env.logs)
                
            logfname=os.path.join(self.env.logs,logname+".log")
            
            #logging.basicConfig(filename=self.serv_path+str(rsid)+"/"+self.logs+"/"+self.processlog+str(rsid)+".log", \
            #            level=logging.DEBUG, format='%(asctime)s %(message)s')
            formatter=logging.Formatter('%(asctime)s %(levelname)s : %(message)s')
            fileh = logging.FileHandler(logfname, 'a')
            fileh.setFormatter(formatter)
            systemlog = logging.getLogger(logname)
            systemlog.addHandler(fileh)
            systemlog.setLevel(logging.DEBUG)
            return systemlog

        except:
            traceback.print_exc()
            return None
        
    def unhandederrorlog(self):
        try:
            if not os.path.exists(self.env.logs):
                os.makedirs(self.env.logs)
                
            logfname=self.env.logs+"error.log"
            
            #logging.basicConfig(filename=self.serv_path+str(rsid)+"/"+self.logs+"/"+self.processlog+str(rsid)+".log", \
            #            level=logging.DEBUG, format='%(asctime)s %(message)s')
            formatter=logging.Formatter('%(asctime)s %(message)s')
            fileh = logging.FileHandler(logfname, 'a')
            fileh.setFormatter(formatter)
            errorlog = logging.getLogger("system")
            errorlog.addHandler(fileh)
            errorlog.setLevel(logging.DEBUG)
            return errorlog

        except:
            traceback.print_exc()
            return None
        
    def update_server_status(self,mess, chtype='db'):
        if chtype=='db':
            curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
            timest=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sql="update serveralive set lastupdate='%s'"%datetime.now()
            curs.execute(sql)
            self.env.conn.postgr.commit()
        elif chtype=='file':
            with open(self.env.logs+self.env.runfile, "w") as run_file:
                run_file.write("%s %s"%(datetime.now(),mess))
                run_file.close()

