#! /usr/bin/env python

from collections import namedtuple
from contextlib import closing, contextmanager
import pprint
import time

import psycopg2

from geoserver.catalog import Catalog


GEOSERVER = 'http://geoserver2.dev:8080/geoserver/rest'
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

NATIVE_CRS = '''
PROJCS["WGS 84 / UTM zone 18N", 
  GEOGCS["WGS 84", 
    DATUM["World Geodetic System 1984", 
      SPHEROID["WGS 84", 6378137.0, 298.257223563, AUTHORITY["EPSG","7030"]], 
      AUTHORITY["EPSG","6326"]], 
    PRIMEM["Greenwich", 0.0, AUTHORITY["EPSG","8901"]], 
    UNIT["degree", 0.017453292519943295], 
    AXIS["Geodetic longitude", EAST], 
    AXIS["Geodetic latitude", NORTH], 
    AUTHORITY["EPSG","4326"]], 
  PROJECTION["Transverse_Mercator", AUTHORITY["EPSG","9807"]], 
  PARAMETER["central_meridian", -75.0], 
  PARAMETER["latitude_of_origin", 0.0], 
  PARAMETER["scale_factor", 0.9996], 
  PARAMETER["false_easting", 500000.0], 
  PARAMETER["false_northing", 0.0], 
  UNIT["m", 1.0], 
  AXIS["Easting", EAST], 
  AXIS["Northing", NORTH], 
  AUTHORITY["EPSG","32618"]]
'''

BoundingBox = namedtuple('BoundingBox', ['xmin', 'ymin', 'xmax', 'ymax'])


def log(msg):
    """This just prints a message. It's a callback for status messages. """
    print msg


def create_workspace(cat, name, uri):
    """This creates an returns the namespace with the given name and uri. """
    log('create_workspace')
    return cat.create_workspace(name, uri)


def create_ds(cat, wspace, name, dbname, db_params):
    """This creates and returns the datastore. """
    log('create_ds')
    ds = cat.create_datastore(name, wspace)
    ds.connection_parameters = db_params.copy()
    ds.connection_parameters.update(dict(
            passwd = db_params['password'],
            schema = "public",
            dbtype = "postgis"
            ))
    cat.save(ds)
    return ds


def pg_to_attribute(c, row):
    """\
    This turns a row of column information from Postgres into an attribute
    dictionary.

    """

    (table_name, col_name, nillable, type_name) = row

    attr_type = ATTR_TYPES.get(type_name)
    if attr_type is None:
        c.execute('SELECT DISTINCT GeometryType("%s") FROM "%s";' % (
                    col_name, table_name))
        # Since there should only be one geomtry type, only take the first one.
        attr_type = ATTR_TYPES.get(c.fetchone()[0])

    return {
            'name'     : col_name,
            'nillable' : nillable,
            'binding'  : attr_type,
            }


def load_attributes(db_params, table_name):
    """This queries the Postgres table to get the attributes for creating the layer. """
    with closing(psycopg2.connect(**db_params)) as cxn:
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


def create_postgis_layer(
        cat, wspace, dstore, name, srs, bounds, native_crs, db_params, log
        ):
    """This creates and returns a new layer. """
    log('create_postgis_layer')

    attributes = load_attributes(db_params, name)
    native     = name
    title      = name

    return cat.create_postgres_layer(
            wspace.name, dstore.name, name, native, title, srs, attributes,
            bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax,
            srs, native_crs, log
            )


def main():
    # Some values for the run.
    run         = int(time.time())
    dbname      = 'Falmouth'
    layer_name  = 'F_Polygons2'
    db_params   = dict(
            host     = 'geoserver2.dev',
            port     = '5432',
            database = dbname,
            user     = 'vagrant',
            password = 'vagrant',
            )
    name_prefix = '%s%s' % (dbname, run)
    geo_type    = 'com.vividsolutions.jts.geom.MultiPolygon'
    srs         = 'EPSG:32618'
    bounds      = BoundingBox(
            -77.65885535032194, 18.49018108988885,
            -77.63576126294949, 18.502941534123202,
            )
    native_crs  = NATIVE_CRS

    # Now, for the actual processing.
    cat        = Catalog(GEOSERVER, "admin", "geoserver")
    wspace     = create_workspace(cat, 'ws_' + name_prefix,
                                  'uri://' + name_prefix)
    data_store = create_ds(cat, wspace, 'ds_' + name_prefix, dbname, db_params)
    layer      = create_postgis_layer(cat, wspace, data_store, layer_name, srs,
                                      bounds, native_crs, db_params, log)


if __name__ == '__main__':
    main()

