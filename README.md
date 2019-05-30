# SpawnpointClusterTool
This tool is used to take a list of coordinates (spawnpoints) and output the center location that covers 3 or more points. This project is written in Python and based on the spawnpoint functionality used in the RocketMap spawnpoint routing functions.

# Get Started With Python
This script was written with Python2.7 in mind. Use the Py3 branch for Python3.6.

To get started using the python script, you can download the files or `git clone` this repository branch.

Create a coordinates file of your spawnpoint coordinates that include latitude and longitude separated by a comma, one pair per line. Below are a few SQL commands to give you an idea of what to export:

A) You can export all spawnpoints if you do not have a big split-up area and want to optimize spawnpoint checking.
```SQL
SELECT lat AS latitude, lon AS longitude
FROM spawnpoint;
```

B) You can export all spawnpoints that do not have a despawn timer so you can complete those.
```SQL
SELECT lat AS latitude, lon AS longitude
FROM spawnpoint 
WHERE despawn_sec = NULL;
```

C) You can export all spawnpoints within a geofence to split-up your routes with optimized spawnpoint locations. Replace the coordinates inside the POLYGON with your geofence information.
```SQL
SELECT lat AS latitude, lon AS longitude
FROM spawnpoint 
WHERE ST_CONTAINS(ST_GEOMFROMTEXT('POLYGON((
33.12 18.24,
33.13 18.25,
33.14 18.26,
33.15 18.27
))'), point(spawnpoint.lat, spawnpoint.lon));
```

D) You can export all spawnpoints within a geofence that do not have a despawn timer to gather specifc TTH. Replace the coordinates inside the POLYGON with your geofence information.
```SQL
SELECT lat AS latitude, lon AS longitude
FROM spawnpoint 
WHERE despawn_sec = NULL AND ST_CONTAINS(ST_GEOMFROMTEXT('POLYGON((
33.12 18.24,
33.13 18.25,
33.14 18.26,
33.15 18.27
))'), point(spawnpoint.lat, spawnpoint.lon));
```

Once you have the files on your system you can run the command `python cluster.py infile.txt` to to have it evaluate the coordinates and output them to outfile.txt. Use the `--help` flag to see the avaliable flags, which are also below:

- 'filename', This is not a flag but the name of the input file.
- '-oc', '--output-clusters', The filename to write cluster data to (defaults to outfile.txt).
- '-r', '--radius', type=float, Maximum radius (in meters) where spawnpoints are considered close (defaults to 70).
- '-ms', '--min-spawnpoints', The minimum amount of spawnpoints to include in clusters that are written out (defaults to 3).

## Notes
This has been tested on Ubuntu 18.04. 

