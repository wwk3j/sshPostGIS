

# This migrates data from ArcGIS to PostGIS/Geoserver. The process follows
# these steps (see export_layer):
#
# 1. Validate and massage the input data;
# 2. Create the appropriate objects in Geoserver;
# 3. Create the PostGIS database;
# 4. Export the data from ArcGIS into PostGIS using the QuickExport tool;
# 5. Create the PostGIS layer in Geoserver.


from collections import namedtuple
from contextlib import closing
from functools import wraps
import re
import time
import traceback

import arcpy
from geoserver.catalog import Catalog
import psycopg2, psycopg2.extensions


TRACE = True

RUN = str(int(time.time()))

#geoType = ""

BoundingBox   = namedtuple('BoundingBox', 'xmin ymin xmax ymax')
DbInfo        = namedtuple('DbInfo', 'host port database user password')
GeoserverInfo = namedtuple('GeoserverInfo', 'base_url user password')
DataInfo      = namedtuple('DataInfo', 'workspace namespace datastore')


ATTR_TYPES = {
        'bpchar'       : 'java.lang.String',
        'float4'       : 'java.lang.Double',
        'float8'       : 'java.lang.Double',
        'int2'         : 'java.lang.Short',
        'int4'         : 'java.lang.Integer',
        }
GEOM_TYPES = {
        'LINESEGMENT'  : 'com.vividsolutions.jts.geom.LineSegment',
        'LINESTRING'   : 'com.vividsolutions.jts.geom.LineString',
        'MULTIPOINT'   : 'com.vividsolutions.jts.geom.MultiPoint',
        'MULTIPOLYGON' : 'com.vividsolutions.jts.geom.MultiPolygon',
        'POINT'        : 'com.vividsolutions.jts.geom.Point',
        'POINTM'       : 'com.vividsolutions.jts.geom.Point',
        'POLYGON'      : 'com.vividsolutions.jts.geom.Polygon',
        'TRIANGLE'     : 'com.vividsolutions.jts.geom.Triangle',
        # TODO: MULTILINESTRING, GEOMETRYCOLLECTION
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


def log(*msg):
    """Print something(s) to the screen. """
    print ' '.join( str(m) for m in msg )


def trace(f):
    """\
    This enables tracing on a function. Set the value of TRACE to turn off
    tracing.

    """

    if TRACE:
        @wraps(f)
        def wrapper(*args, **kwargs):
            params = [ repr(a) for a in args ]
            params += [ '%s=%r' % item for item in sorted(kwargs.items()) ]
            log('TRACE', '%s(%s)' % (f.__name__, ', '.join(params)))

            result = f(*args, **kwargs)

            log('TRACE', '%s => %r' % (f.__name__, result))
            return result
    else:
        wrapper = f

    return wrapper


def arcpy_log(*msg):
    """Print something(s) as an arcpy message. """
    arcpy.AddMessage(' '.join( str(m) for m in msg ))

@trace
def get_geometries(c, table_name):
    """\
    This queries the PostGIS database to return a dictionary mapping geometry
    column names to geometry types for the table.

    """
    c.execute('''
        SELECT f_geometry_column, type
        FROM geometry_columns
        WHERE f_table_name=%s;
        ''',
        (table_name,),
        )
    return dict(c.fetchall())


@trace
def pg_to_attribute(c, row, geometries):
    """\
    This turns a row of column information from Postgres into an attribute
    dictionary.

    """

    (table_name, col_name, nillable, type_name) = row
    is_geom = False

    attr_type = ATTR_TYPES.get(type_name)
    # TODO: Else branch might should print a warning.
    if attr_type is None and col_name in geometries:
        attr_type = GEOM_TYPES[geometries[col_name]]
        is_geom   = True

    return {
            'name'     : col_name,
            'nillable' : nillable,
            'binding'  : attr_type,
            'is_geom'  : is_geom,
            }


@trace
def load_attributes(cxn, table_name):
    """This queries the Postgres table to get the attributes for creating the layer. """
    with closing(cxn.cursor()) as c:
        geometries = get_geometries(c, table_name)
        c.execute('''
            SELECT table_name, column_name, is_nullable, udt_name
            FROM information_schema.columns
            WHERE table_name=%s;
            ''',
            (table_name,)
            )
        col_infos = c.fetchall()
        return [ pg_to_attribute(c, row, geometries) for row in col_infos ]


@trace
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


@trace
def create_postgis_layer(
        cat, wspace, dstore, name, srs, native_crs, db_info
        ):
    """This creates and returns a new layer. """
    with closing(psycopg2.connect(**db_info._asdict())) as cxn:
        attributes = load_attributes(cxn, name)
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
            srs, native_crs
            )


