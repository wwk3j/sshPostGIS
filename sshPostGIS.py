#testing a python SSH module
from collections import namedtuple
import sys, arcpy, psycopg2, psycopg2.extensions, urllib2, geoserver, random, re, pprint 
from contextlib import closing, contextmanager
import time

run = int(time.time())

#geoType = ""

BoundingBox = namedtuple('BoundingBox', ['xmin', 'ymin', 'xmax', 'ymax'])

ATTR_TYPES = {
        'bpchar'       : 'java.lang.String',
        'float8'       : 'java.lang.Double',
        'int2'         : 'java.lang.Short',
        'int4'         : 'java.lang.Integer',

        'LINESEGMENT'  : 'com.vividsolutions.jts.geom.LineSegment',
        'LINESTRING'   : 'com.vividsolutions.jts.geom.LineString',
        'MULTIPOINT'   : 'com.vividsolutions.jts.geom.MultiPoint',
        'MULTIPOLYGON' : 'com.vividsolutions.jts.geom.MultiPolygon',
        'POINT'        : 'com.vividsolutions.jts.geom.Point',
        'POINTM'       : 'com.vividsolutions.jts.geom.Point',
        'POLYGON'      : 'com.vividsolutions.jts.geom.Polygon',
        'TRIANGLE'     : 'com.vividsolutions.jts.geom.Triangle',
        }
reEXTENT = re.compile(r'''
    ^ BOX \(
        ( [\d\.-]* ) \s+ ( [\d\.-]* )
        , \s*
        ( [\d\.-]* ) \s+ ( [\d\.-]* )
    \) $
    ''',
    re.VERBOSE,
    )

def log(msg):
    print msg

def pg_to_attribute(c, row):
    """\
    This turns a row of column information from Postgres into an attribute
    dictionary.

    """

    (table_name, col_name, nillable, type_name) = row
    is_geom = False
    attr_type = ATTR_TYPES.get(type_name)
    if attr_type is None:
        c.execute('SELECT DISTINCT GeometryType("%s") FROM "%s";' % (
                    col_name, table_name))
        # Since there should only be one geomtry type, only take the first one.
        attr_type = ATTR_TYPES.get(c.fetchone()[0])
        is_geom   = True
    return {
        #may have to fix this 'name' part
            'name'     : col_name,
            'nillable' : nillable,
            'binding'  : attr_type,
            'is_geom'  : is_geom,
            }


def load_attributes(cxn, table_name):
    """This queries the Postgres table to get the attributes for creating the layer. """
    with closing(cxn.cursor()) as c:
        c.execute('''
            SELECT table_name, column_name, is_nullable, udt_name
            FROM information_schema.columns
            WHERE table_name=%s;
            ''',
            (table_name,)
            )
        col_infos = c.fetchall()
        return [ pg_to_attribute(c, row) for row in col_infos ]


def get_bounding_box(cxn, table_name, col_name):
    """This queries the PostGIS table for the native bounding box. """
    with closing(cxn.cursor()) as c:
        c.execute('SELECT ST_Extent("{col}") FROM "{table}";'.format(
            col=col_name, table=table_name,
            ))
        extent = c.fetchone()[0]

        m = reEXTENT.match(extent)
        if m is None:
            log('WARNING: Invalid bounding box: %s' % (extent,))
            bounding = BoundingBox(0, 0, 0, 0)
        else:
            bounding = BoundingBox._make(
                    float(m.group(n)) for n in range(1, 5)
                    )

        return bounding

def create_postgis_layer(
        cat, wspace, dstore, name, srs, native_crs, db_params, log
        ):
    """This creates and returns a new layer. """
    log('create_postgis_layer')

    with closing(psycopg2.connect(**db_params)) as cxn:
        attributes = load_attributes(cxn, name)
        arcpy.AddMessage(repr(attributes))
        for attr in attributes:
            if attr['is_geom']:
                bounds = get_bounding_box(cxn, name, attr['name'])
                break
        else:
            bounds = BoundingBox(0, 0, 0, 0)

    native = name
    title  = name

    return cat.create_postgres_layer(
            wspace.name, dstore.name, name, native, title, srs, attributes,
            bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax,
            srs, native_crs, log
            )

#---------------------------------------------------------USE MODULES ABOVE WITH THE CXN OBJECT-----------------------------------------------------------------
def find_new_layer(layer_name):
    base_name = layer_name
    n = 0
    while arcpy.Exists(layer_name):
        n += 1
        layer_name = base_name + '_' + str(n)
    return layer_name

def create_new_ds_name(name):
    base_name = name
    name = base_name + '_' + str(run)
    return name

def db_exists(cxn, db_name):
    """\
This takes a connection to a Postgres object and db name and tests whether it
exists or not.
"""
    with closing(cxn.cursor()) as c:
        c.execute('SELECT COUNT(*) FROM pg_database WHERE datname=%s;', [db_name])
        #c.execute('select %s from pg_tables where schemaname='public';', db_name)
        #if 
        (count,) = c.fetchone()
        return count > 0

