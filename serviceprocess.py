'''
Created on 25 Sep 2017

Classes to handle multithreading

@author: alex
'''

import multiprocessing as mp
import subprocess
import psycopg2.extras
from environment import Environment
import time
import re
from step_utils import steputils
import traceback
import os
import sys
import json
#from WriteFeaturesToTextFile import arg3poss

class step_process(object):
    '''
    This class handles the execution of a service step either it is a python or OS or IDL process 
    '''   
    def __init__(self,env, output, step):
        self.env=env
        self.step_id=step
        self.output_id=output
        self.procstatus=[mp.Queue(), mp.Queue(), mp.Queue(), mp.Queue()] #status read, messages read, progress read, signal to subprocess
        self.py_process=None
        self.op=None
        self.waitsecs=10
        mp.set_executable(os.path.join(sys.exec_prefix, 'pythonw.exe'))
            
    def init_pyprocess(self, func, varargs):
        '''
        Initiate class in case of python process 
        '''   

        try:
            varargs.append(self.procstatus)
            self.py_process = mp.Process(name="step_%s_%s"%(str(self.output_id),str(self.step_id)), target=func, args=varargs)
            self.py_process.start()
        except:
            #traceback.print_exc()
            steputils(self.env).update_step_log(self.output_id, self.step_id, self.get_step()['step_status'], \
                                                'Python process failed to start\n'+traceback.format_exc())

    def init_osprocess(self, command, varargs=[], environ=None):
        '''
        Initiate class in case of OS process 
        '''   

        try:
            self.op=osprocess()
            self.py_process = mp.Process(name="step_%s_%s"%(str(self.output_id),str(self.step_id)), \
                                                      target=self.op.run_osprocess, args=(self.procstatus, self.get_step(), command, varargs, environ, self.waitsecs))
            self.py_process.start()
        except:
            steputils(self.env).update_step_log(self.output_id, self.step_id, self.get_step()['step_status'], \
                                                'OS process failed to start\n'+traceback.format_exc())
            traceback.print_exc()
        
    def terminate(self):
        '''
        Terminate process 
        '''   

        if self.py_process and not self.op:
            self.py_process.terminate()
        elif self.py_process and self.op:
            self.procstatus[3].put('autoifg:terminate')
            
    def is_alive(self):
        '''
        Check if process running
        '''
        if self.py_process:
            return self.py_process.is_alive()
        else:
            return None
        
    def get_step(self):
        '''
        Retrieve step properties from steps_execution table
        '''
        return steputils(self.env).get_step(self.output_id,self.step_id)
    
    def get_status(self):
        '''
        Retrieve process status from process
        '''

        try:
            status=self.procstatus[0].get(False)
            return status
        except:
            return None
    
    def get_message(self):
        '''
        Retrieve message from process
        '''

        try:
            mess=self.procstatus[1].get(False)
            return mess
        except:
            return None

    def get_progress(self):
        '''
        Retrieve progress from process
        '''

        try:
            progress=self.procstatus[2].get(False)
            return progress
        except:
            return None


