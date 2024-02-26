'''
Created on Aug 10, 2017

Copyright (C) Alex Apostolakis - All Rights Reserved
Unauthorized copying of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Alex Apostolakis a.apostolakis@yahoo.gr, alex.apostolakis@technoesis.gr,  August 2017

Library for searching and download sentinel products with the use of metadata database

@author: Alex Apostolakis 

'''

import traceback
import requests
import hubsearchparser
import os
import hashlib
# import partial
from datetime import datetime, timedelta
import psycopg2
import psycopg2.extras
from time import strftime
import json
import xml.etree.ElementTree as ET
from io import StringIO
from functools import partial
import time
import re
import environment
import zipfile
import multiprocessing
from notifications import notification
from notifications import alerts
import operator
from __builtin__ import False
from gen_utils import gentools
import shutil

from copernicus_request_handler import get_access_token, fetch_metadata
from nt import access
from xml.sax.handler import all_properties
from hubsearchparser import check_pagination


class dbProduct(object):
    '''
    This class is used to retrieve and access the metadata of the sentinel product imagery  
    '''

    def __init__(self, env):
        self.env = env
        self.download_retries = 0

    def set_product(self, value, field="product_id"):
        '''
        Retrieve the product metadata
        '''
        curs = self.env.conn.postgr.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            sql = "select * from satellite_input where %s='%s'" % (field, value)
            curs.execute(sql)
            if curs.rowcount > 0:
                self.dbdata = curs.fetchone()
                self.mdata = {}
                if self.dbdata['params']:
                    self.mdata = json.loads(self.dbdata['params']) 
            else:
                self.dbdata = None
        except:
            traceback.print_exc()
            raise
        curs.close()
    
    def get_product_dest(self):
        '''
        Form and return the product files destination on storage
        '''
        
        # C:/GeoHub/sentinel-1/<year>/<month>/<datetime>_<orbit number>_<direction>
        dest = os.path.join(
            self.env.sentinel1path,
            str(self.dbdata['sensing_start'].year),
            str(self.dbdata['sensing_start'].month),
            datetime.strftime(self.dbdata['sensing_start'], '%Y%m%d%H%M%S') + "_" + self.dbdata['orbit'] + "_" + self.dbdata['direction']
            )
        return dest
    
    def get_orbit_dest(self):
        '''
        Form and return the orbit file destination on storage
        '''
        
        # C:/GeoHub/auxiliary/orbits/<satellite>/<year>/<month>/
        orbitdest = os.path.join(self.env.orbitspath, \
        self.dbdata['name'][0:3], \
        str(self.dbdata['sensing_start'].year), \
        str(self.dbdata['sensing_start'].month))
        return orbitdest
    
    def update_product(self, value, field=None):
        '''
        Update product metadata in satellite_input table
        '''

        if field is None:
            field = 'status'
        curs = self.env.conn.postgr.cursor()
        try:
            sql = "update satellite_input set %s='%s' where product_id='%s'" % (field, value, self.dbdata['product_id'])
            curs.execute(sql)
            self.env.conn.postgr.commit()
        except:
            # traceback.print_exc()
            # if log:
            #    self.log.warning("Update satellite input failed:\n"+traceback.format_exc()) if self.log else None
            raise
        curs.close()


class ProductUnzipper(object):
    '''
    class to unzip downloaded product
    '''

    def __init__(self, value, procstatus=None, field='product_id', env=None, log=None):
        '''
        Inits and unzip downloaded product
        '''
        
        if not env:
            self.env = environment.Environment()
        else:
            self.env = env
        self.dbprod = dbProduct(self.env)
        self.dbprod.set_product(value, field)
        
        try:
            unzip_dir = os.path.join(self.dbprod.get_product_dest(), self.env.sentinelunzip)
            if not os.path.isdir(unzip_dir):
                zip_ref = zipfile.ZipFile(os.path.join(self.dbprod.get_product_dest(), self.dbprod.dbdata['name'] + ".zip"), 'r')
                zip_ref.extractall(self.dbprod.get_product_dest())
                zip_ref.close()
                os.rename(os.path.join(self.dbprod.get_product_dest(), self.dbprod.dbdata['name'] + ".SAFE"),
                          os.path.join(self.dbprod.get_product_dest(), self.env.sentinelunzip))
            procstatus[0].put(self.env.STEP_STATUS_COMPLETED) if procstatus else None
                 
        except:
            procstatus[0].put(self.env.STEP_STATUS_FAILED) if procstatus else None
            procstatus[1].put("Zip extraction failed:\n" + traceback.format_exc()) if procstatus else None 
            traceback.print_exc()
            # self.log.warning("Zip extraction failed:\n"+traceback.format_exc()) if self.log else None
            raise


