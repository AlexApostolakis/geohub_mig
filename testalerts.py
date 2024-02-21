'''
Created on 15 Sep 2018

@author: arcgisadmin
'''
from environment import Environment
from notifications import alerts
from logs import applog


env=Environment()
alog=applog(env)
syslog=alog.opengenlog()

talerts=alerts(env,syslog)

talerts.alert_on('test', 'test message 1', 'title',replay = 60, logalert = False)

talerts.alert_off('test message 1')


