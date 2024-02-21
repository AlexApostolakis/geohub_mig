'''
Created on 27 May 2017

@author: alex
'''

import os, sys
import requests
import hubsearchparser
import traceback
from _functools import partial
import hashlib
import structures
import xml.etree.ElementTree as ET
from osgeo import gdal, ogr, osr
import geomtools
import numpy as np
import json
from io import StringIO
import searchimages
import re



#hostcolhub="https://colhub.copernicus.eu/dhus/"
hostcolhub="https://scihub.copernicus.eu/dhus/"
authcolhub1='aapostolakis'
authcolhub2='Al3xd1ploma'

#footprint='POLYGON((22.787591050041993 37.91507553735805,22.787821720017277 37.91518980423113,22.7879880169762 37.91532946350162,22.78827233113178 37.91572727936423,22.788610289467655 37.915549532117026,22.78868539132007 37.91546489041977,22.788717577828248 37.91538024862513,22.788610289467655 37.91505014469544,22.788637111557804 37.91495280607441,22.788717577828248 37.91489778853598,22.788792679680668 37.914851235202036,22.788857052697026 37.91478775333563,22.788851688278996 37.91472427141443,22.788562009705384 37.91428412858731,22.78812749184497 37.91458461099491,22.78775198258289 37.914880860054325,22.787591050041993 37.91507553735805))'
#polywkt='POLYGON((25.93186443529783 38.28644438796505,25.932872945887432 38.288280210327144,25.9351903744763 38.287000192296716,25.936306173426495 38.285585409263035,25.93587701998411 38.28342949637624,25.932679826838356 38.28329474969482,25.93186443529783 38.28644438796505))'

#roi_id 53 server
aoi='POLYGON((22.78718032393538 37.914056715965756,22.788027901984087 37.9146576814114,22.788532157278887 37.91427678838883,22.78829612288558 37.91367581983148,22.78800644431197 37.91376469577256,22.787786503172747 37.91356578280332,22.787539739943377 37.913768927957534,22.78718032393538 37.914056715965756))'

#startdate='NOW-30DAYS'
#enddate='NOW'
startdate="2017-03-26T00:00:00.000Z"
enddate="2017-03-28T00:00:00.000Z"

query='beginposition:[%s TO %s] AND ( footprint:"Intersects(%s)" ) AND platformname:Sentinel-2'%(startdate,enddate,aoi)


sess1=requests.session()
sess1.auth=(authcolhub1 , authcolhub2)
#response = sess1.get(hostcolhub+ 'search', params={'q': query, 'start': 0, 'rows': 100})
#response = sess1.get("https://scihub.copernicus.eu/dhus/odata/v1/Products('998c58d1-2fe6-4ca1-87c6-5947c50afb4d')/Nodes('S2A_MSIL2A_20170705T090551_N0205_R050_T34SFH_20170705T090814.SAFE')/Nodes")
#response = sess1.get(hostcolhub+ "odata/v1/Products('010fc842-077f-4791-bd46-e8aa56ba46f0')/Nodes('S2A_MSIL1C_20170516T091031_N0205_R050_T34SFG_20170516T091829.SAFE')/Nodes('GRANULE')/Nodes('L1C_T34SFG_A009914_20170516T091829')/Nodes('IMG_DATA')/Nodes('T34SFG_20170516T091031_B02.jp2')/Attributes('size')")

#sess1.get(p_uri + "Products('Quicklook')/$value",  hooks=dict(response=partial(_product.store, dest, self.env._catalog, pbar)), stream=True)

#response = sess1.get(hostcolhub+ "odata/v1/Products('b19f28d5-2669-4e2d-9d2a-c47f5eb6df5e')/Nodes('S2A_OPER_PRD_MSIL1C_PDMC_20160717T202905_R007_V20160717T090142_20160717T090142.SAFE')/Nodes('GRANULE')/Nodes('S2A_OPER_MSI_L1C_TL_MPS__20160717T125454_A005581_T35SLD_N02.04')/Nodes('IMG_DATA')/Nodes('S2A_OPER_MSI_L1C_TL_MPS__20160717T125454_A005581_T35SLD_B02.jp2')/Attributes")
#response = sess1.get(hostcolhub+ "odata/v1/Products('b19f28d5-2669-4e2d-9d2a-c47f5eb6df5e')/Nodes('S2A_OPER_PRD_MSIL1C_PDMC_20160717T202905_R007_V20160717T090142_20160717T090142.SAFE')/Nodes('GRANULE')/Nodes")