@trace
def find_new_layer(layer_name):
    """This find a layer name that doesn't exist. """
    base_name = layer_name
    n = 0
    while arcpy.Exists(layer_name):
        n += 1
        layer_name = base_name + '_' + str(n)
    return layer_name


@trace
def create_run_name(name):
    """This returns a name with the run ID appended. """
    return name + '_' + RUN


@trace
def db_exists(cxn, db_name):
    """\
    This takes a connection to a Postgres object and db name and tests whether it
    exists or not.
    """
    with closing(cxn.cursor()) as c:
        c.execute('SELECT COUNT(*) FROM pg_database WHERE datname=%s;',
                  [db_name])
        (count,) = c.fetchone()
        return count > 0


@trace
def createConnObj(db_info):
    """This creates a PostGIS connection. """
    try:
        connxion = psycopg2.connect(**db_info._asdict())
    except psycopg2.InterfaceError:
        raise SystemExit("unable to connect to database")
    return connxion


@trace
def createNewDb(connection, localDbn):
    """This creates a new database. """
    with closing(connection.cursor()) as cur:
        try:
            connection.autocommit = True
            if not(db_exists(connection, localDbn)):
                cur.execute('CREATE DATABASE %s TEMPLATE geodb CONNECTION LIMIT 2' % (localDbn,))
        except psycopg2.extensions.QueryCanceledError:
            raise SystemExit('postgis connection timed out')


@trace
def explodeGeo(featLayer):
    """This actually implodes a multi-part layer into a single-part layer. """
    if not featLayer.isFeatureLayer:
        raise SystemExit("not feature layer, please input feature layer.")
    layer = find_new_layer(featLayer.name + '_singlepart')
    arcpy.MultipartToSinglepart_management(featLayer, layer)
    return layer


@trace
def geoValidate(featLayer):
    """This performs validation on the feature layer. """
    exList = []
    fields = arcpy.ListFields(featLayer, "", "String")

    # Validate bounding box.
    extent = arcpy.Describe(featLayer).extent
    if extent.XMin > extent.XMax:
        exList.append('Invalid bounding box (X).')
    if extent.YMin > extent.YMax:
        exList.append('Invalid bounding box (Y).')

    rows = arcpy.SearchCursor(featLayer)
    while True:
        row = rows.next()
        if not row:
            break

        for field in fields:
            if field.name == "Shape":
                if row.getValue(field.name) == "Polygon":
                    if field.name == "Shape_Area":              # WING: This will always be false (see two lines up). What are you trying to test for?
                        if row.getValue(field.name) == 0:
                            exList.append("zero area polygon")
            elif field.name == "Polyline":
                if row.getValue(field.name) == 0:
                    exList.append("line length is zero")
            elif field.name == "Point":
                if field.name == "LONGITUDE":
                    if row.getValue(field.name) > 90 or row.getValue(field.name) < -90:
                        exList.append("Longitude has non-applicable values")
                        if field.name == "LATITUDE":            # WING: This always won't be reached.
                            if row.getValue(field.name) > 180 or row.getValue(field.name) < -180:
                                exList.append("Latitude has non-applicable values")

    if exList:
        raise Exception('; '.join(exList))

    return featLayer


@trace
def get_srs(layer):
    """This takes a layer and returns the srs and native crs for it. """
    layer_descr = arcpy.Describe(layer)

    spatialRef = layer_descr.spatialReference
    spaRef = 'EPSG:%s' % (spatialRef.factoryCode,)

    # use this for the native_crs xml
    # first, figure out exactly which properties to use.
    native_crs = spatialRef.exportToString()
    if ";" in native_crs:
        native_crs = native_crs.split(";", 1)[0]
    native_crs = native_crs.replace("'", '"')

    return (spaRef, native_crs)


@trace
def fix_geoserver_info(gs_info):
    """This makes sure that the Geoserver URL points to the rest interface. """
    gs_info = gs_info._replace(
            base_url=gs_info.base_url.rstrip('/'),
            )

    if gs_info.base_url.endswith('/web'):
        gs_info = gs_info._replace(
                base_url=gs_info.base_url[:-4]
                )

    if not gs_info.base_url.endswith('/rest'):
        gs_info = gs_info._replace(
                base_url=gs_info.base_url + '/rest'
                )

    return gs_info


