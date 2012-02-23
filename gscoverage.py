#! /usr/bin/env python

from geoserver.catalog import Catalog
from collections import namedtuple
import time


GEOSERVER = 'http://geoserver2.dev:8080/geoserver/rest'


BoundingBox = namedtuple('BoundingBox', ['xmin', 'ymin', 'xmax', 'ymax'])


# Settings
run         = int(time.time())
dbname      = 'Falmouth'
layer_name  = 'F_Polygons2'
name_prefix = '%s%s' % (dbname, run)
geo_type    = 'com.vividsolutions.jts.geom.MultiPolygon'
srs         = 'EPSG:32618'
bounds      = BoundingBox(
        -77.65885535032194, 18.49018108988885,
        -77.63576126294949, 18.502941534123202,
        )
native_crs  = '''
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


def log(msg):
    print msg


def create_workspace(cat):
    log('create_workspace')
    ws_name = 'ws_' + name_prefix
    wspace  = cat.create_workspace(ws_name, 'uri://' + name_prefix)
    return wspace


def create_ds(cat, wspace, name, dbname):
    log('create_ds')
    ds = cat.create_datastore(name, wspace)
    ds.connection_parameters = dict(
            host     = "localhost",
            port     = "5432",
            database = dbname,
            user     = "vagrant",
            schema   = "public",
            passwd   = "vagrant",
            dbtype   = "postgis"
            )
    cat.save(ds)
    return ds


def create_postgis_layer(
        cat, wspace, dstore, name, srs, bounds, native_crs, log
        ):
    log('create_postgis_layer')

    attributes = {
            'geom'        : geo_type,
    }
    native     = name
    title      = name

    return cat.create_postgres_layer(
            wspace.name, dstore.name, name, native, title, srs, attributes,
            bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax,
            srs, native_crs, log
            )


cat        = Catalog(GEOSERVER, "admin", "geoserver")
wspace     = create_workspace(cat)
data_store = create_ds(cat, wspace, 'ds_' + name_prefix, dbname)
layer      = create_postgis_layer(cat, wspace, data_store, layer_name, srs,
                                  bounds, native_crs, log)

