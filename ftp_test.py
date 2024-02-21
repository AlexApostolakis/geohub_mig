'''
Created on 24 Mar 2019

@author: alex
'''

import os
from ftplib import FTP

# Check if directory exists (in current location)
def ftp_directory_exists(folder):
    filelist = []
    ftp.retrlines('LIST',filelist.append)
    for f in filelist:
        if f.split()[-1] == folder and f.upper().startswith('D'):
            return True
    return False

def ftp_chdir(folder): 
    if ftp_directory_exists(folder) is False: # (or negate, whatever you prefer for readability)
        ftp.mkd(folder)
    ftp.cwd(folder)

def splitallpath(path):
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

        
ftp = FTP('ftp.technoesis.gr')     # connect to host, default port
ftp.login('aapostol290065','TqTuGuc6Xak0')                     # user anonymous, passwd anonymous@
#ftp.cwd('debian')               # change into "debian" directory
#ftp.retrlines('LIST')           # list directory contents
#ftp.retrbinary('RETR README', open('README', 'wb').write)

print ftp.pwd()
ftp_chdir('private')

#for folder in splitallpath('test2ftp/t1'):
#    ftp_chdir(folder)

#folder=r"C:\GeoHub\auxiliary\orbits\S1A\2017\7"+"\\"
#fname="S1A_OPER_AUX_RESORB_OPOD_20170703T090353_V20170703T040049_20170703T071819.EOF"
#ftp.storbinary('STOR '+fname, open(folder+fname, 'rb'))

ftp.quit()
