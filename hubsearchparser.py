import re
import sys
import xml.etree.ElementTree as ET
from osgeo import gdal, ogr, osr
from numpy import prod
from copernicus_request_handler import *

def filter_namespaces(root):
    '''
    return xml name spaces
    '''
    for element in root.iter():
        element.tag = re.sub('\{.*\}', '', element.tag)
        
    return root


def check_pagination(response):
    for item in response['properties']['links']:
        if item['rel'] == 'next':
            return True
        else:
            continue
    return False


def parse_opensearch(_input):

    '''
    Creates a dictionary with product properties for each product found in '_input' 
    and returns the list of dictionaries   
    '''
    map_schema = {
        'startDate': 'Sensing start',
        'completionDate': 'Sensing stop',
        'coordinates': 'WKT footprint',
        'gmlgeometry': 'GML footprint',
        'id': 'id',
        'title': 'Name',
        'published': 'Ingestion date',
        'instrument': 'Instrument name',
        'orbitDirection': 'Pass direction',
        'relativeOrbitNumber': 'Relative orbit',
        'platform': 'Satellite name',
        'polarisation': 'Polarization',
        'productType': 'Product type',
        'sensorMode': 'Instrument mode',
        'size': 'Size',
        'status': 'Status',
        'swath': 'Instrument swath'
        }
    
    liste = []
    for product in _input:
        dicte={}
        for k in product:
            if k == 'id':
                dicte[map_schema[k]] = str(product['id'])
        for k in product['properties']:
            if k == 'services':
                check = explore_json(product['properties'].get('services'))
                size = check.get('download').get('size')
                #print(type(size))
                dicte[map_schema['size']] = size
            if k in map_schema.keys():
                dicte[map_schema[k]] = str(product['properties'][k])
            
                
        polygon = ogr.CreateGeometryFromGML(dicte['GML footprint'])
        dicte['WKT footprint']=polygon.ExportToWkt()
        if dicte['Name'][-5:]=='.SAFE':
            dicte['Name']=dicte['Name'][:-5]
        liste.append(dicte)
    return liste

def parse_safe(_input):
    entries = {}
    
    root = None
    if hasattr(_input, 'read'):
        root = ET.parse(_input).getroot()
    else:
        root = ET.fromstring(_input)
    
    root = filter_namespaces(root)
    entries.update(get_acquisition_period(root))
    entries.update(get_platform(root))
    entries.update(get_orbit(root))
    entries.update(get_standalone_product(root))
    
    return entries
    
def get_acquisition_period(root):
    map_schema = {'startTime': 'Sensing start',
                  'stopTime': 'Sensing stop'}
    
    entries = {}
    
    for element in  root.find('.//acquisitionPeriod').iter():
        tag = element.tag
        
        mapping = map_schema.get(tag)
        if mapping is not None:
            entries[mapping] = element.text
    
    return entries


def get_platform(root):
    map_schema = {'nssdcIdentifier': 'NSSDC identifier',
                  'familyName': 'Satellite name',
                  'number': 'Satellite number',
                  'instrument_familyName': 'Instrument name',
                  'instrument_mode': 'Instrument mode',
                  'instrument_swath': 'Instrument swath'}
    
    entries = {}
    
    instr_entry = False 
    for element in root.find('.//platform').iter():
        tag  = element.tag

        if tag == 'instrument':
            instr_entry = True
            
        if instr_entry:
            tag = 'instrument_' + tag
        
        if tag == 'instrument_familyName':
            entries['Instrument abbreviation'] = element.get('abbreviation')
                
        mapping = map_schema.get(tag) 
        if mapping is not None:
            entries[mapping] = element.text
            
    return entries


def get_orbit(root):
    map_schema = {'orbitNumber_start': 'Start orbit number',
                  'orbitNumber_stop': 'Stop orbit number',
                  'relativeOrbitNumber_start': 'Start relative orbit number',
                  'relativeOrbitNumber_stop': 'Stop relative orbit number',
                  'cycleNumber': 'Cycle number',
                  'phaseIdentifier': 'Phase identifier',
                  'pass': 'Pass direction'}
    
    entries = {}
    
    for element in root.find('.//orbitReference').iter():
        tag = element.tag
        
        if element.get('type') is not None:
            tag = tag + '_' + element.get('type')
        
        mapping = map_schema.get(tag)
        if mapping is not None:
            entries[mapping] = element.text
            
    return entries


def get_standalone_product(root):
    map_schema = {'byteOrder': 'Byte Order',
                  'calCompressionType': 'Cal Compression Type',
                  'calISPPresent': 'Cal ISP present',
                  'circulationFlag': 'Circulation flag',
                  'echoCompressionType': 'Echo Compression Type',
                  'instrumentConfigurationID': 'Instrument configuration id',
                  'missionDataTakeID': 'Mission datatake id',
                  'noiseCompressionType': 'Noise Compression Type',
                  'noiseISPPresent': 'Noise ISP present',
                  'productClass': 'Product class',
                  'productClassDescription': 'Product class description',
                  'productComposition': 'Product composition',
                  'productConsolidation': 'Product consolidation',
                  'productTimelinessCategory': 'Timeliness category',
                  'productType': 'Product type',
                  'segmentStartTime': 'Segment start time',
                  'sliceNumber': 'Slice number',
                  'sliceOverlap': 'Slice overlap',
                  'sliceProductFlag': 'slice product flag',
                  'theoreticalSliceLength': 'Theoretical slice length',
                  'transmitterReceiverPolarisation': 'Polarization'}
    
    entries = {}
    
    if root.find('.//standAloneProductInformation') is not None:
        for element in root.find('.//standAloneProductInformation').iter():
            tag = element.tag
            
            mapping = map_schema.get(tag) 
            if mapping is not None:
                entries[mapping] = element.text
            
    return entries


def parse_odata(_input):
    pass
