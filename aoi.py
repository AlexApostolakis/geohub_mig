import sys
import warnings
from osgeo import ogr, gdal
from base64 import b64decode
import traceback

gdal.UseExceptions()

class Aoi(object):
    
    def __init__(self, footprint, rep=None):
        # The AOI's footprint.
        self.footprint = None
        
        # If footprint argument is None type, nothing will happen.
        if footprint is None:
            return
        
        # If the footprint argument is of Geometry type then assign it
        # to the footprint variable of the current object, otherwise
        # properly convert it representation according to the rep argument
        # and then assign it to the current object's footprint variable.
        if isinstance(footprint, ogr.Geometry):
            self.footprint = footprint
            
        elif rep is not None:
            
            if rep.upper() == 'GML':
                self.footprint = ogr.CreateGeometryFromGML(footprint)
            elif rep.upper() == 'WKB':
                self.footprint = ogr.CreateGeometryFromWkb(b64decode(footprint))
            elif rep.upper() == 'WKT':
                self.footprint = ogr.CreateGeometryFromWkt(footprint)
    
    
    def intersects(self, footprint, rep=None):

        if footprint is None:
            return False
        
        footprint_geom = None
        if isinstance(footprint, ogr.Geometry):
            footprint_geom = footprint
        
        elif rep is not None:
            
            if rep.upper() == 'GML':
                footprint_geom = ogr.CreateGeometryFromGML(footprint)
            elif rep.upper() == 'WKB':
                footprint_geom = ogr.CreateGeometryFromWkb(b64decode(footprint))
            elif rep.upper() == 'WKT':
                footprint_geom = ogr.CreateGeometryFromWkt(footprint)
        
        
        return self.footprint.Intersects(footprint_geom) if footprint_geom is not None else False
    
    '''   
    def __get_geometry__(self, footprint, rep=None, force=True):
        
        if footprint is None:
            return None
        
        if isinstance(footprint, ogr.Geometry):
            return footprint
        
        if rep is not None and\
            footprint:
            
            if rep.upper() == 'GML':
                return ogr.CreateGeometryFromGML(footprint)
                
            elif rep.upper() == 'WKB':
                return ogr.CreateGeometryFromWkb(b64decode(footprint))
                
            elif rep.upper() == 'WKT':
                return ogr.CreateGeometryFromWkt(footprint)
        
        if force:
            footprint_geom = None
            
            footprint_geom = ogr.CreateGeometryFromGML(footprint)
            if footprint_geom is not None:
                return footprint_geom
            
            footprint_geom = ogr.CreateGeometryFromWkb(b64decode(footprint))
            if footprint_geom is not None:
                return footprint_geom
            
            footprint_geom = ogr.CreateGeometryFromWkt(footprint)
            if footprint_geom is not None:
                return footprint_geom
            
        return None
    '''

'''
def main(argv):

    gml = """<gml:Polygon srsName="http://www.opengis.net/gml/srs/epsg.xml#4326" xmlns:gml="http://www.opengis.net/gml">
               <gml:outerBoundaryIs>
                  <gml:LinearRing>
                     <gml:coordinates>25.955881,35.673836 23.187389,36.072445 23.520250,37.711277 26.350811,37.314232 25.955881,35.673836</gml:coordinates>
                  </gml:LinearRing>
               </gml:outerBoundaryIs>
             </gml:Polygon>"""
    
    wkt = "POLYGON((13.776404104233 34.080804383786,34.870154104233 34.080804383786,34.870154104233 47.332066221651,13.776404104233 47.332066221651,13.776404104233 34.080804383786))"
    
    aoi = Aoi(gml, rep='gml')
    
    print aoi.intersects(wkt, rep='wkt')

    
if __name__ == '__main__':
    sys.exit(main(sys.argv))
'''