'''
Created on 8 Oct 2018

@author: Alex Apostolakis

Class for publishing event results
'''

import os
from environment import Environment
import shutil
from fileutils import fileutils
import traceback
from geomtools import geomtools
from notifications import notification as notif
from datetime import datetime
import re
import json
from ftplib import FTP, all_errors
import ogr
import urllib2
import webdbinterface
import pysftp


class Publish(object):
    '''
    Publish results by copying files to the appropriate location
    '''

    def __init__(self, eventid, outdir, pubstat, fileset='ifg', procstatus=None, env=None, log=None, archive = False, notify = True, overwrite = True):
        '''
        Constructor
        '''
        
        try:
            if not env:
                self.env=Environment()
            else:
                self.env=env
            
            self.filesdict = {}
            
            self.pstatus=procstatus
            self.log=log
            self.eventdict=None
            self.sendnotif = notify
            self.overwrite = overwrite
            self.fileset = fileset
            self.eventid = eventid
            self.warning=''

            self.get_fileset()  
            
            if not archive:
                self.datapath = self.env.datapath
            else:
                self.datapath = self.env.archiveroot+self.env.eventsdir
            
            self.publish_output(outdir, pubstat)

            self.logmess(self.env.STEP_STATUS_COMPLETED,0)
            
        except:
            self.logmess("Output publishing failed:\n"+traceback.format_exc())
            self.logmess(self.env.STEP_STATUS_FAILED,0)
                
    
    
    def get_fileset(self):
        if self.fileset=='ifg':
            #High resolution
            self.filesdict['highres_ifg'] = self.env.pub_highres_ifg
            #Thumbnail
            self.filesdict['thumbnail'] = self.env.pub_humbnail
            #kml
            self.filesdict['kml'] = self.env.pub_kml
            #Low resolution
            self.filesdict['lowres_ifg'] = self.env.pub_lowres_ifg
        elif self.fileset=='unw':
            self.filesdict['unw_kml']='file_result_reflat_geo_disp_ql.kml'
            self.filesdict['unw_tif']='file_result_reflat_geo_disp_ql.tif'
            self.filesdict['unw_tif_sml']='file_result_reflat_geo_disp_ql.tif.sml'
            self.filesdict['unw_cc_kml']='file_result_Interf_cc_ql_geo_ql.kml'
            self.filesdict['unw_cc_tif']='file_result_Interf_cc_ql_geo_ql.tif'
            self.filesdict['unw_cc_tif_sml']='file_result_Interf_cc_ql_geo_ql.tif.sml'
            
            '''
            # LOS files from SarScape

            for ext in ['_ILOS','_ALOS','']:
                basekey='unw_%s'%ext
                basefile='file_result_reflat_geo_disp%s'%ext
                for ext2 in ['','.hdr','.sml']:
                    self.filesdict[('%s_%s'%(basekey,ext2)).replace('.','')]='%s%s'%(basefile,ext2)
            '''
                
    def ftp_login(self, ftppublisher):
        if ('ftptype' in ftppublisher and ftppublisher['ftptype']=='ftp') or not 'ftptype' in ftppublisher:
            ftp = FTP(ftppublisher["domain"])     
            ftp.login(ftppublisher["user"],ftppublisher["pass"])
        elif ftppublisher['ftptype']=='sftp':
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None
            ftp=pysftp.Connection(host=ftppublisher["domain"], username=ftppublisher["user"], password=ftppublisher["pass"], cnopts = cnopts)
        else:
            raise
            return None
        return ftp

        
    def ftp_directory_exists(self,folder,ftp, ftptype):
        if not ftptype or ftptype=='ftp':
            filelist = []
            ftp.retrlines('LIST',filelist.append)
            for f in filelist:
                if f.split()[-1] == folder and f.upper().startswith('D'):
                    return True
            return False
        elif ftptype=='sftp':
            return ftp.isdir(folder)

    def ftp_chdir(self, folder, ftp, ftptype): 
        if self.ftp_directory_exists(folder,ftp, ftptype) is False: 
            if not ftptype or ftptype=='ftp':
                ftp.mkd(folder)
            elif ftptype=='sftp':
                ftp.mkdir(folder)
        self.ftp_cwd(folder,ftp, ftptype)
            
    def ftp_cwd(self,folder, ftp, ftptype): 
        if not ftptype or ftptype=='ftp':
            ftp.cwd(folder)
        elif ftptype=='sftp':
            ftp.chdir(folder)
        
        
    def ftp_put(self, ftp, ftpname, localname, ftptype):
        if not ftptype or ftptype=='ftp':
            ftp.storbinary('STOR '+ftpname, open(localname, 'rb'))
        elif ftptype=='sftp':
            ftp.put(localname)

    def ftp_isfile(self, ftp, fname, ftptype):
        if not ftptype or ftptype=='ftp':
            return False
        else:
            return ftp.isfile(fname)
        
    def ftp_rmTree(self, path, ftp):
        """Recursively delete a directory tree on a remote server."""
        wd = ftp.pwd()
    
        try:
            names = ftp.nlst(path)
        except all_errors as e:
            # some FTP servers complain when you try and list non-existent paths
            self.logmess('FtpRmTree: Could not remove {0}: {1}'.format(path, e))
            return
    
        for name in names:
            if os.path.split(name)[1] in ('.', '..'): continue
    
            #self.logmess('FtpRmTree: Checking {0}'.format(name))
    
            try:
                ftp.cwd(name)  # if we can cwd to it, it's a folder
                ftp.cwd(wd)  # don't try a nuke a folder we're in
                self.ftp_rmTree(name, ftp)
            except all_errors:
                ftp.delete(name)
        try:
            ftp.rmd(path)
        except all_errors as e:
            self.logmess('FtpRmTree: Could not remove {0}: {1}'.format(path, e))
            
    def ftp_quit(self, ftp, ftptype):
        if not ftptype or ftptype=='ftp':
            ftp.quit()
        elif ftptype=='sftp':
            ftp.close()

        

    def splitallpath(self,path):
        allparts = []
        while 1:
            parts = os.path.split(path)
            if parts[0] == path:  # sentinel for absolute paths
                allparts.insert(0, parts[0])
                break
            elif parts[1] == path: # sentinel for relative paths
                allparts.insert(0, parts[1])
                break
            else:
                path = parts[0]
                allparts.insert(0, parts[1])
        return allparts
    
    def get_eventdata(self, outdir):
        eventfolder=os.path.basename(os.path.dirname(os.path.dirname(outdir)))

        if self.eventdict:
            eventname = self.eventdict["name"]
            eventdate_st =  self.eventdict["time"]
            eventdate = datetime.strptime(eventdate_st,'%Y-%m-%d %H:%M:%S')
            epicenter = ogr.CreateGeometryFromWkt(self.eventdict["epicenter"])
        else:
            eventdate_st = re.search("[^_]+$",eventfolder).group(0)    
            eventdate= datetime.strptime(eventdate_st,'%Y%m%d%H%M%S')
            eventname = re.match("^.*_",eventfolder).group(0)[:-1]

        # "depth": 10.0, "magnitude": 5.8
        
        #eventdate_st = re.search("[^_]+$",eventfolder).group(0)
        
        outname=os.path.basename(os.path.dirname(outdir))
        outprops=outname.split('_')
        
        master_date = datetime.strptime(outprops[1],'%Y%m%d%H%M%S')
        slave_date = datetime.strptime(outprops[2],'%Y%m%d%H%M%S')
        copre = 'co' if master_date < slave_date else 'pre'
        orbit = outprops[3]
        direction = outprops[4]
        
        try:        
            mag = self.eventdict["magnitude"]
            depth = self.eventdict["depth"]
        except:
            mag = None
            depth = None
            
        return eventname, eventdate_st, eventdate, mag, depth, epicenter.GetY(),epicenter.GetX()

    def get_outputdata(self, outdir):
        outname=os.path.basename(os.path.dirname(outdir))
        outprops=outname.split('_')
        
        master_date = datetime.strptime(outprops[1],'%Y%m%d%H%M%S')
        slave_date = datetime.strptime(outprops[2],'%Y%m%d%H%M%S')
        copre = 'co' if master_date < slave_date else 'pre'
        
        return outname, outprops[1], outprops[2], copre, outprops[3], outprops[4]
    
    def notif_message(self, outdir):
        '''
        Send notification message about publishing
        '''

        eventfolder=os.path.basename(os.path.dirname(os.path.dirname(outdir)))
            
        eventname, eventdate_st, eventdate, mag, depth, lat, lon = self.get_eventdata(outdir)
        
        outname, masterdate_st, slavedate_st, copre, orbit, direction = self.get_outputdata(outdir)
        
        #outname = os.path.basename(os.path.dirname(outdir))
        #outprops = outname.split('_')
        
        master_date = datetime.strptime(masterdate_st,'%Y%m%d%H%M%S')
        slave_date = datetime.strptime(slavedate_st,'%Y%m%d%H%M%S')
        
        titlepref = '%s %s' %(eventname, eventdate)
        fileset = 'Interferogram' if self.fileset=='ifg' else 'Unwrapped phase'
        titlsuf ='Published %s-seismic output %s (orbit: %s, direction: %s)'%(copre, fileset, orbit, direction)

        try:        
            magdepth = 'magnitude: %s, depth: %s'%(mag ,depth)if self.eventdict else ""
        except:
            magdepth = ""
        
        message = '%s-seismic output published for event %s %s'%(copre, eventname,eventdate) +\
       '\n%s'%magdepth +\
       '\n------------------------------------------------------------------' + \
       '\nOrbit : %s'%orbit + \
       '\nDirection : %s'%direction + \
       '\nMaster: %s'%master_date + \
       '\nSlave : %s'%slave_date
        
        '''
        url example 
        http://geohub.idcom.gr/preview/?id=co_20190916130444_20190928130444_100_ASCENDING&event=PAKISTAN_20190924110155&location=PAKISTAN&depth=10%20km&magnitude=6.1&lat=33.03&lon=73.78
        '''
        if self.env.publishpreviewpage:
            #previewpage = "http://geohub.idcom.gr/preview/"
            '''
            previewpage=self.env.publishpreviewpage
            if self.eventdict and "magnitude" in self.eventdict.keys() and "depth" in self.eventdict.keys():
                mag = self.eventdict["magnitude"]
                depth = self.eventdict["depth"]
                epicenter = ogr.CreateGeometryFromWkt(self.eventdict["epicenter"])
                depth_st="%s km"%depth
                url = "%s?id=%s&event=%s&location=%s&depth=%s&magnitude=%s&lat=%.2f&lon=%.2f"\
                %(previewpage,outname,eventfolder,urllib2.quote(eventname),urllib2.quote(depth_st),mag,epicenter.GetY(),epicenter.GetX())
            '''
            url=self.env.publishpreviewpage
            message+="\n\nPreview Link:\n%s\n"%url
        
        attlist=[]
        if self.fileset == 'ifg':
            attlist = [os.path.join(outdir,self.filesdict['lowres_ifg'])]  
        #else:
        #    attlist = [os.path.join(outdir,self.filesdict['unw_tif'])]
        
        if self.warning!='':
            message+='\n\n'+ self.warning
            
        notif(self.env).send_notification('publish', 'content', message, titlsuf, titlepref, attachments=attlist)
        
    def publishtowebdb(self, outdir, ftppublisher):

        outdir_array=self.splitallpath(outdir)
        outftpfolder=os.path.join(outdir_array[-3],outdir_array[-2],outdir_array[-1])
        tifffilepath = os.path.join(outftpfolder,self.filesdict['highres_ifg'])
        lowresfilepath = os.path.join(outftpfolder,self.filesdict['lowres_ifg'])
        kmlfilepath = os.path.join(outftpfolder,self.filesdict['kml'])
        
        eventname, eventdate_st, eventdate, mag, depth, lat, lon = self.get_eventdata(outdir)
        
        mysqlcon = webdbinterface.mysql_connection()
        
        evid_new = webdbinterface.getEventID(mysqlcon, evid=self.eventid)
        evid_dt = webdbinterface.getEventID(mysqlcon, eventname, eventdate_st)
        
        if evid_dt is None and evid_new is None:
            evid = webdbinterface.insert_pub_event(mysqlcon, eventname, mag, depth, eventdate_st, lat, lon, None, None, self.eventid)
        elif evid_new:
            evid = webdbinterface.update_pub_event(mysqlcon, evid_new, eventname, mag, depth, eventdate_st, lat, lon, None, None)
        elif evid_dt and evid_new is None:
            evid=evid_dt
        outname, masterdate, slavedate, copre, orbit, direction = self.get_outputdata(outdir)
        
        webdbinterface.insert_pub_output(mysqlcon, evid, ftppublisher["relftpfolder"], self.datapath,'%s-seismic'%copre, masterdate, slavedate, int(orbit), direction, tifffilepath, lowresfilepath, kmlfilepath)
        #delete_ev_pub_output(mysqlcon, evid)
        #delete_pub_event(mysqlcon, evid)
        
    def transfer_files(self, outdir, ftppublisher):
        
        ftpdomain = ftppublisher["domain"]
        ftpfolder = ftppublisher["ftpfolder"]
        copyfiles = eval(ftppublisher["copyfiles"])
        ftpfiles = eval(ftppublisher["ftpfiles"])
        skiplargeftp = eval(ftppublisher["skiplargeftp"])
        webdb = eval(ftppublisher["webinterfacedb"]) if self.fileset=='ifg' else False
        ftppublisher_type = ftppublisher["ftptype"] if "ftptype" in ftppublisher else None
        
        eventfolder=os.path.dirname(os.path.dirname(outdir))
        eventpubfolder=eventfolder.replace(self.datapath, self.env.publishfolder)
        outpubdir=outdir.replace(self.datapath, self.env.publishfolder)
        
        outdir_array=self.splitallpath(outdir)
        eventftpfolder=outdir_array[-3]
        outftpfolder=os.path.join(outdir_array[-3],outdir_array[-2],outdir_array[-1])
        
        if not os.path.exists(outpubdir) and copyfiles:
            os.makedirs(outpubdir)
            
        if ftpfiles:
            # connect to host, default port
            try:
                ftp = self.ftp_login(ftppublisher)
                #ftp = FTP(ftpdomain)     
                #ftp.login(ftppublisher["user"],ftppublisher["pass"])
            except:
                errmess="FTP connection to server %s failed:\n"%ftpdomain+traceback.format_exc()
                self.logmess(errmess)  
                raise Exception(errmess)
                return

        for fname in self.filesdict:
            if os.path.isfile(os.path.join(outdir,self.filesdict[fname])):
                if copyfiles and not os.path.exists(os.path.join(outpubdir,self.filesdict[fname])):
                    try:
                        shutil.copyfile(os.path.join(outdir,self.filesdict[fname]), os.path.join(outpubdir,self.filesdict[fname]))
                    except:
                        errmess="File copy of %s to %s failed:\n"%(os.path.join(outdir,self.filesdict[fname]), os.path.join(outpubdir,self.filesdict[fname]))+traceback.format_exc()
                        self.warning+='WARNING! '+errmess+'\n'
                        self.logmess(errmess)  

                if skiplargeftp and os.path.getsize(os.path.join(outdir,self.filesdict[fname]))>10000000:
                    continue
                if ftpfiles:
                    try:
                        self.ftp_cwd(ftpfolder,ftp,ftppublisher_type)
                        for folder in self.splitallpath(outftpfolder):
                            self.ftp_chdir(folder,ftp,ftppublisher_type)
                        #ftp.storbinary('STOR '+self.filesdict[fname], open(os.path.join(outdir,self.filesdict[fname]), 'rb'))
                        if not self.overwrite and self.ftp_isfile(ftp,self.filesdict[fname],ftppublisher_type):
                            continue
                        self.ftp_put(ftp, self.filesdict[fname], os.path.join(outdir,self.filesdict[fname]), ftppublisher_type)
                    except:
                        errmess="File transfer of %s to %s failed:\n"%(self.filesdict[fname],os.path.join(ftpfolder,outftpfolder))+traceback.format_exc()
                        self.warning+='WARNING! '+errmess+'\n'
                        self.logmess(errmess)  
                        #raise Exception(errmess)
                        #return
            else:
                if copyfiles or ftpfiles:
                    errmess="File %s not found in %s"%(self.filesdict[fname],outdir)
                    self.logmess(errmess)
                    #raise Exception(errmess)
                    #return
        
        for fjson in fileutils().find_files(self.env.processed_trigger, '%s*%s*'%(self.env.eventfileprefix,os.path.basename(eventfolder)), "list"):
            if fjson[-4:].lower()=='json':
                with open(fjson) as f:
                    self.eventdict=json.load(f)
            if copyfiles and not os.path.exists(os.path.join(eventpubfolder,os.path.basename(fjson))):
                try:
                    shutil.copyfile(os.path.join(eventfolder,fjson), os.path.join(eventpubfolder,os.path.basename(fjson)))
                except:
                    errmess="File copy of %s to %s failed:\n"%(os.path.join(eventfolder,fjson), os.path.join(eventpubfolder,os.path.basename(fjson)))+traceback.format_exc()
                    self.warning+='WARNING! '+errmess+'\n'
                    self.logmess(errmess)  
            if ftpfiles:
                try:
                    self.ftp_cwd(ftpfolder,ftp,ftppublisher_type)
                    self.ftp_chdir(eventftpfolder,ftp,ftppublisher_type)
                    #ftp.storbinary('STOR '+os.path.basename(fjson), open(os.path.join(eventpubfolder,os.path.basename(fjson)), 'rb'))
                    self.ftp_put(ftp, os.path.basename(fjson), os.path.join(eventpubfolder,os.path.basename(fjson)), ftppublisher_type)
                except:
                    errmess="File transfer of %s to %s failed:\n"%(os.path.basename(fjson),os.path.join(ftpfolder,eventftpfolder))+traceback.format_exc()
                    self.warning+='WARNING! '+errmess+'\n'
                    self.logmess(errmess)  
                    #raise Exception(errmess)
                    #return
        if ftpfiles:
            self.ftp_quit(ftp, ftppublisher_type)
            
        if webdb:
            self.publishtowebdb(outdir, ftppublisher)
        
    def publish(self, outdir):
        '''
        Copy files for publishing
        '''
        for ftppublisher in self.env.ftppublishers:
            self.transfer_files(outdir, ftppublisher)
        
        if self.sendnotif:
            self.notif_message(outdir)
            
    def unpublish(self, outdir):
        '''
        Remove files for publishing
        '''
        
        
        for ftppublisher in self.env.ftppublishers:
            ftp_files = eval(ftppublisher["ftpfiles"])

            outpubdir=outdir.replace(self.datapath, self.env.publishfolder)
            if os.path.exists(outpubdir):
                shutil.rmtree(outpubdir)
            
            if ftp_files:    
                outdir_array=self.splitallpath(outdir)
                eventftpfolder=outdir_array[-3]
                outfolder=outdir_array[-2]
    
                try:
                    ftp = self.ftp_login(ftppublisher)
                    self.ftp_chdir(ftppublisher["ftpfolder"],ftp)
                    self.ftp_chdir(eventftpfolder,ftp)
                    self.ftp_rmTree(outfolder, ftp)
                except:
                    errmess="FTP connection to server %s failed:\n"%self.env.ftpdomain+traceback.format_exc()
                    self.logmess(errmess)  
                    raise Exception(errmess)
                    return
        
    def publish_output(self, outdir, pubstat):
        '''
        Publish or unpublish
        '''
        
        if pubstat.upper()=='YES':
            self.logmess('Output will be published',logtype='info')
            self.create_lowres(outdir)
            self.publish(outdir)
        elif pubstat.upper()=='NO' :
            self.logmess('Output will be unpublished',logtype='info')
            self.unpublish(outdir)
            
    def create_lowres(self, outdir):
        '''
        Create low resolution and thumbnail image
        '''
        
        if 'highres_ifg' not in self.filesdict:
            return
        input_tif=os.path.join(outdir, self.filesdict['highres_ifg'])
        if not os.path.isfile(input_tif):
            errmess="File %s not found in %s"%(self.filesdict['highres_ifg'],outdir)
            self.logmess(errmess)
            raise Exception(errmess)
            return
        lowres_ifg = os.path.join(outdir, self.filesdict['lowres_ifg'])
        thumb_ifg = os.path.join(outdir, self.filesdict['thumbnail'])
        scale=12
        #if not os.path.isfile(lowres_ifg):
        if True:    
            downsample_tif=os.path.join(outdir, self.filesdict['highres_ifg'].split('.')[0]+"_%d."%scale+self.filesdict['highres_ifg'].split('.')[1])
            geomtools.downsample_tiff(input_tif, downsample_tif, scale=scale )
            geomtools.convert_tiff(downsample_tif, lowres_ifg, 'png')
            geomtools.create_thumbnail(lowres_ifg, thumb_ifg, scale=10)
            geomtools.makeblacktransparent(lowres_ifg, lowres_ifg)
        

    def logmess(self,mess,messtype = 1, logtype = 'error'):
        if self.pstatus:
            self.pstatus[messtype].put(mess)
        if self.log and messtype==1:
            if logtype=='error':
                self.log.error(mess)
            elif logtype=='info':
                self.log.info(mess)  
                
