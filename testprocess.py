'''
Created on 24 Sep 2017

@author: alex
'''

import sys
from environment import Environment
from autoifgsrv import deleteutils
from serviceprocess import step_process
from time import sleep



def main(argv):

    env=Environment()
    sp=step_process(env, 1789,91)
    sleep(3)
    pars=r"D:\data\geohub\sentinel-1\2022\2\20220224230513_164_DESCENDING *_slc walk slave"
    sp.init_pyprocess(deleteutils, pars.split())
    sleep(3)
    
    while sp.is_alive():
        print sp.get_status()
        print sp.get_message()
        print sp.get_progress()
        sleep(3)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
