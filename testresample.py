'''
Created on 25 April 2018

@author: alex
'''

from osgeo import gdal, gdalnumeric
import numpy as np
import subprocess
from PIL import Image
from geomtools import geomtools

def downsample_output ( g, fname_out, hires_data, scale, ct=None ):
    """This function downsamples, using the **mode**, the 2D array
    `hires_data`. The datatype is assumed byte in this case, and
    you might want to change that. The output files are given by
    `fname_out`, and we downsample by a factor of 100 and 300. The
    initial GDAL dataset is `g` (this is where the data are coming
    from, and we use that to fish out the resolution, geotransform,
    etc.).
    
    NOTE that this is fairly specialised a function, and you might
    want to have more flexiblity by adding options to deal with
    the aggregation procedure in `gdal.RegenerateOverviews`, the
    resolutions of the aggregations you want, the datatypes, etc.
    """
    # Create an in-memory GDAL dataset to store the full resolution
    # dataset...
    total_obs = g.RasterCount
    drv = gdal.GetDriverByName( "MEM" )
    dst_ds = drv.Create("", g.RasterXSize, g.RasterYSize, 1, \
        gdal.GDT_Byte )
    dst_ds.SetGeoTransform( g.GetGeoTransform())
    dst_ds.SetProjection ( g.GetProjectionRef() )
    dst_ds.GetRasterBand(1).WriteArray ( hires_data )
    
    geoT = g.GetGeoTransform()
    drv = gdal.GetDriverByName( "GTiff" )
    '''
    resampled = drv.Create( "%s_resample_%d.tif" % (fname_out,scale), \
        g.RasterXSize/scale, g.RasterYSize/scale, 1, gdal.GDT_Byte )
    '''
    resampled = drv.Create( fname_out, g.RasterXSize/scale, g.RasterYSize/scale, 1, gdal.GDT_Byte )

    if ct:
        resampled.GetRasterBand(1).SetColorTable(ct)
        
    saveOptions = []
    saveOptions.append("QUALITY=75")
    

    # Obtains a JPEG GDAL driver
    #jpegDriver = gdal.GetDriverByName("JPEG")
 
 
    
    this_geoT = ( geoT[0], geoT[1]*scale, geoT[2], geoT[3], \
            geoT[4], geoT[5]*scale )
    resampled.SetGeoTransform( this_geoT )
    resampled.SetProjection ( g.GetProjectionRef() )
    resampled.SetMetadata ({"TotalNObs":"%d" % total_obs})

    
    gdal.RegenerateOverviews ( dst_ds.GetRasterBand(1), \
        [resampled.GetRasterBand(1)], 'mode' )
    
    resampled.GetRasterBand(1).SetNoDataValue ( 0 )
    resampled = None


def downsample_tiff ( fname_in, fname_out, scale ):
    inpimg=gdal.Open(fname_in)
    band=inpimg.GetRasterBand(1)
    band_array=band.ReadAsArray().astype(np.uint8)
    ct=band.GetColorTable()
    downsample_output(inpimg,fname_out,band_array,scale,ct)
    
def convert_tiff (tiffname, outname, imgtype, quality = 100):

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

def create_thumbnail (pngname, outname, scale):
   
    im = Image.open(pngname)
    w, h = im.size
    im.thumbnail((w / scale, h / scale), Image.ANTIALIAS)
    im.save(outname)
    
def check_trans(img):
    if pic.shape[2] == 3:
        print("No alpha channel!")
    if pic.shape[2] == 4:
        print("There's an alpha channel!")    
    
import matplotlib.pyplot as plt
from PIL import Image
import os
import sys

img="C:\\GeoHub\\publish\\co_20180926230142_20181008230142_4_ASCENDING\\ifg\\lowResolution"
img1=img+'.png'
img2=img+'_trans.png'

if os.path.isfile(img1):
    pic = plt.imread(img1)
    check_trans(pic)

if os.path.isfile(img2):
    pic = plt.imread(img2)
    check_trans(pic)

    
