'''
Created on 11 Feb 2018

Contains class with methods to retrieve quake events from usgs or emsc APIs
@author: alex
'''

import requests
from datetime import datetime
from datetime import timedelta
import json
import traceback
from fileutils import fileutils
import re
from geomtools import geomtools
import os


class EventDetection(object):
    def __init__(self,env,log):
        '''
        Initiates environment and log 
        '''
        self.env=env
        self.log=log
            
    def get_starttime(self):
        '''
        Return start time for searching events 
        '''

        starttime=datetime.utcnow()-timedelta(minutes=self.env.eventpastrange)
        starttime_st=starttime.strftime("%Y-%m-%dT%H:%M:%S")
        return starttime_st

    def get_minmag(self):
        '''
        Return minimum magnitude
        '''

        return self.env.minmagnitude


    def get_usgs_uri(self):
        '''
        query usgs event API
        
        uri example:
        https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2018-02-21T12:19:58&minmagnitude=5
        '''
        baseuri="http://www.seismicportal.eu/fdsnws"
        uri="%s/event/1/query?format=json&starttime=%s&minmagnitude=%.1f"%(baseuri,self.get_starttime(),self.get_minmag())
        
        return uri

    def get_emsc_uri(self):
        '''
        query emsc event API

        uri example:
        http://www.seismicportal.eu/fdsnws/event/1/query?starttime=2018-03-18&format=json&minmagnitude=5.5        
        '''
       
        #baseuri="http://www.seismicportal.eu/fdsnws"
        baseuri="https://www.seismicportal.eu/fdsnws"
        uri="%s/event/1/query?format=json&starttime=%s&minmagnitude=%.1f"%(baseuri,self.get_starttime(),self.get_minmag())
        
        return uri
        
    def get_last_quakes_emsc(self):
        '''
        Returns last quakes from emsc
        '''

        return self.get_last_quakes(self.get_emsc_uri())
        
    def get_last_quakes_usgs(self):
            
        '''
        Returns last quakes from usgs
        '''
        
        return self.get_last_quakes(self.get_usgs_uri())

    def get_last_quakes(self,uri):
        
        '''
        Queries uri and returns last quakes
        '''

        sess=requests.session()

        try:
            response = sess.get(uri, verify=False)
            if response.status_code == 200:
                quakes_js = json.loads(response.content)
                return quakes_js['features']
            else:
                if not self.env.eventerrornotif or datetime.now()-self.env.eventerrornotif>timedelta(minutes=60):
                    self.log.error("Response error from %s\nResponce code : %s, reason: %s"%(uri,response.status_code,response.reason))
                    self.env.eventerrornotif=datetime.now()
                return []
        except:
            if not self.env.eventerrornotif or datetime.now()-self.env.eventerrornotif>timedelta(minutes=60):
                self.log.error("error in detecting event from %s :"%uri+traceback.format_exc())
                self.env.eventerrornotif=datetime.now()
            return []
        
    def save_trigger_config(self, fname, quake_store_st, logmsg):
        with open(os.path.join(self.env.configpath,fname), 'w') as f:
            f.write(quake_store_st)
            f.close()
            if self.env.DEBUG:
                self.log.debug(logmsg)

    def store_quake(self,detected_quake,source):
        
        '''
        Store quake in json file
        '''

        quake_to_store={}
        if self.env.DEBUG:
            self.log.debug("detected quake to store: %s :"%detected_quake)
        try:
            if source=="emsc":
                quake_to_store["name"]=detected_quake["properties"]["flynn_region"]
                timest=re.match('[^\\.]*',detected_quake["properties"]["time"]).group(0)
                quake_to_store["time"]=datetime.strptime(timest,'%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                quake_to_store["depth"]=detected_quake["properties"]["depth"]
            elif source=="usgs":
                quake_to_store["name"]=detected_quake["properties"]["title"]
                quake_to_store["time"]=datetime.fromtimestamp(int(detected_quake["properties"]["time"])/1000).strftime('%Y-%m-%d %H:%M:%S')
            quake_to_store["magnitude"]=detected_quake["properties"]["mag"]
            quake_to_store["epicenter"]="POINT (%s %s)"%(detected_quake["geometry"]["coordinates"][0],detected_quake["geometry"]["coordinates"][1])
            if source=="emsc":
                basefname="%s%s"%(self.env.eventfileprefix,detected_quake["properties"]["unid"])
                quake_to_store["qid"]=detected_quake["properties"]["unid"]
            elif source=="usgs":
                basefname="%s%s"%(self.env.eventfileprefix,detected_quake["id"])
                quake_to_store["qid"]=detected_quake["id"]
            quake_store_st=json.dumps(quake_to_store,ensure_ascii=False)
            fname="%s.json"%basefname
            existfiles=[f for f in fileutils().find_files(self.env.configpath, basefname+'*')]
            if len(existfiles)==0:
                self.save_trigger_config(fname,quake_store_st, "detected quake stored")
            else:
                #check if detected event params are changed
                for fn in existfiles:
                    if self.env.processed_trigger in fn:
                        with open(fn, 'r') as f:
                            saved_quake = json.loads(f.read())
                            if 'qid' in saved_quake and not saved_quake == quake_to_store:
                                #changed_params=[k for k in saved_quake if saved_quake[k]!=quake_to_store[k]]
                                #if "time" in changed_params 
                                #if saved_quake["time"]==quake_to_store["time"] and saved_quake["name"]==quake_to_store["name"]:
                                self.save_trigger_config(fname,quake_store_st, "changed detected quake stored")
        except:
            self.log.error("fail to store detecting event : %s :"%detected_quake)

    def store_last_quakes_usgs(self,quakes):
        '''
        Store quakes from usgs
        '''

        self.store_last_quakes(quakes,"usgs")

    def store_last_quakes_emsc(self,quakes):
        '''
        Store quakes from emsc
        '''

        self.store_last_quakes(quakes,"emsc")
            
    def store_last_quakes(self,quakes,source):
        
        '''
        Store found quakes from source according conditions
        '''

        try:
            for quake in quakes:
                ec_in_greece=geomtools.point_in_greecepoly(quake["geometry"]["coordinates"])
                if  (ec_in_greece and quake["properties"]["mag"]>=self.env.minmagnitudegreece) \
                    or (not ec_in_greece and quake["properties"]["mag"]>=self.env.minmagnitudeworld):
                    self.store_quake(quake,source)
        except:
            self.log.error("error storing %s event"%source+traceback.format_exc())