#response = sess1.get("https://qc.sentinel1.eo.esa.int/aux_poeorb/",verify=False)

#response = sess1.get("https://qc.sentinel1.eo.esa.int/aux_poeorb/S1B_OPER_AUX_POEORB_OPOD_20170821T111434_V20170731T225942_20170802T005942.EOF",verify=False)


#gt=geomtools.Geomtools()
#polynew=gt.convert_geom(polywkt,4326, 32635)
#tilelist,resp=sd.get_granule_tiles('b19f28d5-2669-4e2d-9d2a-c47f5eb6df5e','S2A_OPER_PRD_MSIL1C_PDMC_20160717T202905_R007_V20160717T090142_20160717T090142.SAFE')
'''
fa6383b8-03ed-4455-8ee5-c719e233f314

9ead6404-184d-4160-9f2a-51d8eefb81b4
response = sess1.get(hostcolhub+ "odata/v1/Products('b19f28d5-2669-4e2d-9d2a-c47f5eb6df5e')/Nodes('S2A_OPER_PRD_MSIL1C_PDMC_20160717T202905_R007_V20160717T090142_20160717T090142.SAFE')/Nodes('GRANULE')/"+ \
                     "Nodes('S2A_OPER_MSI_L1C_TL_MPS__20160717T125454_A005581_T35SLC_N02.04')/Nodes('QI_DATA')/"+ \
                     "Nodes('S2A_OPER_MSK_CLOUDS_MPS__20160717T125454_A005581_T35SLC_B00_MSIL1C.gml')/$value")
print response.content
sd.check_clouds(polywkt, response)


print response.content

response = sess1.get("https://scihub.copernicus.eu/dhus/odata/v1/Products('713bd67e-4936-48aa-8cd3-ae7167c48e73')/Nodes('S2A_MSIL2A_20170526T090601_N0205_R050_T35SLC_20170526T090726.SAFE')/Nodes('GRANULE')/Nodes('L2A_T35SLC_A010057_20170526T090726')/Nodes('MTD_TL.xml')/$value")
response = sess1.get("https://scihub.copernicus.eu/dhus/odata/v1/Products('998c58d1-2fe6-4ca1-87c6-5947c50afb4d')/Nodes('S2A_MSIL2A_20170705T090551_N0205_R050_T34SFH_20170705T090814.SAFE')/Nodes('GRANULE')/Nodes('L2A_T34SFH_A010629_20170705T090814')/Nodes")
response = sess1.get("https://scihub.copernicus.eu/dhus/odata/v1/Products('6b072ed3-2224-43fa-a1f3-b51d2f685a14')/Nodes('S2A_OPER_PRD_MSIL1C_PDMC_20160727T151307_R007_V20160727T090829_20160727T090829.SAFE')/Nodes('GRANULE')/Nodes('S2A_OPER_MSI_L1C_TL_MPS__20160727T125058_A005724_T35SLC_N02.04')/Nodes('S2A_OPER_MTD_L1C_TL_MPS__20160727T125058_A005724_T35SLC.xml')/$value")

xml_file = open("Output3.xml", "w")
xml_file.write(response.content)
xml_file.close()
'''
#response = sess1.get("https://qc.sentinel1.eo.esa.int/aux_poeorb/S1B_OPER_AUX_POEORB_OPOD_20170821T111434_V20170731T225942_20170802T005942.EOF",verify=False)
'''
response = sess1.get("https://qc.sentinel1.eo.esa.int/aux_resorb/?mission=S1A&validity_start_time=2017-10-01",verify=False)
xml_file = open("orbitfiles.xml", "w")
xml_file.write(response.content)
xml_file.close()
'''
'''
response = sess1.get("https://scihub.copernicus.eu/dhus/odata/v1/Products('713bd67e-4936-48aa-8cd3-ae7167c48e73')/Products('Quicklook')/$value",headers = {'Range': 'bytes=20000-'})
xml_file = open("ql.jpg", "wb")
xml_file.write(response.content)
xml_file.close()
print response.content
'''
print re.match('.*ZIP',"sgsdg.ZIP")