class osprocess(object):
    '''
    Handles OS processes run for steps 
    '''
    def __init__(self):
        self.env=Environment()

    def terminate_osprocess(self,os_process):
        '''
        Terminate OS process 
        '''

        if os.name=='nt':
            sp=subprocess.Popen(['taskkill', '/F', '/T', '/PID', str(os_process.pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            outp=sp.communicate()
            return outp[0]+'\n'+outp[1]
        else:
            os_process.terminate()
        
    def run_osprocess(self, procinfo, step, command, varargs=[], environ=None,waitsecs=10):
        '''
        Start and monitor OS process
        '''

        cmdlist=varargs[:]
        try:
            paramsdict=json.loads(step['params'])
            hungsecs=None
            progfile=None
            if 'parser' in paramsdict:
                progfile, hungsecs=eval('self.'+paramsdict['parser']+'_file(varargs)')
            stopwaitsecs=hungsecs if hungsecs else 86400 #24h
            cmdlist.insert(0, command)
            os_process = subprocess.Popen(cmdlist, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, env=environ)
            prev_progress=''
            sameprogresssecs=0
            terminated=False
            count_term_attempts=0
            while os_process.poll() is None:
                mess=None
                try:
                    mess=procinfo[3].get(False)
                except:
                    mess=None
                if mess=='autoifg:terminate':
                    termout=self.terminate_osprocess(os_process)
                    if count_term_attempts<5:
                        procinfo[1].put(termout)
                        count_term_attempts+=1
                    terminated=True
                    continue
                if progfile and os.path.exists(progfile):
                    progress=eval('self.'+paramsdict['parser']+'("progress", parsefile=progfile)')
                    if progress and progress==prev_progress:
                        sameprogresssecs+=waitsecs
                    elif progress:
                        sameprogresssecs=0
                        procinfo[2].put(progress) if progress else None
                    prev_progress=progress
                    if sameprogresssecs>stopwaitsecs:
                        procinfo[1].put('process hang')
                        sameprogresssecs=0
                        self.terminate_osprocess(os_process)
                        terminated=True
                time.sleep(waitsecs)
            if 'parser' in paramsdict and not terminated:
                out_err=os_process.communicate()
                _status=eval('self.'+paramsdict['parser']+'("status",out_err)')
                _status=procinfo[0].put(_status)
                logmess=out_err[0]+'\n'+out_err[1]
                if progfile:
                    logmess+="\n##Logs : %s"%os.path.join(os.path.dirname(progfile),'Process.log')
                procinfo[1].put(logmess)
            elif terminated:
                procinfo[0].put(self.env.STEP_STATUS_FAILED)
            else:
                procinfo[0].put(self.env.STEP_STATUS_COMPLETED)
        except:
            procinfo[1].put('OS process failed\n'+traceback.format_exc())
            traceback.print_exc()


    def parsping_file(self, varargs):
        return None, None 

    def parsping(self, parsetype, out_err):
        if parsetype=='status':
            if "statistics" in out_err[0]:
                return self.env.STEP_STATUS_COMPLETED
            else:
                return self.env.STEP_STATUS_FAILED
        else:
            return None

    def parseIDLscriptout_file(self,varargs):
        '''
        Find ENVI SARscape output file for parsing progress and define time to consider process frozen
        '''
        output1=None
        for arg in varargs:
            if 'ifg' in arg:
                output1=arg
                break
        if not output1 and varargs[3]:
            output1=varargs[3]
        
        with open(self.env.configpath+self.env.idl_python_config, "r") as idl_ini:
            idl_ini_st=idl_ini.read()
            idl_ini.close()
        iniconfigdict=json.loads(idl_ini_st)
        
        output2=None
        workdirs=[wdir for wdir in iniconfigdict if 'work_dir' in wdir]
        for workdir in workdirs:
            wdir_st = workdir[0:workdir.find('_work_dir')]
            if wdir_st in varargs[1]:
                output2=iniconfigdict[workdir]
                break
        if not 'ifg' in output1:
            output1=os.path.join(output1,iniconfigdict[wdir_st+'_dir'])
        
        progfname=os.path.join(output1,output2,'work','process.working') if output1 and output2 else None
        
        hungsecs=iniconfigdict["hungsecs"] if "hungsecs" in iniconfigdict else None
            
        return progfname, hungsecs
    
        
    def parseIDLscriptout(self, parsetype, out_err=None, parsefile=None):
        '''
        Parse IDL scripts and ENVI SARscape output files for update status of completion and progress
        '''
        if parsetype=='status':
            if re.search("STEP SUCCESS",out_err[0]):
                return self.env.STEP_STATUS_COMPLETED
            else:
                return self.env.STEP_STATUS_FAILED
        elif parsetype=='progress':
            try:
                with open(parsefile, "r") as pf:
                    progress=pf.read()
                    pf.close()
                progress=progress.replace('\n', ' ').replace('\r', '')
                return progress
            except:
                return None
