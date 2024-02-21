'''
Created on 28 Feb 2018

@author: alex
'''

import mysql.connector
import xml.etree.ElementTree as ET 
from io import StringIO
from unicodedata import east_asian_width
import os

def mysql_connection():
    mysqlcon = mysql.connector.connect(user='w9165_geohub', password='G00dm0rn!ng',
                              host='db22.papaki.gr',
                              database='w91651dval_geohub')
    return mysqlcon

def get_coords(kml): 
    with open(kml, 'r') as fxml:
        xmlstring = fxml.read()
    xmlstring=xmlstring.replace('\xae','')
    xmlelems = ET.fromstring(xmlstring)
    ns = dict([ node for _, node in ET.iterparse( StringIO(unicode(xmlstring, "utf-8")), events=['start-ns'] )])
    north = float(xmlelems.find(".//{"+ns['']+"}north").text)
    south = float(xmlelems.find(".//{"+ns['']+"}south").text)
    east = float(xmlelems.find(".//{"+ns['']+"}east").text)
    west = float(xmlelems.find(".//{"+ns['']+"}west").text)
    return north, south, east, west

def insert_pub_event(connection, location, mag, depth, evdatetime, lng, lat, link, desc, evid):
    cursor = connection.cursor()
    
    if evid is None:
        sql="Select max(EvID) from Events"
        cursor.execute(sql)
        maxID = cursor.fetchone()[0]
        evid = maxID+1

    '''
    sample query
    INSERT INTO Events (EvID, EvLocation, Magnitude, Depth, EvDateTime, Lng, Lat, Link, Description) VALUES (10, 'Athens', 3.0, 7.4, '20180101151245', 38.016, 23.736, '', '')
    '''
    
    link = '' if not link else link
    desc = '' if not desc else desc    
        
    sql="INSERT INTO Events (EvID, EvLocation, Magnitude, Depth, EvDateTime, Lng, Lat, Link, Description) VALUES (%s, '%s', %.1f, %.1f, '%s', %s, %s, '%s', '%s')"\
    %(evid,location, mag, depth, evdatetime, lng, lat, link, desc)
    cursor.execute(sql)    
    connection.commit()
    cursor.close()
    return evid

def update_pub_event(connection, evid, location, mag, depth, evdatetime, lng, lat, link, desc):
    cursor = connection.cursor()

    link = '' if not link else link
    desc = '' if not desc else desc    
    
    sql="UPDATE Events set EvLocation='%s', Magnitude=%.1f, Depth=%.1f, EvDateTime='%s', Lng=%s, Lat=%s, Link='%s', Description='%s' where EvID=%d"\
    %(location, mag, depth, evdatetime, lng, lat, link, desc,evid)
    
    cursor.execute(sql)    
    connection.commit()
    cursor.close()
    return evid

def getEventID(connection, location=None, datetime=None, evid=None):
    if evid is None:
        sql="Select EvID from Events where EvLocation='%s' and EvDateTime='%s'"%(location, datetime)
    else:
        sql="Select EvID from Events where EvID=%s"%(evid)

    cursor = connection.cursor()
    cursor.execute(sql)
    res = cursor.fetchone()
    if res:
        eid = res[0]
    else:
        eid = None
    cursor.close()
    return eid
    
def getEvent(connection, EventID):
    sql="Select * from Events where EvID=%d"%(EventID)
    cursor = connection.cursor()
    cursor.execute(sql)
    if cursor.rowcount<=0 or cursor.rowcount>1:
        raise ValueError("no events")
        res=None
    else:
        res= cursor.fetchone()
    cursor.close()
    return res

def getGeohubRow(connection, sql):
    cursor = connection.cursor()
    cursor.execute(sql)
    return cursor.fetchone()


def delete_pub_event(connection, evid):
    sql="delete from Events where EvID=%d"%evid
    cursor = connection.cursor()
    cursor.execute(sql)
    connection.commit()
    cursor.close()
    
def delete_ev_pub_output(connection, evid):
    sql="delete from Interferograms where EventID=%d"%evid
    cursor = connection.cursor()
    cursor.execute(sql)
    connection.commit()
    cursor.close()
    
