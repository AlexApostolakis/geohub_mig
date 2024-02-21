'''
Created on 28 Feb 2018

@author: alex
'''

from geomtools import geomtools
import ogr
from datetime import datetime, timedelta

class m:
    K=1
    
    def a(self):
        print m.K

def strptime_m(datetime_string,format_string):
    '''
    Parse time with milliseconds or not 
    '''
    dtlist = datetime_string.strip().split(".")
    dt_no_ms=dtlist[0]
    mSecs=dtlist[1] if len(dtlist)>1 else None
   
    dt = datetime.strptime(dt_no_ms[:19], format_string)
    fullDateTime = dt + timedelta(milliseconds = int(mSecs)) if mSecs else dt 
    return fullDateTime

folder=r"Z:\data\alexis\geohub_prod_backup\events\Mexico_Mw7.2_20180216233959\20180205003836_20180130003913_5_ASCENDING"
geomtools.downsample_tiff(folder+"/ifg/file_result_Interf_fint_geo_ql.tif", \
                          folder+"/lowresolution.tif", scale=12 )
geomtools.convert_tiff(folder+"/lowResolution.tif",\
                       folder+"/lowResolution.png", 'png')

