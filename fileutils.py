'''
Created on 16 Nov 2017

@author: arcgisadmin
'''
import os
import fnmatch
import environment
import traceback

class fileutils(object):
    
    def find_files(self,directory, pattern, listtype="walk"):
        if listtype=="list":
            for basename in os.listdir(directory):
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(directory, basename)
                    if os.path.isfile(filename):
                        yield filename
        else:
            for root, dirs, files in os.walk(directory):
                for basename in files:
                    if fnmatch.fnmatch(basename, pattern):
                        filename = os.path.join(root, basename)
                        yield filename
                    
    def find_dirs(self,directory, pattern):
        for root, dirs, files in os.walk(directory):
            for basename in dirs:
                if fnmatch.fnmatch(basename, pattern):
                    dirname = os.path.join(root, basename)
                    yield dirname
                    
    def removeEmptyFolders(self, path):
        for root, dirs, files in os.walk(path, topdown=False):
            for name in dirs:
                try:
                    if len(os.listdir( os.path.join(root, name) )) == 0: #check whether the directory is empty
                        #print( "Deleting", os.path.join(root, name) )
                        try:
                            os.rmdir( os.path.join(root, name) )
                        except:
                            #print( "FAILED :", os.path.join(root, name) )
                            pass
                except:
                    pass