class OrbitFileDownloader(object):
    '''
    class to download orbit file
    '''

    ORB_FILE_VALID = 0
    ORB_FILE_NOT_VALID = 1
    ORB_FILE_NOT_VALIDATED = 2

    def __init__(self, orbitpath, orbitfname, procstatus=None, env=None, log=None):
        '''
        Initiates class and downloads orbit file
        '''
        
        if not env:
            self.env = environment.Environment()
        else:
            self.env = env
        self.proc = multiprocessing.current_process()
        self.pstatus = procstatus
        try:
            self.orbitpath = orbitpath
            self.orbitfile = orbitfname
            orbitfulldest = os.path.join(orbitpath, self.orbitfile)
           
            valid = self.validate_orbitfile()
            if valid == OrbitFileDownloader.ORB_FILE_NOT_VALIDATED and os.path.isfile(orbitfulldest):
                warningmess = "Orbit validation failed - using existing orbit file (not validated)"
                procstatus[1].put(warningmess)
                procstatus[0].put(self.env.STEP_STATUS_FAILED)
                if log:
                    log.error(warningmess)
            elif valid in [OrbitFileDownloader.ORB_FILE_NOT_VALID, OrbitFileDownloader.ORB_FILE_NOT_VALIDATED]:
                procstatus[1].put('Downloading Orbit File to: %s' % orbitfulldest)
                orbiturl = self.get_orbiturl(orbitfname)
                if orbiturl:
                    self.orbit_download(orbiturl)
                    if self.validate_orbitfile() == OrbitFileDownloader.ORB_FILE_VALID:
                        procstatus[0].put(self.env.STEP_STATUS_COMPLETED)
                    else:
                        procstatus[0].put(self.env.STEP_STATUS_FAILED)
                else:
                    procstatus[0].put(self.env.STEP_STATUS_FAILED)
            else:
                procstatus[1].put('Orbit File already available: %s' % orbitfulldest)
                procstatus[0].put(self.env.STEP_STATUS_COMPLETED)
                    
        except:
            errormess = "Orbit Downloader failed:\n" + traceback.format_exc()
            procstatus[1].put(errormess)
            procstatus[0].put(self.env.STEP_STATUS_FAILED)
            if log:
                log.error(errormess)

    def get_orbiturl(self, orbitfname):
        '''
        Retrieves Orbit file url
        '''

        sess = requests.session()
        orbiturl = None
        failmess = 'Orbit url retrieve failed'

        try:
            name_param = "physical_name"
            uri = self.env.orbitshub + 'api/v1/?product_type=AUX_RESORB'
            response = sess.get("%s&%s=%s" % (uri, name_param, orbitfname), verify=False)
            if response.status_code == 200: 
                resorbs = json.loads(response.content)
                orbfiledata = resorbs['results']
                if len(orbfiledata) == 1:
                    orbiturl = orbfiledata[0]['remote_url']
                else:
                    mess = '%s:\nFile %s not found' % (failmess, orbitfname)
                    self.pstatus[1].put(mess)
            else:
                mess = '%s:\nResponce code : %s, reason: %s' % (failmess, response.status_code, response.reason)
        except:
            mess = '%s:\n' % failmess + traceback.format_exc()
            self.pstatus[1].put(mess)
            # notification(self.env).send_notification("error","orbits",mess)
            
        return orbiturl

    def validate_orbitfile(self):
        '''
        Validates orbit file
        '''

        sess = requests.session()
        failmess = 'Orbit file validation failed'

        try:
            orbitfilefull = os.path.join(self.orbitpath, self.orbitfile)
    
            if not os.path.isfile(orbitfilefull):
                return OrbitFileDownloader.ORB_FILE_NOT_VALID

            name_param = "physical_name"
            uri = self.env.orbitshub + 'api/v1/?product_type=AUX_RESORB'
            response = sess.get("%s&%s=%s" % (uri, name_param, self.orbitfile), verify=False)
            if response.status_code == 200: 
                resorbs = json.loads(response.content)
                orbfiledata = resorbs['results']
                if len(orbfiledata) == 1:
                    filesize = os.path.getsize(orbitfilefull)
                    orbfilehash = orbfiledata[0]['hash'].upper()
                    with open(orbitfilefull, 'rb') as orbitfile:
                        localhash = gentools.hash_bytestr_iter(gentools.file_as_blockiter(orbitfile), hashlib.sha1(), True)
                    orbfilesize = int(orbfiledata[0]['size'])
                    if orbfilesize == filesize and localhash == orbfilehash:
                        return OrbitFileDownloader.ORB_FILE_VALID
                    else:
                        return OrbitFileDownloader.ORB_FILE_NOT_VALID
                else:
                    mess = '%s:\nFile %s not found' % (failmess, self.orbitfile)
            else:
                mess = '%s:\nResponce code : %s, reason: %s' % (failmess, response.status_code, response.reason)

            self.pstatus[1].put(mess)
            return OrbitFileDownloader.ORB_FILE_NOT_VALIDATED
                    
        except:
            mess = '%s:\n' % failmess + traceback.format_exc()
            self.pstatus[1].put(mess)
            return OrbitFileDownloader.ORB_FILE_NOT_VALIDATED
            # notification(self.env).send_notification("error","orbits",mess)

    def orbit_download(self, orb_uri):
        '''
        Downloads orbit file
        '''

        sess_orb = requests.session()
        try:
            orbdest = self.orbitpath
            
            if not os.path.isdir(orbdest):
                os.makedirs(orbdest)

            r = sess_orb.get(orb_uri, headers={}, stream=True, allow_redirects=True)
            with open(os.path.join(orbdest, self.orbitfile), 'wb') as f:
                shutil.copyfileobj(r.raw, f)
                f.close()

        except:
            # traceback.print_exc()
            mess = "Orbit download failed:\n" + traceback.format_exc()
            self.pstatus[1].put(mess)
            notification(self.env).send_notification("error", "orbits", mess)
            self.log.warning(mess) if self.log else None
            # steputils(self.env).update_step_log(self.output,self.step,self.pstatus,"Orbit download failed:\n"+traceback.format_exc()) if self.output else None
            raise
        sess_orb.close()


