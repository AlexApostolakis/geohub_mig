import publishing
import multiprocessing as mp
import logging

logger = logging.getLogger(r'testpublish.log')

#need_download, checkmess=self.decide_download(self.p_uri,self.dbprod.dbdata['name'] + '.zip',self.dbprod.dbdata['status'],self.dbprod.mdata['sizebytes'], \
#                                 self.dbprod.mdata['checksum'], self.dbprod)

pd=publishing.Publish('3757', r'Y:\GeoHub_test_run\events\NORTHERNSUMATRAINDONESIA_20220930192841\pre_20220921231248_20220909231249_62_DESCENDING\ifg', 'yes', fileset='ifg', procstatus=[mp.Queue(), mp.Queue(), mp.Queue(), mp.Queue()], env=None, log=logger, archive = False, notify = True, overwrite = True)

