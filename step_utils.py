'''
Created on 1 Nov 2017

Utilities to retrieve or update steps_log, steps_execution and service_ouput tables information

@author: Alex Apostolakis
'''
import traceback
from datetime import datetime
import time
import psycopg2
import psycopg2.extras


class steputils:
    '''
    Utilities to retrieve or update steps_log, steps_execution and service_ouput tables information
    '''
    
    def __init__(self,env, systemlog=None):
        self.env=env
        self.mglog=systemlog

    
    def update_step_log(self,output, step, status, message):
        '''
        Inserts a new entry in steps_log table
        '''
        conn=self.env.conn.postgr
        curs=conn.cursor()
        try:
            sql="insert into steps_log (output_id, step_id, logtime, message, status) values ('%s', '%s','%s','%s','%s')"%(output, step, datetime.now(), message.replace("'",'"'), status)
            curs.execute(sql)
            self.env.conn.postgr.commit()
            time.sleep(0.01) #in order to create primary key output_id, step_id, logtime
        except:
            traceback.print_exc()
            self.mglog.warning("Update step log failed"+traceback.format_exc()) if self.mglog else None
        curs.close()
        
    def get_step_log_str(self,outputid, stepid):
        '''
        Retrieves data from step log
        '''
        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            sql="select * from steps_log where output_id=%d and step_id=%d order by logtime desc"%(outputid, stepid)
            curs.execute(sql)
            slog=curs.fetchone()
            logmsg="================ STEP LOG ==================="
            while slog:
                logmsg+="\n\n%s\nSTATUS : %s\nMESSAGE:\n=========\n%s\n"%(slog['logtime'],slog['status'],slog['message'])
                slog=curs.fetchone()
            return logmsg
            
        except:
            self.mglog.warning("Get step log strings failed"+traceback.format_exc()) if self.mglog else None
        curs.close()
        
    def get_step(self, output_id, step_id):
        '''
        Retrieves a step information dictionary by query in steps, steps_executionn and service_output tables
        '''

        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        step=None
        try:
            sql="select *,se.status step_status, cast(s.params::json->>'priority' as integer) step_priority "+ \
                "from steps_execution se join service_output so on se.output_id=so.id join steps s on se.step_id=s.id " + \
                "where output_id=%d and step_id=%d"%(output_id,step_id)
            curs.execute(sql)
            step=curs.fetchone()
        except:
            traceback.print_exc()
            self.mglog.warning("Get step failed"+traceback.format_exc()) if self.mglog else None
        curs.close()
        return step
    
    def get_steps(self, query):
        '''
        Retrieves a list of steps from steps_execution table
        '''

        curs=self.env.conn.postgr.cursor()
        steps=[]
        try:
            sql="select step_id from steps_execution where %s"%query
            curs.execute(sql)
            steps=curs.fetchall()
        except:
            traceback.print_exc()
            self.mglog.warning("Get steps failed"+traceback.format_exc()) if self.mglog else None
        curs.close()
        return steps
    
    def update_step(self, output, step, value, field='status',extra=''):
        '''
        Updates step information in steps_execution table
        '''

        curs=self.env.conn.postgr.cursor()
        try:
            if value=='' or value=='NULL': 
                setval='NULL' 
            else:
                setval="'%s'"%value
            extra=','+extra if extra else ''
            sql="update steps_execution set %s=%s %s where output_id=%d and step_id=%d"%(field,setval,extra,output,step)
            curs.execute(sql)
            self.env.conn.postgr.commit()
        except:
            traceback.print_exc()
            self.mglog.warning("Update step %s failed:\n"%field+traceback.format_exc())
        curs.close()

    def get_output(self, output_id=None, order=None, where_cl=None):
        '''
        Retrieves information from an output based on query criteria
        '''

        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        output=None
        try:
            sql=self.get_output_sql(output_id, order, where_cl)
            curs.execute(sql)
            output=curs.fetchone()
        except:
            traceback.print_exc()
            self.mglog.warning("Get output failed"+traceback.format_exc()) if self.mglog else None
        curs.close()
        return output
    
            
    def iter_output(self, output_id=None, order=None, where_cl=None):
        '''
        Creates an output iterator based on query criteria
        '''

        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        output=None
        try:
            sql=self.get_output_sql(output_id, order, where_cl)
            curs.execute(sql)
            while True:
                output=curs.fetchone()
                if output:
                    yield output
                else:
                    curs.close()
                    break
        except:
            traceback.print_exc()
            self.mglog.warning("Outputs iterator failed"+traceback.format_exc()) if self.mglog else None
            curs.close()
 
    def get_outputs(self, output_id=None, order=None, where_cl=None):
        '''
        Creates an output iterator based on query criteria
        '''

        curs=self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        outputs=[]
        try:
            sql=self.get_output_simple_sql(output_id, order, where_cl)
            curs.execute(sql)
            outputs=curs.fetchall()
            curs.close()
            return outputs

        except:
            traceback.print_exc()
            self.mglog.warning("Get outputs failed"+traceback.format_exc()) if self.mglog else None
            curs.close()
    
    def get_output_sql(self, output_id=None, order=None, where_cl=None):
        '''
        Form SQL to retrieve wide range of output information combining steps
        '''

        sql_firstlast="select first_step, last_step, id oid from service_output so "+\
        "join (select min(step_id) first_step,output_id of_id from steps_execution where start_time is not NULL group by output_id) sef on so.id=sef.of_id "+\
        "join (select max(step_id) last_step,output_id ol_id from steps_execution where end_time is not NULL group by output_id) sel on so.id=sel.ol_id"

        sql="select service_id,id,output_status, first_step, se1.start_time out_start, "+\
        "last_step,se2.end_time out_end, se2.estimate_end out_est_end "+\
        "from service_output so join (%s) fl "%sql_firstlast+\
        "on so.id=fl.oid "+\
        "left join steps_execution se1 on so.id=se1.output_id and fl.first_step=se1.step_id "+\
        "join steps_execution se2 on so.id=se2.output_id and fl.last_step=se2.step_id "
        
        if output_id:
            sql+="where so.id=%d "%output_id
            
        if where_cl and output_id:
            sql+="and %s "%where_cl
        elif where_cl:
            sql+="where %s " %where_cl

        if order:
            sql+="order by %s "%order
           
        return sql

    def get_output_simple_sql(self, output_id=None, order=None, where_cl=None):
        '''
        Form simple SQL to retrieve wide output information
        '''

        sql="select service_id,id,output_status from service_output "
        
        if output_id:
            sql+="where so.id=%d "%output_id
            
        if where_cl and output_id:
            sql+="and %s "%where_cl
        elif where_cl:
            sql+="where %s " %where_cl

        if order:
            sql+="order by %s "%order
           
        return sql
    
    def update_output(self, output, value, field='output_status',extra=''):
        '''
        Updates service_output table
        '''

        curs=self.env.conn.postgr.cursor()
        try:
            if value=='' or value=='NULL': 
                setval='NULL' 
            else:
                setval="'%s'"%value
            extra=','+extra if extra else ''
            sql="update service_output set %s=%s %s where id=%d"%(field,setval,extra,output)
            curs.execute(sql)
            self.env.conn.postgr.commit()
        except:
            traceback.print_exc()
            self.mglog.warning("Update output %s failed:\n"%field+traceback.format_exc())
        curs.close()

    def inputinuse(self,input_id):
        '''
        Checks if a running step uses a specific input file
        '''

        curs=self.env.conn.postgr.cursor()
        sql="select * from service_output where inputs like '%%%s%%' and output_status='%s'"%(input_id,self.env.OUT_STATUS_PROCESSING)
        curs.execute(sql)
        if curs.rowcount>0:
            return True
        else:
            return False
 