if not os.path.isfile(img1):
    sys.exit()
    
img = Image.open(img1)
img = img.convert("RGBA")
datas = img.getdata()

newData = []
for item in datas:
    if item[0] == 0 and item[1] == 0 and item[2] == 0:
        newData.append((0, 0, 0, 0))
    else:
        newData.append(item)

img.putdata(newData)
img.save(img2, "PNG")

'''
inpimg=gdal.Open("C:/GeoHub/events/file_result_Interf_fint_geo_ql.tif")
band=inpimg.GetRasterBand(1)
band_array=band.ReadAsArray().astype(np.uint8)

ct=band.GetColorTable()
downsample_output(inpimg,"C:/GeoHub/events/file_result_Interf_fint_geo",band_array,20,ct)


inpimg=gdal.Open("C:/GeoHub/events/file_result_Interf_fint_geo_resample_10.tif")
band=inpimg.GetRasterBand(1)
band_array=band.ReadAsArray().astype(np.uint8)

ct=band.GetColorTable()

#ct=inpimg.GetRasterBand(1).GetRasterColorTable()

r=np.copy(band_array)
g=np.copy(band_array)
b=np.copy(band_array)

#rgbArray=np.zeros((band_array.shape[0],band_array.shape[1],3), dtype=np.uint8)

# Create new Image and a Pixel Map

newimage = Image.new("RGB", band_array.shape[::-1])
rgbArray= np.asarray(newimage,dtype=np.uint8).copy()
jpgArray= np.asarray(newimage,dtype=np.uint16).copy()

for i in range(ct.GetCount()):
    sEntry = ct.GetColorEntry(i)
    rgbArray[..., 0][band_array==i]=sEntry[0]
    rgbArray[..., 1][band_array==i]=sEntry[1]
    rgbArray[..., 2][band_array==i]=sEntry[2]
    print "%3d: %d,%d,%d" % (i,sEntry[0],sEntry[1],sEntry[2])
    
jpgArray=rgbArray


#saveOptions = []
#saveOptions.append("QUALITY=75")

# Obtains a JPEG GDAL driver
#jpegDriver = gdal.GetDriverByName("JPEG")   

# Create the .JPG file
#jpegDriver.CreateCopy("C:/GeoHub/events/file_result_Interf_fint_geo_ql.jpg", inpimg, 0, saveOptions)  

#comm='C:/OSGeo4W64/bin/gdal_translate -of JPEG -expand rgb -scale -co worldfile=yes C:/GeoHub/events/file_result_Interf_fint_geo_ql.tif C:/GeoHub/events/file_result_Interf_fint_geo_ql.jpg'
#subprocess.call(comm, shell=True)

img = Image.fromarray(rgbArray,'RGB')
imgjpg = Image.fromarray(jpgArray,'RGB')

imgjpg.save('C:/GeoHub/events/file_result_Interf_fint_geo_ql_10.jpg','JPEG',quality=75)
img.save('C:/GeoHub/events/file_result_Interf_fint_geo_ql_10.png','png')
inpimg=gdal.Open("C:/GeoHub/events/file_result_Interf_fint_geo_ql.tif")

scale = 5
outtiff='C:/GeoHub/events/lowres_%d.tif'%scale
geomtools.downsample_tiff("C:/GeoHub/events/file_result_Interf_fint_geo_ql.tif", outtiff, scale )
q1=100; q2=50
itype='png'
geomtools.convert_tiff(outtiff, 'C:/GeoHub/events/lowres_%d_%d.%s'%(scale,q1,itype), itype)
geomtools.convert_tiff(outtiff, 'C:/GeoHub/events/lowres_%d_%d.%s'%(scale,q2,itype), itype)

scalethumb = 10
geomtools.create_thumbnail ('C:/GeoHub/events/lowres_%d_%d.%s'%(scale,q1,itype), 'C:/GeoHub/events/thumb_%d_%d.%s'%(scale,scalethumb,itype), scalethumb)
'''


