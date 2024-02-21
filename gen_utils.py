'''
Created on 25 June 2018

@author: alex
'''

class gentools(object):
    '''
    Methods for General utilities
    '''

    @staticmethod
    def hash_bytestr_iter(bytesiter, hasher, ashexstr=False):
        '''
        calculates MD5 checksum
        '''
        for block in bytesiter:
            hasher.update(block)
        return (hasher.hexdigest().upper() if ashexstr else hasher.digest())

    @staticmethod
    def file_as_blockiter(afile, blocksize=65536):
        '''
        Iterates through a file with a certain 'blocksize'
        '''

        with afile:
            block = afile.read(blocksize)
            while len(block) > 0:
                yield block
                block = afile.read(blocksize)