class Downloader(object):
    '''
    Methods for file download
    '''
    
    def __init__(self, procstatus=None, env=None, log=None): 
        if not env:
            self.env = environment.Environment()
        else:
            self.env = env
        self.pstatus = procstatus
        
        self.prevtimeslow = None
        self.prevtimemedium = None
        self.bytes_read_prev_slow = None
        self.bytes_read_prev_medium = None
        
    def downloader(self, dest, product, response, *args, **kwargs):
        '''
        Downloads and stores a file in storage destination 'dest'
        In case of slow download searches for better download sources
        Information on download progress is send to parent processes 
        '''

        # print(dest, product, response)

        _file_path = None
        _file = None
        percent = 0.0
        
        # curs = self.env.conn.postgr.cursor()
        # try:
            # sql="update satellite_input set %s='%s' where product_id='%s'"%(field,value, self.dbdata['product_id'])
            # curs.execute(sql)
            # self.env.conn.postgr.commit()
        # except:
            # #traceback.print_exc()
            # #if log:
            # #    self.log.warning("Update satellite input failed:\n"+traceback.format_exc()) if self.log else None
            # raise
        
        try:
            url = response.url
            status_code = response.status_code
            
            if status_code in (200, 206):
                
                if dest is None:
                    self.pstatus[1].put("There is not a storage path for this update_product.")
                    return
                
                if not os.path.isdir(dest):
                    os.makedirs(dest)
                
                # Get the filename from the content-disposition header.
                _file = response.headers["Content-disposition"].split(';')[1].split('=')[1]
                
                # Get the path to the file.
                _file_path = os.path.join(dest, _file)
                
                with open(_file_path, 'wb' if status_code == 200 else 'ab') as _file_obj:
                    if product:
                        product.update_product(self.env.INP_STATUS_DOWNLOADING + ' ' + "%.1f" % (percent))
                    bytes_read = self.bytes_read_prev_slow = self.bytes_read_prev_medium = os.path.getsize(_file_path)
                    self.prevtimeslow = datetime.now()
                    self.prevtimemedium = datetime.now()
                    for _chunk in response.iter_content(8192):
                        _file_obj.write(_chunk)
                        bytes_read += len(_chunk)
                        if self.check_faster_hub(bytes_read, product, url):
                            break
                        if product:
                            total_size = product.mdata['Size']  # *100
                            tmp_percent = float(bytes_read) / total_size
                            if tmp_percent - percent > 0.001:
                                percent = tmp_percent
                                product.update_product(self.env.INP_STATUS_DOWNLOADING + ' ' + "%.1f%%" % (percent*100))
                                if self.pstatus:
                                    self.pstatus[2].put(self.env.INP_STATUS_DOWNLOADING + ' ' + "%.1f%%" % (percent*100))
                if product:
                    product.update_product(self.env.INP_STATUS_AVAILABLE)
                
            elif status_code == 304:
                self.pstatus[1].put('Data already stored and valid.')
            else:
                self.pstatus[1].put('Could not get the data, Status code: %s, Reason: %s, \nURL: %s' % (response.status_code, response.reason, response.url))
                raise
        except Exception as e:
            print(e)
            self.pstatus[1].put('Error during download: ' + traceback.format_exc())
            # traceback.print_exc()
            raise

    # check for faster download hub
    def check_faster_hub(self, bytes_read, product, url):
        '''
        Check for faster download or stop download if too slow
        '''

        if bytes_read - self.bytes_read_prev_slow > self.env.slowdownloadbytes:
            curtime = datetime.now()
            if curtime - self.prevtimeslow > timedelta(seconds=self.env.slowdownloadtime):
                self.pstatus[1].put('Download too slow. Stopping download')
                return True
            self.bytes_read_prev_slow = bytes_read
            self.prevtimeslow = curtime

        if product and bytes_read - self.bytes_read_prev_medium > self.env.mediumdownloadbytes \
           and product.download_retries < self.env.stepretries - 1:
            curtime = datetime.now()
            if curtime - self.prevtimemedium > timedelta(seconds=self.env.mediumdownloadtime):
                speed, hub, checksum, httpsize = self.find_best_host(product.dbdata['product_id'], [url])
                newspeed = self.env.bestdownloadbytes * 1.0 / (speed.microseconds * 1.0) * 1000.0 if speed.microseconds > 1 else self.env.bestdownloadbytes * 1.0 / 1000.0
                oldspeed = self.env.mediumdownloadbytes * 1.0 / ((curtime - self.prevtimemedium).microseconds * 1.0) * 1000.0 if (curtime - self.prevtimemedium).microseconds > 1 else self.env.mediumdownloadbytes * 1.0 / 1000.0
                # if speed.microseconds*1.0/(2.0*self.env.bestdownloadbytes)<(curtime-self.prevtimemedium).microseconds*1.0/self.env.mediumdownloadbytes and checksum and httpsize:
                if newspeed > oldspeed * 2.0 and checksum and httpsize:
                    self.pstatus[1].put('Faster hub detected (%s) current hub speed: %s kb/sec, faster hub speed: %s kb/sec. Stopping download' % (hub['host'], oldspeed, newspeed))
                    return True
            self.bytes_read_prev_medium = bytes_read
            self.prevtimemedium = curtime
        
        return False

    def download_speed(self, speeds, response, *args, **kwargs):
        '''
        Measure download speed 
        '''

        try:
            status_code = response.status_code
            if status_code in (200, 206):
                    prevtime = datetime.now()
                    bytes_read = 0
                    for _chunk in response.iter_content(8192):
                        bytes_read += len(_chunk)
                        if bytes_read > self.env.bestdownloadbytes:
                            curtime = datetime.now()
                            speeds.append(curtime - prevtime)
                            return
        except:
            self.pstatus[1].put('Error during download speed test: ' + traceback.format_exc())
        finally:
            speeds.append(timedelta(days=1000))
            
    def find_best_host(self, product_id, exclude_hosts_url=[]):
        '''
        Find best hub according download speed 
        '''

        bestspeed = timedelta(days=1000)
        besthub = None
        checksum = None
        httpsize = None
        for hub in self.env.colhubs:
            if all(hub['host'] not in url for url in exclude_hosts_url):
                sess = requests.session()
                sess.auth = (hub['user'] , hub['pass'])
                p_uri = ProductTracer(self.env).get_uri(hub['host'], product_id)
                tmpchecksum = ProductTracer(self.env).get_property(p_uri, 'Checksum/Value', sess)
                tmphttpsize = ProductTracer(self.env).get_size_http(p_uri, sess)
                speeds = []
                try:
                    sess.get(
                        p_uri + "/$value",
                        hooks=dict(response=partial(
                            self.download_speed, speeds)
                        ),
                        headers={},
                        stream=True,
                          verify=False,
                          allow_redirects=True
                    )
                    if speeds[0] < bestspeed:
                        bestspeed = speeds[0]
                        besthub = hub
                        checksum = tmpchecksum
                        httpsize = tmphttpsize
                except:
                    self.pstatus[1].put('Error while speed test for hub %s :' % hub['host'] + traceback.format_exc())

                sess.close()
                sess = None
        if checksum and httpsize and besthub: 
            return bestspeed, besthub, checksum, httpsize
        else:
            return bestspeed, None, None, None