@trace
def create_datastore(cat, workspace, db_info, data_info):
    """This creates the datastore on geoserver. """
    datastore = cat.create_datastore(data_info.datastore, workspace)

    if datastore.connection_parameters is None:
        datastore.connection_parameters = {}
    datastore.connection_parameters.update(db_info._asdict())
    datastore.connection_parameters.update(dict(
        port   = str(db_info.port),
        schema = 'public',
        dbtype = 'postgis',
        ))

    cat.save(datastore)
    return datastore


@trace
def make_export_params(db_info):
    """\
    This takes the db_info and converts it into a parameter string to pass to
    the QuickExport tool.

    """

    params = [
            'POSTGIS',                          db_info.database,
            '"RUNTIME_MACROS',
            '""HOST',                           db_info.host,
            'PORT',                             str(db_info.port),
            'USER_NAME',                        db_info.user,
            'PASSWORD',                         db_info.password,
            'GENERIC_GEOMETRY',                 'no',
            'LOWERCASE_ATTRIBUTE_NAMES',        'Yes""',
            'META_MACROS',
            '""DestHOST',                       db_info.host,
            'DestPORT',                         str(db_info.port),
            'DestUSER_NAME',                    db_info.user,
            'DestPASSWORD',                     db_info.password,
            'DestGENERIC_GEOMETRY',             'no',
            'DestLOWERCASE_ATTRIBUTE_NAMES',    'Yes""',
            'METAFILE',
            'POSTGIS',
            'COORDSYS',
            '',
            '__FME_DATASET_IS_SOURCE_',         'false"'
            ]

    return ','.join(params)


@trace
def quick_export(layer, db_info):
    """A small facade over the QuickExport tool. """
    # arcpy.SetSeverityLevel(2)
    # arcpy.CheckOutExtension("DataInteroperability")
    params = make_export_params(db_info)
    arcpy.QuickExport_interop(layer, params)


@trace
def export_layer(db_info, gs_info, data_info, layer_name):
    """\
    This takes the parameters and performs the export.

    This can be run as a module or called from other code.

    """

    geoValidate(layer_name)
    layer = explodeGeo(layer_name)
    (spaRef, native_crs) = get_srs(layer)

    cat = Catalog(*tuple(gs_info))
    wspace = cat.create_workspace(data_info.workspace, data_info.namespace)
    datastore = create_datastore(cat, wspace, db_info, data_info)

    with closing(createConnObj(db_info._replace(database='postgres'))) as cxn:
        createNewDb(cxn, db_info.database)
    quick_export(layer, db_info)
    create_postgis_layer(
            cat, wspace, datastore, layer, spaRef, native_crs, db_info,
            )

    try:
        # TODO: Surely we don't mean to actually delete the layer before we QE
        # it?
        arcpy.DeleteFeatures_management(layer)
    except:
        log(arcpy.GetMessages())


def main():
    """\
    This reads the parameters from the arcpy parameters and performs the
    export.

    """

    # Clobber the log function to send everything to arcpy.AddMessage.
    global log
    log = arcpy_log

    try:
        featLayer = arcpy.GetParameter(0)

        # TODO: Need to prompt for Geoserver info, data info. NOTHING below should
        # be hard-coded.
        db_info   = DbInfo(
                host     = arcpy.GetParameterAsText(1),
                port     = int(arcpy.GetParameterAsText(2)),
                database = arcpy.GetParameterAsText(5),
                user     = arcpy.GetParameterAsText(3),
                password = arcpy.GetParameterAsText(4),
                )
        gs_info   = GeoserverInfo(
                base_url = 'http://geoserver.dev:8080/geoserver/web',
                user     = 'admin',
                password = 'geoserver',
                )
        data_info = DataInfo(
                workspace = create_run_name('sshPostGISws'),
                namespace = create_run_name('uri:uva.sshPostGIS'),
                datastore = create_run_name('sshPostGISds'),
                )

        if not arcpy.Exists(featLayer):
            raise RuntimeError('error in feature layer passed')

        gs_info = fix_geoserver_info(gs_info)

        export_layer(db_info, gs_info, data_info, featLayer)
    except:
        tb = traceback.format_exc()
        log('ERROR', tb)
        raise


if __name__ == '__main__':
    main()



