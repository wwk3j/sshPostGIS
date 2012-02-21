#testing a python SSH module
import sys, arcpy, psycopg2, psycopg2.extensions, urllib2, geoserver, random
from contextlib import closing
import time

run = int(time.time())

geoType = ""

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
    # use this for the nativeCRS xml
    # first, figure out exactly which properties to use. 
    nativeCRS = spatialRef.exportToString()
    arcpy.AddMessage(nativeCRS)
    if ";" in nativeCRS:
        nativeCRS, leftover = nativeCRS.split(";", 1)
    arcpy.AddMessage(nativeCRS)
    desc = arcpy.Describe(layer)
    ext = desc.extent
    arcpy.AddMessage(', '.join(dir(ext)))
    arcpy.AddMessage("Describing %r => %r\n\n" % (layer, ext))
    arcpy.AddMessage('%r / %r / %r / %r\n\n' % (ext.upperRight, ext.lowerRight, ext.upperLeft, ext.lowerLeft))
    arcpy.AddMessage('%r, %r - %r, %r\n\n' % (ext.XMin, ext.YMin, ext.XMax, ext.YMax))
    lyname = arcpy.GetParameterAsText(6)
    arcpy.AddMessage(dir(spatialRef))
    spaRef = 'EPSG:%s' %(spatialRef.factoryCode)
    latlonbox = ('<latLonBoundingBox> \
                    <minx>%r</minx> \
                    <maxx>%r</maxx> \
                    <miny>%r</miny> \
                    <maxy>%r</maxy> \
                    <crs>%r</crs> \
                    </latLonBoundingBox>' % (ext.XMin, ext.YMin, ext.XMax, ext.YMax, spaRef))
    XMin = ext.XMin
    YMin = ext.YMin
    XMax = ext.XMax
    YMax = ext.YMax
    print "%s\n" % (latlonbox)
try:
    
    arcpy.AddMessage(arcpy.GetSeverityLevel())
    arcpy.SetSeverityLevel(1)
    arcpy.DeleteFeatures_management(layer)
except:
    print arcpy.GetMessages()

try:
    arcpy.QuickExport_interop(layer, 'POSTGIS,%s,"RUNTIME_MACROS,""HOST,%s,PORT,%d,USER_NAME,%s,PASSWORD,%s,GENERIC_GEOMETRY,no,\
    LOWERCASE_ATTRIBUTE_NAMES,Yes"",META_MACROS,""DestHOST,%s,DestPORT,%d,DestUSER_NAME,%s,DestPASSWORD,%s,DestGENERIC_GEOMETRY,no, \
    DestLOWERCASE_ATTRIBUTE_NAMES,Yes"",METAFILE,POSTGIS,COORDSYS,,__FME_DATASET_IS_SOURCE_,false"' %(dbname,(server),(portnum),(usrName),(passWord),(server),(portnum),(usrName),(passWord)))
except arcpy.ExecuteWarning, warning:
    arcpy.AddMessage('QuickExport warning: %s' % (warning,))
except:
    print arcpy.AddMessage('QuickExport Parameters invalid')
    raise
#just in case of 404 or 500 errors

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
    global geoType
    g = arcpy.Geometry()
    geometryList = arcpy.CopyFeatures_management(featLayer, g)
    for geometry in geometryList:
        if geometry.type == "polygon":
            geoType = 'com.vividsolutions.jts.geom.Polygon'
        elif geometry.type == "polyline":
            geoType = 'com.vividsolutions.jts.geom.LineString'
        elif geometry.type == "multipoint" or geometry.type == "point":
            geoType = 'com.vividsolutions.jts.geom.Point'
    arcpy.AddMessage(arcpy.__file__)
    arcpy.AddMessage(sys.version)
    arcpy.AddMessage(geoType)
    attributes = {'the_geom': geoType, 'description': 'java.lang.String', 'timestamp': 'java.util.Date'}
    nativeName = "dataType1"
    layerTitle = "Lyr3"
    # arcpy.AddMessage('<%s> <%s> <%s>' % (cat.service_url, wspace, name))
    if XMin > XMax:
        print "illegal bbox"
    cat.create_postgres_layer(wsName, name, lyname, nativeName, layerTitle, spaRef, attributes, XMin, YMin, XMax, YMax, spaRef, nativeCRS,
                              arcpy.AddMessage)
    # arcpy.AddMessage('%s: <%s>\n%r\n\n%s' % debug)
    raise Exception('whatever')
except:
    import traceback
    tb = traceback.format_exc()
    arcpy.AddMessage('ERROR TB: %s' % (tb,))
    raise