class ProductDownloader(object):
    '''
    Class contains methods for downloading a sentinel-1 product and update metadata information
    '''

    def __init__(self, value, procstatus=None, field='product_id', env=None, log=None):
        '''
        Initiates class, retrieves product metadata information and downloads product
        '''
        
        if not env:
            self.env = environment.Environment()
        else:
            self.env = env
        self.proc = multiprocessing.current_process()
        self.pstatus = procstatus

        if self.proc and self.proc.name.split('_')[0] == 'step':
            self.output = int(self.proc.name.split('_')[1])
            self.step = int(self.proc.name.split('_')[2])
        try:
            self.dbprod = dbProduct(self.env)
            self.dbprod.set_product(value, field)
            if not self.dbprod.dbdata:
                procstatus[0].put(self.env.STEP_STATUS_FAILED) if procstatus else None
                return
            self.ptracer = ProductTracer(self.env)
            self.sess = None
            self.p_uri = None
            self.http_headers = {}
            self.log = log
            self.product_download()

        except:
            errormess = "Product Downloader failed:\n" + traceback.format_exc()
            procstatus[1].put(errormess)
            procstatus[0].put(self.env.STEP_STATUS_FAILED)
            if self.log:
                self.log.error(errormess)

    def find_host_session(self):

        '''
        Finds a working hub that contains the product
        '''

        for hub in self.env.colhubs:
            self.sess = requests.session()
            self.sess.auth = (hub['user'] , hub['pass'])
            self.p_uri = self.ptracer.get_uri(hub['host'], self.dbprod.dbdata['product_id'])
            self.checksum = self.ptracer.get_property(self.p_uri, 'Checksum/Value', self.sess)
            self.httpsize = self.ptracer.get_size_http(self.p_uri, self.sess)
            if self.checksum and self.httpsize: 
                return
            self.sess.close()
            self.sess = None     

    def set_host_session(self, hub, checksum, httpsize, token, product_id, username, password):
        '''
        Prepare the class properties to download from a hub host that contains the product
        ''' 
        self.sess = requests.session()
        self.sess.auth = (username , password)
        self.p_uri = hub + "/odata/v1/Products(" + product_id + ")"
        self.httpsize = httpsize
        self.token = token
        self.checksum = checksum
        
    def set_product_dest(self, product):
        '''
        Sets the product destination
        '''
        
        self.dest = product.get_product_dest()
        return self.dest

    def decide_download(self, uri, filename, status, knownsize=0, knownchecksum="", product=None):
        
        '''
        Decides to download a product from start, not download at all or continue download
        based on existing files and metadata information
        '''
        
        mess = "File ok"
        filepath = os.path.join(self.dest, filename)
        if os.path.isfile(filepath):
            filesize = os.path.getsize(filepath)
            #httpsize = 0
            #checksum = ""
            # if product:
            #    httpsize=self.httpsize
            #    checksum=self.checksum
            
            size_and_checksum_ok = False
            
            # To-Do check logic with filesize and excepted from field
            if filesize == knownsize:
                self.pstatus[2].put('Calculating checksum')
                with open(filepath, 'rb') as inpfile:
                    localchecksum = gentools.hash_bytestr_iter(gentools.file_as_blockiter(inpfile), hashlib.md5(), True)
                    
                if localchecksum.upper() == knownchecksum.upper():
                    size_and_checksum_ok = True
                else:
                    mess = "Checksum control failed"
            else:
                mess = "File size different than size declared in odata"

            if status != self.env.INP_STATUS_AVAILABLE:
                if re.match("^%s" % self.env.INP_STATUS_DOWNLOADING, status):
                    time.sleep(20)
                    filesize5 = os.path.getsize(filepath)
                    if filesize5 != filesize:
                        return False, "File is currently downloading"  # update_product is currently downloading
                if filesize < knownsize:  # product is (probably) partially downloaded
                    # self.http_headers = {'Range': 'bytes=%s-'%(filesize)}
                    self.http_headers = {}  # partial download is not working anymore. Force full download
                elif size_and_checksum_ok:  # product is already downloaded
                    if product:
                        product.update_product(self.env.INP_STATUS_AVAILABLE)
                    return False, mess
                else:
                    self.http_headers = {}  # product is corrupted, force full download
            elif status == self.env.INP_STATUS_AVAILABLE and not size_and_checksum_ok:
                    self.http_headers = {}
            else:  # update_product is already downloaded
                return False, mess
                # self.http_headers = {'If-Modified-Since': http_now}
        else:
            mess = "File does not exists. Starting Download"
        return True, mess
    
    def product_download(self):

        '''
        Downloads Quick look icon and full product
        '''       
        
        try: 
            
            self.downloadhub=self.env.colhubs[0]
            # self.find_host_session()
            username = self.downloadhub['user']
            password = self.downloadhub['pass']
            huburl = self.downloadhub['host']
            tokenfile = os.path.join(self.env.configpath,self.downloadhub['token'])
            self.token = get_access_token(username, password, tokenfile)

            downloader_obj = Downloader(self.pstatus, self.env)
            downloader = downloader_obj.downloader
            self.set_product_dest(self.dbprod)
            #url = 'https://catalogue.dataspace.copernicus.eu/odata/v1/Products'
                
            params_dict = self.dbprod.mdata               
            if 'Checksum' not in params_dict:
                params_dict['Checksum'] = self.get_checksum(huburl, self.dbprod.dbdata['product_id'])
                self.dbprod.update_product(json.dumps(params_dict), 'params')
                
            checksum = params_dict['Checksum']
            httpsize = params_dict['Size']

            self.set_host_session(hub=huburl, checksum=checksum, httpsize=httpsize, token=self.token,
                                  product_id=self.dbprod.dbdata['product_id'], username=username, password=password)

            file_name = self.dbprod.dbdata['name'] + '.zip'
            product_download_url = self.p_uri
            product_status = self.dbprod.dbdata['status']
            product_size = self.dbprod.mdata['Size']
            product_id = self.dbprod.dbdata['product_id']
            
            need_download, checkmess = self.decide_download(
                product_download_url,
                file_name,
                product_status,
                product_size,
                checksum,
                self.dbprod
                )
            
            self.pstatus[1].put(checkmess)
           
            while self.dbprod.download_retries < self.env.stepretries - 1 and need_download:
                
                self.pstatus[1].put(
                    'Start downloading {}'.format(product_download_url)
                    )
                
                url = 'https://zipper.dataspace.copernicus.eu/odata/v1/Products'
                product_id = self.dbprod.dbdata['product_id']
                product_download_url = url + "({})/$value".format(product_id)
                
                access_token = get_access_token(username, password, tokenfile)
                headers = {'Authorization': 'Bearer {}'.format(access_token)}
                
                self.sess = requests.Session()
                self.sess.headers.update(headers)
                
                self.sess.get(
                    product_download_url,
                    hooks=dict(response=partial(
                        downloader,
                        self.dest,
                        self.dbprod)
                        ),
                    headers=headers,
                    stream=True,
                    verify=False
                    )
                self.dbprod.download_retries += 1
                
                uri = self.p_uri
                file_name = self.dbprod.dbdata['name'] + '.zip'
                need_download, checkmess = self.decide_download(
                    uri,
                    file_name,
                    product_status,
                    product_size,
                    checksum,
                    self.dbprod)
                
                self.pstatus[1].put(checkmess)
                if need_download:
                    self.pstatus[1].put('Retry Download')
                    speed, hub, checksum, httpsize = downloader_obj.find_best_host(self.dbprod.dbdata['product_id'])
                    if hub:
                        self.set_host_session(hub, checksum, httpsize)
                    else:
                        self.pstatus[1].put('No hub found for download')
                        break

            if not need_download:
                self.pstatus[0].put(self.env.STEP_STATUS_COMPLETED)
                
            else:
                self.pstatus[1].put('Downloaded file check failed')
                self.pstatus[0].put(self.env.STEP_STATUS_FAILED)
        
        except Exception as e:
            traceback.print_exc()
            self.log.Info("Satellite input download failed:\n" + traceback.format_exc()) if self.log else None
            raise

    def get_checksum(self, hub, product_id):
        headers = {'Authorization': 'Bearer {}'.format(self.token)}
        
        #print(self.p_uri, headers)
        
        try:
            p_uri =  hub + "/odata/v1/Products(" + product_id + ")"
            response = requests.get(p_uri, headers=headers)
            response.raise_for_status()          
            parsed_data = response.json()       
            checksum = parsed_data['Checksum'][0]['Value']
            
        except requests.exceptions.RequestException as e:
            print("Metadata fetch attempt failed. Retrying...\n{}".format(e)) 
                       
        return checksum 
    


