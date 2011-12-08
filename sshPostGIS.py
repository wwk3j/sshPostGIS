#testing a python SSH module
import sys, arcpy, psycopg2, psycopg2.extensions
from contextlib import closing

def find_new_layer(layer_name):
    base_name = layer_name
    n = 0
    while arcpy.Exists(layer_name):
        n += 1
        layer_name = base_name + '_' + str(n)
    return layer_name

def db_exists(cxn, db_name):
    """\
This takes a connection to a Postgres object and db name and tests whether it
exists or not.
"""
    with closing(cxn.cursor()) as c:
        arcpy.AddMessage('B.1')
        c.execute('SELECT COUNT(*) FROM pg_database WHERE datname=%s;', [db_name])
        arcpy.AddMessage('B.2')
        (count,) = c.fetchone()
        arcpy.AddMessage('B.3')
        return count > 0

def createConObj():
    arcpy.AddMessage('A')
    try:
        connxion = psycopg2.connect(host=server, database='postgres', user=usrName, port=portnum, password=passWord)
    except psycopg2.InterfaceError:
        arcpy.AddMessage("unable to connect to database")
        sys.exit(1)
    return connxion

def createCurObj(connection):
    localDbn = dbname
    cur = connection.cursor()
    arcpy.AddMessage('B')
    try:
        connection.autocommit = True
        arcpy.AddMessage('localDbn=%r' % (localDbn,))
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
    rows = arcpy.SearchCursor(featLayer)
    row = rows.next()
    exList = []
    #fields = arcpy.ListFields(layer, "Shape", "Shape_Area", "Shape_Length")
    #refer to SearchCursor page because cursor cannot use getValue
    while row:
        #for field in fields:
        shpType = row.getValue("Shape")
        polyArea = row.getValue("Shape_Area")
        lineLength = row.getValue("Shape_Length")
        #latVal = row.getValue("LATITUDE")
        #lonVal = row.getValue("LONGITUDE")
        if shpType == "Polygon":
            if polyArea == 0:
                exList.append('area is zero')
                #arcpy.DeleteRows_management(polyArea)
        elif shpType == "Polyline":
            if lineLength == 0:
                exList.append('length is zero') 
                #arcpy.DeleteRows_management(linelength)
        elif shpType == "Point":
            if latVal > 180 or latVal < -180:
                exList.append('non-applicable latitude value, exceeds 90 degrees either pole') 
            elif lonVal > 90 or lonVal < -90:
                exList.append('non-applicable longitude value, exceeds 180 degrees either pole')           
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
    #may need to switch these layer and featLayer names
    layer = explodeGeo(featLayer)
    arcpy.AddMessage('C')
   
    
# TODO: This always gets run. Delete feature here, maybe.

try:
    #this try/catch is for Error 000464 in case the data is currently being used in another ArcGIS app.
    #you cannot delete a layer when it is used in another ArcGIS app although we can assume it isn't being used.
    arcpy.AddMessage(arcpy.GetSeverityLevel())
    arcpy.SetSeverityLevel(1)
    arcpy.DeleteFeatures_management(layer)
except:
    print arcpy.GetMessages()
arcpy.QuickExport_interop(layer)

