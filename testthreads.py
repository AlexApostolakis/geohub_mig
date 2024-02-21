'''
Created on 24 2017

@author: alex
'''

from threading import Thread
from time import sleep

def function01(arg,name):
    for i in range(arg):
        print '%s i---->%d'%(name,i)
        #print name,"arg---->",arg,'\n')
        sleep(1)


def test01():
    threads=[]
    threadcount=5
    i=0
    '''
    l1=[4,5,6]
    
    print l1
    print len(l1)
    print range( len(l1))
    print l1[1]
    del l1[0]
    print l1
    print len(l1)
    print range( len(l1))
    print l1[1]
    print l1[0]
    '''
    while i<threadcount:
        thname='thread'+str(i)
        threads.append(Thread(target = function01, args = ((i+1)*4,thname,)))
        threads[-1].setName(thname)
        threads[-1].start()
        i=1+i
        
    while len(threads)>0:
        l=len(threads)
        i=0
        while i < l:
            if not threads[i].isAlive():
                tname=threads[i].getName()
                del threads[i]
                print "********** thread %s finished *********.Remaning %d"%(tname,len(threads))
            else:
                i=i+1
            l=len(threads)
        
    #threads[-1].join()
    print ("thread finished...exiting")
    



test01()