class ProductTracer(object):
    '''
    Methods to search Copernicus hub for sentinel products
    '''    

    def __init__(self, env, log=None):
        hubs = None
        hubs = env.colhubs if hubs == None else hubs
        self.env = env
        self.log = log
        self.al = alerts(self.env, self.log)
        tokenfile = os.path.join(self.env.configpath,self.env.colhubs[0]['token'])
        self.session_token = get_access_token(hubs[0]['user'], hubs[0]['pass'], tokenfile)
    
    def add_seconds_to_timestamp(self, timestamp_str, seconds_to_add):
        # Convert the string to a datetime object
        timestamp_dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    
        # Add specified seconds
        new_timestamp_dt = timestamp_dt + timedelta(seconds=seconds_to_add)
    
        # Convert the updated datetime object back to a string
        new_timestamp_str = new_timestamp_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
        return new_timestamp_str
    
    # Change query from old OSearch API request to the new datasapce OSeach API request
    def query_transform(self, query):
        q = {}
        
        for e in query.split(" AND "):
            line = e.strip()
            

            if line.startswith('beginposition'):
                startDate, completionDate = line.split('beginposition:')[1].split(" TO ")
                q['startDate'] = startDate.split('[')[1]
                q['completionDate'] = self.add_seconds_to_timestamp(completionDate.split(']')[0], 40)
                
            if line.startswith('ingestiondate'):
                publishedAfter, publishedBefore = line.split('ingestiondate:')[1].split(" TO ")
                q['publishedAfter'] = publishedAfter.split('[')[1]
                q['publishedBefore'] = publishedBefore.split(']')[0]
                
            if line.startswith('footprint'):
                q['geometry'] = line.split('sects(')[1][:-2].strip()
                
            if line.startswith('producttype:'):
                q['productType'] = line.split('producttype:')[1].strip()
                
            if line.startswith('relativeorbitnumber:'):
                q['relativeOrbitNumber'] = line.split('number:')[1].strip()
            
            if line.startswith('sensoroperationalmode:'):
                q['sensorMode'] = line.split('sensoroperationalmode:')[1].strip()
            
            if line.startswith('filename:S1A_'):
                q['platform'] = 'S1A'
                
            if line.startswith('filename:S1B_'):
                q['platform'] = 'S1B'
    
        final = ''
        
        for i, (k, v) in enumerate(q.items()):
            final += k + '=' + v
            if i == len(q) - 1:
                break
            final += "&"
            
        return final
    
    def checkhubs(self):
        try:
            self.besthubs = []
            for hub in self.env.colhubs:
                hubnew = hub.copy()
                hubnew['delay'] = timedelta(days=50)
                
                self.sess.auth = (hub['user'] , hub['pass'])
                
                query = self.format_query(datetime.utcnow() - timedelta(minutes=600), datetime.utcnow(), self.env.ifg_filters, "", "ingestiondate")
                
                response = self.sess.get(hub['host'] + 'search', params={'q': query, 'start': 0, 'rows': 10}, verify=False)
                
                if response.status_code == 200:
                    entries = hubsearchparser.parse_opensearch(response.content)
                    
                    if entries:
                        entries.sort(key=operator.itemgetter('Ingestion date'))
                        ingestion = datetime.strptime(entries[-1]['Ingestion date'][:19], '%Y-%m-%dT%H:%M:%S')
                        hubnew['delay'] = datetime.utcnow() - ingestion
                        
                self.besthubs.append(hubnew)
        except:
            self.log.error("Checking Hub efficiency failed" + traceback.format_exc()) if self.log else None
            traceback.print_exc()

    def format_query(self, fromdate, todate, filters_st, roi, datesearch):
        '''
        Form hub query
        '''
        fromdate_st = fromdate.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        todate_st = todate.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        filters = filters_st.split(',')
        filtstring = ''
        
        for afilter in filters:
            if afilter:
                filtstring = filtstring + ' AND ' + afilter
        
        roistring = ''
        
        if roi:
            roistring = 'AND footprint:"Intersects(%s)"' % roi
            
        query = '%s:[%s TO %s] %s %s' % (datesearch, fromdate_st, todate_st, roistring, filtstring)
        
        return query
    
    def product_seeker(self, fromdate, todate, filters_st, roi="", datesearch="beginposition", start=0, rows=100, hubs=None):
        '''
        Seek products that meet hub query
        '''
    
        hubs = self.env.colhubs if hubs == None else hubs

        self.sess = requests.session()
        
        old_query = self.format_query(fromdate, todate, filters_st, roi, datesearch)
        #self.log.info('Old Query: ' + old_query)     
        new_query = self.query_transform(old_query)
                    
        try:
            for hub in hubs:
                
                url = hub['host']
                access_token = self.session_token
                endpoint = '/resto/api/collections'
                query = '/SENTINEL-1/search.json?' + new_query
                self.log.info('New Query: ' + new_query)


                pages = 0
                response = fetch_metadata(url=url, endpoint=endpoint, access_token=access_token, session=self.sess, query=query)

                renspose_data = []

                pages = 1
                while True:
                    
                    parsed_data = response
                    
                    if parsed_data.get('features') is not None:
                        
                        for d in parsed_data['features']:
                            renspose_data.append(d)
                    
                    if check_pagination(parsed_data):
                        pages += 1
                        if pages > hub["maxpages"]:
                            self.log.info("Query exceeded maximum paging number current {}".format(pages))
                            break
                        
                        page_query = query + '&page={}'.format(pages) 
                            
                        response = fetch_metadata(url=url, endpoint=endpoint, access_token=access_token, session=self.sess, query=page_query)                        
                        self.log.info('New Query: ' + page_query)                        
                        #if response == None:
                        #    self.log.info('failed to get next query page')
 
                    else:
                        break

                data = hubsearchparser.parse_opensearch(renspose_data)
                # print(data)
                if data:
                    self.log.info("Successfull search request to %s :\n" % hub['host'])
                    self.al.alert_off("hub : %s" % hub['host'])
                else:
                    # TODO
                    self.log.info("Response failed, no data available for {}\nHost: {}".format(new_query, hub['host']))
                    
        # Problem on rensponse
        except Exception as err:
            if self.log:
                self.log.info("Error {}".format(err))
                self.log.error("request to %s failed:\n" % hub['host'] + traceback.format_exc())
                
        # Returning data
        finally:
            return data
            self.sess.close()
        
    def get_uri(self, host, product_id):
        '''
        Forms and Returns a sentinel product uri for download
        '''
        return host + "odata/v1/Products('%s')/" % product_id if host and product_id else None
        
    def get_size_http(self, uri, sess=None):
        '''
        Retrieves product size from uri
        '''

        size = None
        if not sess:
            sess = self.sess
        try:
            response = sess.get(uri, verify=False)
            if response.status_code == 200:
                findsize = ET.fromstring(response.content)
                ns = dict([ node for _, node in ET.iterparse(StringIO(unicode(response.content, "utf-8")), events=['start-ns']) ])      
                size = int(findsize.find(".//d:ContentLength", ns).text)
            
            else:
                self.log.warning("Could not get size for update_product %s. Status code: %s. Reason: %s" % (uri, response.status_code, response.reason))\
                if self.log else None
        except:
            self.log.warning("Error getting update_product size:\n" + traceback.format_exc()) if self.log else None
        
        return size
    
    def get_property(self, uri, _property, sess=None):
        '''
        Retrieves a product property from hub
        '''

        value = None
        if not sess:
            sess = self.sess
        
        try:
            response = sess.get(uri + _property + '/$value', verify=False)
            
            if response.status_code == 200:
                value = response.content
            else:
                self.log.warning("Could not get property %s for update_product %s. Status code: %s. Reason: %s" % (_property, uri, response.status_code, response.reason))\
                if self.log else None
        except:
            self.log.warning("Error getting property %s:\n" % _property + traceback.format_exc()) if self.log else None
        return value
    
    def get_manifest(self, uri, name):
        '''
        Retrieves the product manifest from hub
        '''

        manifest = {}
        try:
            response = self.sess.get(uri + "Nodes('%s.SAFE')/Nodes('manifest.safe')/$value" % name, verify=False)
            
            if response.status_code == 200:
                manifest = hubsearchparser.parse_safe(response.content)
            else:
                self.log.warning("Could not get manifest for update_product %s. Status code: %s. Reason: %s" % (response.url, response.status_code, response.reason))\
                if self.log else None
        except:
            self.log.warning("Error getting manifest:\n" % +traceback.format_exc()) if self.log else None
        return manifest

        
