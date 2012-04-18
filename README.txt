
********************************************READ ME FILE********************************************

File Date: April 17, 2012
File Name: arcmap2psql2geoserver
File Version: 1.0

Software Name: sshPostGIS 
Version: 1.0

System Prerequisites: ArcGIS 10 or above (therefore Windows XP and above), *GeoServer, PostGIS

*If geoserver and postgres are not installed, 
the latest versions can be obtained here: http://workshops.opengeo.org/stack-intro/install-suite.html

Installation Notes:
1. Unzip the file
2. Open up ArcMap, go to the Catalog, right click and add toolbox by locating it where it is stored.
3. Upon adding toolbox, right click the sshTool3 and navigate to properties and click the source tab, 
and change the script file source to where it is located.
4. Click apply and ok. 

Features: 
Facilitates the transferring of a shapefile from a PostGIS database to a GeoServer

Known Issues:
 
How to Use:
Click the script tool and fill in accordingly the fields dealing with ArcMap first, then PostGis, and finally GeoServer. 

featLayer-a shapefile currently open within the table of contents or what is known as a layer panel 
Note: 
Make sure to only input shapefiles, or else the dialog progress screen will state an improper input message. 
Make sure shapefiles are a maximum of 12 characters, start with a letter, and alphanumeric. 
Feature classes will be incompatible

server-where the current connection between the PostGis database will be facilitated. 
Note: 
This is generally done via localhost, 
however it may also be done via the web interface of PostGis though modifications will be needed.

portnumber- directly related to the server if localhost should be used.

database- the name that will be referred to containing the layer within the PostGis database. 
Note: be sure not to start this off with a number or anything non alphabetical 

user && password- the necessary security credentials for the PostGis database

base_url-the url for geoserver
Note: may be localhost with the portnumber specified from depending on Tomcat configurations
Generally 8080 or the geoserver web interface.

gs_user-the username for the geoserver

gs_password-the password for the geoserver

workspace-the workspace for the geoserver
namespace-the namespace for the geoserver
Note: generally a url web presence of that shapefile, i.e. where it was obtained, etc. 
datastore-the datastore name for the shapefile