def createConObj():
    try:
        connxion = psycopg2.connect(host=server, database='postgres', user=usrName, port=portnum, password=passWord)
    except psycopg2.InterfaceError:
        arcpy.AddMessage("unable to connect to database")
        sys.exit(1)
    return connxion

def createCurObj(connection):
    localDbn = dbname
    cur = connection.cursor()
    try:
        connection.autocommit = True
        arcpy.AddMessage('localDbn=%r\n' % (localDbn,))
        arcpy.AddMessage('db_exists => %r\n' % (db_exists(connection, localDbn),))
        arcpy.AddMessage('post db-exists \n')
        if not(db_exists(connection, localDbn)):
            cur.execute('CREATE DATABASE %s TEMPLATE geodb CONNECTION LIMIT 2' %(localDbn))
    except psycopg2.extensions.QueryCanceledError:
        print "timed out"
        sys.exit(1)
    cur.close()
    connection.close()

def explodeGeo(featLayer):
    if not featLayer.isFeatureLayer:
        print "not feature layer, please input feature layer."
        sys.exit(1)
    else:
        layer = find_new_layer(featLayer.name + '_singlepart')
        arcpy.MultipartToSinglepart_management(featLayer, layer)
    return layer
        

def geoValidate(featLayer):
    arcpy.AddMessage("B.4 %s\n" % (dir(featLayer),))
    exList = []
    rows = arcpy.SearchCursor(featLayer)
    row = rows.next()
    fields = arcpy.ListFields(featLayer, "", "String")
    while row:
        for field in fields:
            # arcpy.AddMessage("%s (%s) = %r" % (field.name, field.type, row.getValue(field.name)))
            if field.name == "Shape":
                if row.getValue(field.name) == "Polygon":
                    if field.name == "Shape_Area":
                        if row.getValue(field.name) == 0:
                            exList.append("zero area polygon")
            elif field.name == "Polyline":
                if row.getValue(field.name) == 0:
                    exList.append("line length is zero")
            elif field.name == "Point":
                if field.name == "LONGITUDE":
                    if row.getValue(field.name) > 90 or row.getValue(field.name) < -90:
                        exList.append("Longitude has non-applicable values")
                        if field.name == "LATITUDE":
                            if row.getValue(field.name) > 180 or row.getValue(field.name) < -180:
                                exList.append("Latitude has non-applicable values")       
        row = rows.next()
    if exList:
        raise Exception('; '.join(exList))
    return featLayer
    
    
params = arcpy.GetParameterInfo()
server = arcpy.GetParameterAsText(0)
portnum = int(arcpy.GetParameterAsText(1))
usrName = arcpy.GetParameterAsText(2)
passWord = arcpy.GetParameterAsText(3)
dbname = arcpy.GetParameterAsText(4)
featLayer = arcpy.GetParameter(5)
if not(arcpy.Exists(arcpy.GetParameter(5))):
    raise RuntimeError('error in feature layer passed')
else:
    createCurObj(createConObj())
    geoValidate(featLayer)
    
    layer = explodeGeo(featLayer)
    spatialRef = arcpy.Describe(layer).spatialReference
    # use this for the native_crs xml
    # first, figure out exactly which properties to use. 
    native_crs = spatialRef.exportToString()
    arcpy.AddMessage(native_crs)
    if ";" in native_crs:
        native_crs, leftover = native_crs.split(";", 1)
    arcpy.AddMessage(native_crs)
    desc = arcpy.Describe(layer)
    ext = desc.extent
    arcpy.AddMessage(', '.join(dir(ext)))
    arcpy.AddMessage("Describing %r => %r\n\n" % (layer, ext))
    arcpy.AddMessage('%r / %r / %r / %r\n\n' % (ext.upperRight, ext.lowerRight, ext.upperLeft, ext.lowerLeft))
    arcpy.AddMessage('%r, %r - %r, %r\n\n' % (ext.XMin, ext.YMin, ext.XMax, ext.YMax))
    lyname = arcpy.GetParameterAsText(6)
    arcpy.AddMessage(dir(spatialRef))
    spaRef = 'EPSG:%s' %(spatialRef.factoryCode)
    XMin = ext.XMin
    YMin = ext.YMin
    XMax = ext.XMax
    YMax = ext.YMax

try:
    
    arcpy.AddMessage(arcpy.GetSeverityLevel())
    arcpy.SetSeverityLevel(1)
    #arcpy.DeleteFeatures_management(layer)
except:
    print arcpy.GetMessages()

try:
    from geoserver.catalog import Catalog
except ImportError:
    import traceback
    tb = traceback.format_exc()
    arcpy.AddMessage('Cannot import: %s\n' % (tb,))
    raise

