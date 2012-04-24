
********************************************READ ME FILE********************************************

File Date: April 17, 2012
File Name: arcmap2psql2geoserver
File Version: 1.0

Software Name: sshPostGIS 
Version: 1.0

System Prerequisites: ArcGIS 10 or above (therefore Windows XP and above), *GeoServer, PostGIS

*If geoserver and postgres are not installed, 
the latest versions can be obtained here: http://workshops.opengeo.org/stack-intro/install-suite.html
Note*: If using tomcat6 for geoserver through a virtual machine there is a chance of assertion error 500, 
so if possible install the geoserver binary over utilizing it from a virtual machine, or else HTTP errors might occur. 

Installation Instructions:
1. Unzip the file
2. Open up ArcMap, go to the Catalog, right click and add toolbox by locating it where it is stored.
3. Upon adding toolbox, right click the sshPostGIS_script and navigate to properties and click the source tab, 
and change the script file source to where it is located.
4. Click apply and ok. 

Features: 
Facilitates the transferring of a shapefile from a PostGIS database to a GeoServer

Known Issues:
 
How to Use:
Click the script tool and fill in accordingly the fields dealing with ArcMap first, then PostGis, and finally GeoServer. 

Shapefile-a shapefile currently open within the table of contents or what is known as a layer panel 
Note: 
Make sure to only input shapefiles, or else the dialog progress screen will state an improper input message. 
Make sure shapefiles are a maximum of 12 characters, start with a letter, and alphanumeric. 
Feature classes will be incompatible

Server-where the current connection between the PostGis database will be facilitated. 
Note: 
This is generally done via localhost, 
however it may also be done via the web interface of PostGis though modifications will be needed.

Port Number- directly related to the server if localhost should be used; i.e. the number associated with 
where Postgres processes will be performed in relation to the tool.

Database- the name that will be referred to containing the layer within the PostGis database. 
Note: be sure not to start this off with a number or anything non alphabetical 

User && Password- the necessary security credentials for the PostGis database

Base URL-the url for geoserver
Note: may be localhost with the portnumber specified from depending on Tomcat configurations
Generally 8080 or the geoserver web interface.

Geoserver User-the username for the geoserver

Geoserver Password-the password for the geoserver

Workspace-the workspace for the geoserver
Namespace-the namespace for the geoserver
Note: generally a url web presence of that shapefile, i.e. where it was obtained, etc. 
Datastore-the datastore name for the shapefile

Troubleshooting: 
TBD