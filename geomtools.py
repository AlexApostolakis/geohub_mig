'''

Copyright (C) Alex Apostolakis - All Rights Reserved
Unauthorized copying of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Alex Apostolakis a.apostolakis@yahoo.gr, alex.apostolakis@technoesis.gr,  May 2017


@author: Alex Apostolakis 
'''

from osgeo import gdal, ogr, osr, gdalnumeric
import numpy as np
from PIL import Image
import os

class geomtools(object):
    '''
    Geometry tools based on osgeo ogr,osr libraries 
    '''

    @staticmethod
    def convert_geom(WKT, inputEPSG, outputEPSG):
        '''
        Convert coordinate system
        '''
        
        # create a geometry from coordinates
        geom = ogr.CreateGeometryFromWkt(WKT)
        
        # create coordinate transformation
        inSpatialRef = osr.SpatialReference()
        inSpatialRef.ImportFromEPSG(inputEPSG)
        
        outSpatialRef = osr.SpatialReference()
        outSpatialRef.ImportFromEPSG(outputEPSG)
        
        coordTransform = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)
    
        # transform point
        geom.Transform(coordTransform)
        WKTexp=geom.ExportToWkt()
        
        return WKTexp, geom
    
    @staticmethod
    def create_polygon(coords):  
        '''
        Create polygon from coordinates list
        '''
        
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for coord in coords:
            ring.AddPoint(coord[0], coord[1])
    
        # Create polygon
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        return poly.ExportToWkt(), poly

    @staticmethod
    def rectangle_coords(p1,p2):
        '''
        Create rectangle coordinates list from two diagonal corners points
        '''

        x1=p1[0]; y1=p1[1]; x2=p2[0]; y2=p2[1]
        if x1>x2 :
            xtmp=x1
            x1=x2
            x2=xtmp
        if y1<y2 :
            ytmp=y1
            y1=y2
            y2=ytmp
        return ((x1,y1), (x2,y1), (x2,y2), (x1,y2), (x1,y1))
    
    @staticmethod
    def getGreecePoly():
        
        '''
        Polygon containing Greece Cyprus and part of Asia Minor
        '''

        GreecePolyWkt="POLYGON ((18.65283066373327259 39.65794599054790126, 21.34561562573208349 41.69981804171136019, "+\
                   "26.70092953892072174 42.77500108955357661, 30.05934673871698948 41.3600703465938011, "+\
                   "30.1501147711439188 40.37625559650057028, 28.12296204694256474 40.09909736492252819, "+\
                    "27.24553773348227637 39.49470175000891459, 27.91116997127974031 37.69770159832712153, "+\
                    "29.54499455496441129 35.83154069094151595, 31.84445137644653556 35.80700709068257481, "+\
                    "35.23312458705177619 35.97858297528981097, 33.4480199493222301 33.769664511442258, "+\
                    "22.76764813375392649 33.92043862623369677, 19.37897492314868586 36.85507873203386708, "+\
                    "18.65283066373327259 39.65794599054790126))"

        geompoly = ogr.CreateGeometryFromWkt(GreecePolyWkt)
        
        '''
        f = ogr.Open("greece.shp")
        shape = f.GetLayer(0)
        #first feature of the shapefile
        feature = shape.GetNextFeature()
        geompoly=feature.GetGeometryRef()

        '''

        return geompoly

    @staticmethod
    def pointGeom(point):
        '''
        Return point geometry from point coordinates
        '''

        spatialReference = osr.SpatialReference()
        spatialReference.SetWellKnownGeogCS("WGS84")

        # Create point
        pt = ogr.Geometry(ogr.wkbPoint)
        pt.AssignSpatialReference(spatialReference)
        pt.SetPoint(0, point[0], point[1])
        return pt

    @staticmethod
    def point_in_polygon(pt, poly):
        '''
        Check if point is within a polygon
        '''
        return pt.Within(poly)

    @staticmethod
    def point_in_greecepoly(pt):
        '''
        Check if point is within Greece polygon
        '''

        g_pt=geomtools.pointGeom(pt)
        g_poly=geomtools.getGreecePoly()
        return geomtools.point_in_polygon(g_pt,g_poly)
    

    @staticmethod
    def downsample_output ( g, fname_out, hires_data, scale, ct=None ):
        '''
        This function downsamples, using the **mode**, the 2D array
        `hires_data`. The datatype is assumed byte in this case, and
        you might want to change that. The output files are given by
        `fname_out`. The initial GDAL dataset is `g` (this is where the data are coming
        from, and we use that to fish out the resolution, geotransform, etc.).
        '''

        # Create an in-memory GDAL dataset to store the full resolution
        total_obs = g.RasterCount
        drv = gdal.GetDriverByName( "MEM" )
        dst_ds = drv.Create("", g.RasterXSize, g.RasterYSize, 1, \
            gdal.GDT_Byte )
        dst_ds.SetGeoTransform( g.GetGeoTransform())
        dst_ds.SetProjection ( g.GetProjectionRef() )
        dst_ds.GetRasterBand(1).WriteArray ( hires_data )
        
        geoT = g.GetGeoTransform()
        drv = gdal.GetDriverByName( "GTiff" )
        resampled = drv.Create( fname_out, g.RasterXSize/scale, g.RasterYSize/scale, 1, gdal.GDT_Byte )
    
        if ct:
            resampled.GetRasterBand(1).SetColorTable(ct)
        
        this_geoT = ( geoT[0], geoT[1]*scale, geoT[2], geoT[3], \
                geoT[4], geoT[5]*scale )
        resampled.SetGeoTransform( this_geoT )
        resampled.SetProjection ( g.GetProjectionRef() )
        resampled.SetMetadata ({"TotalNObs":"%d" % total_obs})
        
        gdal.RegenerateOverviews ( dst_ds.GetRasterBand(1), \
            [resampled.GetRasterBand(1)], 'mode' )
        
        resampled.GetRasterBand(1).SetNoDataValue ( 0 )
        resampled = None

    @staticmethod
    def downsample_tiff ( fname_in, fname_out, scale ):
        '''
        call downsample_output with simpler arguments
        '''
        inpimg=gdal.Open(fname_in)
        band=inpimg.GetRasterBand(1)
        band_array=band.ReadAsArray().astype(np.uint8)
        ct=band.GetColorTable()
        geomtools.downsample_output(inpimg,fname_out,band_array,scale,ct)
    
    @staticmethod
    def convert_tiff(tiffname, outname, imgtype, quality = 100):
        '''
        convert single band tiff with color table to jpeg or png
        '''
   
        inpimg=gdal.Open(tiffname)
        band=inpimg.GetRasterBand(1)
        band_array=band.ReadAsArray().astype(np.uint8)
        ct=band.GetColorTable()
        newimage = Image.new("RGB", band_array.shape[::-1])
        rgbArray= np.asarray(newimage,dtype=np.uint8).copy()
        jpgArray= np.asarray(newimage,dtype=np.uint16).copy()
        
        for i in range(ct.GetCount()):
            sEntry = ct.GetColorEntry(i)
            rgbArray[..., 0][band_array==i]=sEntry[0]
            rgbArray[..., 1][band_array==i]=sEntry[1]
            rgbArray[..., 2][band_array==i]=sEntry[2]
            #print "%3d: %d,%d,%d" % (i,sEntry[0],sEntry[1],sEntry[2])
    
        img = Image.fromarray(rgbArray,'RGB')
        img.save(outname,imgtype, quality=quality)
        
    @staticmethod
    def makeblacktransparent(inname, outname):
        '''
        add alpha channel and make black background
        '''
        img = Image.open(inname)
        img = img.convert("RGBA")
        datas = img.getdata()
        
        newData = []
        for item in datas:
            if item[0] == 0 and item[1] == 0 and item[2] == 0:
                newData.append((0, 0, 0, 0))
            else:
                newData.append(item)
        
        img.putdata(newData)
        img.save(outname, "PNG")


    @staticmethod
    def create_thumbnail (pngname, outname, scale):
        '''
        create thumbnail from png
        '''
       
        im = Image.open(pngname)
        w, h = im.size
        im.thumbnail((w / scale, h / scale), Image.ANTIALIAS)
        im.save(outname)
    
    @staticmethod    
    def point_inland_check(point):
        lpolyfile = ogr.Open(os.path.join("ne_10m_land","ne_10m_land.shp"))
        shape = lpolyfile.GetLayer(0)
        distances = []
        for feature in shape:
            g=feature.GetGeometryRef()
            if point.Within(g):
                return point.Within(g), point.Distance(g)
            #print point.Distance(g)
            distances.append(point.Distance(g))
        return False,min(distances)