try:
    cat = Catalog("http://localhost:8080/geoserver/rest", "admin", "geoserver")
    wsName = "tempWS" + str(run)
    wspace = cat.create_workspace(wsName, "http://www.justice" + str(run) + "inc.gov" )
    name= "dat_store"
    name = create_new_ds_name(name)
    datastore = cat.create_datastore(name, wspace)
    datastore.connection_parameters = dict(
        host="localhost",
        port="5432",
        database=dbname,
        user ="vagrant",
        schema = "public",
        passwd="vagrant",
        dbtype="postgis")
    cat.save(datastore)
    #global geoType
    #g = arcpy.Geometry()
    #geometryList = arcpy.CopyFeatures_management(featLayer, g)
    #for geometry in geometryList:
     #   if geometry.type == "polygon":
      #      geoType = 'com.vividsolutions.jts.geom.Polygon'
       # elif geometry.type == "polyline":
        #    geoType = 'com.vividsolutions.jts.geom.LineString'
        #elif geometry.type == "multipoint" or geometry.type == "point":
         #   geoType = 'com.vividsolutions.jts.geom.Point'
    arcpy.AddMessage(arcpy.__file__)
    arcpy.AddMessage(sys.version)
    #arcpy.AddMessage(geoType)
    #attributes = {'the_geom': geoType, 'description': 'java.lang.String', 'timestamp': 'java.util.Date'}
    nativeName = "dataType1"
    layerTitle = "Lyr3"
    # arcpy.AddMessage('<%s> <%s> <%s>' % (cat.service_url, wspace, name))
    if XMin > XMax:
        print "illegal bbox"
    db_params = dict(
        host = 'localhost',
        port = '5432',
        database = dbname,
        user = 'vagrant',
        password = 'vagrant', 
        )
    arcpy.AddMessage("using alternate version of create postgis layer here")
    #cat.create_postgres_layer(wsName, name, lyname, nativeName, layerTitle, spaRef, attributes, XMin, YMin, XMax, YMax, spaRef, native_crs,
                             # arcpy.AddMessage)
    # arcpy.AddMessage('%s: <%s>\n%r\n\n%s' % debug)
    qe_params = {
        'dbname' : '%dbname,',
        'server' : '%server,',
        'portnum' : '%portnum,',
        'usrName' : '%usrName,',
        'passWord' : '%passWord,',
        }
    
    arcpy.CheckOutExtension("DataInteroperability")
    try:
        params = (
            'POSTGIS,%s,"RUNTIME_MACROS,""HOST,%s,PORT,%d,USER_NAME,%s,PASSWORD,%s,GENERIC_GEOMETRY,no,'
            'LOWERCASE_ATTRIBUTE_NAMES,Yes"",META_MACROS,""DestHOST,%s,DestPORT,%d,DestUSER_NAME,%s,DestPASSWORD,%s,DestGENERIC_GEOMETRY,no,'
            'DestLOWERCASE_ATTRIBUTE_NAMES,Yes"",METAFILE,POSTGIS,COORDSYS,,__FME_DATASET_IS_SOURCE_,false"' %
                (dbname, server , portnum, usrName, passWord, server, portnum, usrName, passWord)
            )
        #QuickExport: ne_10m_populated_places_singlepart_153, 'POSTGIS,mar082012_3,"RUNTIME_MACROS,""HOST,localhost,PORT,5432,USER_NAME,vagrant,PASSWORD,vagrant,GENERIC_GEOMETRY,no,        LOWERCASE_ATTRIBUTE_NAMES,Yes"",META_MACROS,""DestHOST,localhost,DestPORT,5432,DestUSER_NAME,vagrant,DestPASSWORD,vagrant,DestGENERIC_GEOMETRY,no,         DestLOWERCASE_ATTRIBUTE_NAMES,Yes"",METAFILE,POSTGIS,COORDSYS,,__FME_DATASET_IS_SOURCE_,false"'
        #arcpy.QuickExport_interop(layer, 'POSTGIS,' + dbname + "RUNTIME_MACROS,""HOST," + server + "PORT," + unicode(portnum) + "USER_NAME," + usrName + "PASSWORD," + passWord + "GENERIC_GEOMETRY,no, \
        #LOWERCASE_ATTRIBUTE_NAMES,Yes,""META_MACROS,""DestHOST," + server + "DestPORT," + unicode(portnum) + "DestUSER_NAME," + usrName + "DestPASSWORD," + passWord + "DestGENERIC_GEOMETRY,no, \
        #DestLOWERCASE_ATTRIBUTE_NAMES,Yes"",METAFILE,POSTGIS,COORDSYS,,__FME_DATASET_IS_SOURCE_,false" %(dbname,(server),(portnum),(usrName),(passWord),(server),(portnum),(usrName),(passWord)))
        arcpy.AddMessage('QuickExport: %s, \'%s\'' % (layer, params))
        #consider getting rid of the escape chars between the string params
        arcpy.SetSeverityLevel(2)
        print arcpy.GetSeverityLevel()
        output = arcpy.QuickExport_interop(layer, params)
    except arcpy.ExecuteWarning, warning:
        arcpy.AddMessage('QuickExport warning: %s' % (warning,))
    finally:
        print arcpy.GetSeverityLevel()
        arcpy.GetMessages()
        arcpy.AddMessage('OUT = ' + repr(output))
    #except:
     #   print arcpy.AddMessage('QuickExport Parameters invalid')
      #  raise Exception('whatever')
    create_postgis_layer(cat, wspace, datastore, lyname, spaRef, native_crs, db_params, log)
except:
    import traceback
    tb = traceback.format_exc()
    arcpy.AddMessage('ERROR TB: %s' % (tb,))
    raise