def exist_pub_output(connection,evid, ftppath, localroot, copre, masterdatetime, slavedatetime, orbit, direction, tiff_filepath, lowres_filepath, kml_filepath):
    
    '''
    sample query
    select from Interferograms where Master='20180101121425' and Slave='20180101121425' and Mode='ASCENDING' and orbit='156' and 
    ImgTIF='data/OFFSHOREMAULECHILE_20190929155752/co_20190926100420_20191008100421_156_DESCENDING/ifg/file_result_Interf_fint_geo_ql.png''
    
    
    '''
    ftp_tiff_filepath = os.path.join(ftppath,tiff_filepath).replace('\\','/')
    
    cursor = connection.cursor()
    sql = "select * from Interferograms where Master='%s' and Slave='%s' and orbit='%s' and Mode='%s'  and ImgTIF='%s'"\
    %(masterdatetime, slavedatetime, orbit, direction, ftp_tiff_filepath)
    
    cursor.execute(sql)
    res = cursor.fetchone()
    if res:
        return True
    else:
        return False
    

def insert_pub_output(connection,evid, ftppath, localroot, copre, masterdatetime, slavedatetime, orbit, direction, tiff_filepath, lowres_filepath, kml_filepath):
    '''
    sample query
    "INSERT INTO Interferograms (Type, Master, Slave, Orbit, Mode, ImgTIF, ImgLow, Kml, EventID, North, South, West, East)"+\
    "VALUES ('co-seismic', '20180101121425', '20180101121445', 156, 'ASCENDING', 'data/OFFSHOREMAULECHILE_20190929155752/co_20190926100420_20191008100421_156_DESCENDING/ifg/file_result_Interf_fint_geo_ql.png', 
    'data/OFFSHOREMAULECHILE_20190929155752/co_20190926100420_20191008100421_156_DESCENDING/ifg/lowResolution.png', 
    'data/OFFSHOREMAULECHILE_20190929155752/co_20190926100420_20191008100421_156_DESCENDING/ifg/file_result_Interf_fint_geo_ql.kml', 
    8, -34.97185107, -37.38825441, -70.83616644, -74.32652682)"
    '''
    
    if exist_pub_output(connection,evid, ftppath, localroot, copre, masterdatetime, slavedatetime, orbit, direction, tiff_filepath, lowres_filepath, kml_filepath):
        return

    cursor = connection.cursor()
    north, south, east, west = get_coords(os.path.join(localroot,kml_filepath))
    
    ftp_tiff_filepath = os.path.join(ftppath,tiff_filepath).replace('\\','/')
    ftp_lowres_filepath = os.path.join(ftppath,lowres_filepath).replace('\\','/')
    ftp_kml_filepath = os.path.join(ftppath,kml_filepath).replace('\\','/')
   
    #sql="Select * from Interferograms where Master = %s and Slave = %s"%(masterdatetime, slavedatetime)
    #cursor.execute(sql)
    #res = cursor.fetchone()
    #if res: #do not duplicate ifg entry
    #    cursor.close()
    #    return

    sql="INSERT INTO Interferograms (Type, Master, Slave, Orbit, Mode, ImgTIF, ImgLow, Kml, EventID, North, South, West, East) "+\
    "VALUES ('%s', '%s', '%s', %d, '%s', '%s', '%s', '%s', %d, %s, %s, %s, %s)"\
    %(copre, masterdatetime, slavedatetime, orbit, direction, ftp_tiff_filepath, ftp_lowres_filepath, ftp_kml_filepath, evid, north, south, east, west)

    cursor.execute(sql)    
    connection.commit()
    cursor.close()
    
#print get_coords('file_result_Interf_fint_geo_ql.kml')
#rs=getEvent(mysqlcon, 9)

#evid = insert_pub_event(mysqlcon, 'testlocation', 1.5, 3.5, '20180101151245', 38.016, 23.736, None, None)
#mysqlcon= mysql_connection()
#evid = getEventID(mysqlcon, 'testlocation', '20180101151245')
#insert_pub_output(mysqlcon, evid, '', 'co-seismic', '20180101121425', '20180101121445', 156, 'ASCENDING', 'a_tiff_filepath', 'a_lowres_filepath', 'file_result_Interf_fint_geo_ql.kml')
#delete_ev_pub_output(mysqlcon, evid)
#delete_pub_event(mysqlcon, evid)




