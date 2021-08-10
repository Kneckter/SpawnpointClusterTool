# SpawnpointClusterTool
This tool is used to take a list of coordinates (spawnpoints, gyms, pokestops, etc.) and output the center location that covers a configurable amount of points. 
It checks for the max cluster and works its way backwards to the smallest allowed cluster to ensure the best coverage.
The output will also be sorted using the Greedy TSP formula.

# Get Started With Python
This script was written with Python3.6.

To get started using the python script, you can download the files or `git clone https://github.com/Kneckter/SpawnpointClusterTool` this repository.

You will need a few Python3 modules to run this script so run this command: `sudo -H pip3 install -U configargparse==0.14.0 peewee==3.9.6 matplotlib==3.1.1 PyMySQL==0.9.3 geopy==1.20.0 s2sphere==0.2.5`

You do not need to create lists of coordinate pairs, this tool has settings to connect to your database and read a geofence that is part of a questing instance. 
Make a copy of the `config.ini.example` and rename it as `config.ini`. Fill in the database settings for your RDM database.

Review the other options in the config file. All options in the config file can be passed on the command line, which can be viewed with the `-h` or `--help` flags.

```
Database Settings
'--db-name' - 'Name of the database to be used (required).'
'--db-user' - 'Username for the database (required).'
'--db-pass' - 'Password for the database (required).'
'--db-host' - 'IP or hostname for the database (defaults to 127.0.0.1).'
'--db-port' - 'Port for the database (defaults to 3306).'

General Settings
'-cf', '--config' - 'Set configuration file (defaults to ./config.ini).'
'-geo', '--geofence' - 'The name of the RDM quest instance to use as a geofence (required).'
'-of', '--output' - 'The base filename without extension to write cluster data to (defaults to outfile.txt).'

Spawnpoint Settings
'-sp', '--spawnpoints' - 'Have spawnpoints included in cluster search (defaults to false).'
'-r', '--radius' - 'Maximum radius (in meters) where spawnpoints are considered close (defaults to 70).'
'-ms', '--min' - 'The minimum amount of spawnpoints to include in clusters that are written out (defaults to 3).'
'-ct', '--timers' - 'Choose whether to use confirmed spawn timers (yes), use unconfirmed timers (no), or all timers (all) (defaults to all).'
'-lu', '--lastupdated' - 'Only use spawnpoints that were last updated in x days. Use 0 to disable this option (defaults to 0).'

Pokestop and Gym Settings
'-ps', '--pokestops' - 'Have pokestops included in the cluster search (defaults to false).'
'-gym', '--gyms' - 'Have gyms included in the cluster search (defaults to false).'
'-mr', '--minraid' - 'The minimum amount of gyms or pokestops to include in clusters that are written out (defaults to 1).'
'-rr', '--raidradius' - 'Maximum radius (in meters) where gyms or pokestops are considered close (defaults to 500).'

S2Cell Settings
**Still a WIP**
'-s2c', '--s2cells' - 'Have the S2Cells included in the cluster search (defaults to false).'
'-s2l', '--s2level' - 'Specify the level for the S2Cell (defaults to 15).'
'-s2m', '--s2min' - 'The minimum amount of S2Cell centers to include in clusters that are written out (defaults to 1).'
'-s2r', '--s2radius' - 'Maximum radius (in meters) where S2Cell centers are considered close (defaults to 500).'

IV List Settings
No cluster options will be recognized for the below options.
'-giv', '--genivlist' - 'Skip all the normal functionality and just generate an IV list using RDM data (defaults to false).'
'-mp', '--maxpoke' - 'The maximum number to be used for the end of the IV list (defaults to 890).'
'--excludepoke' - 'List of Pokemon to exclude from the IV list. Specified as Pokemon ID. Use this only in the config file (defaults to none).'
'-d', '--days' - 'Only include data from x days in the IV list's query. 0 for today, 1 for yesterday & today, etc. (defaults to 7).'

Create Circles Settings
Creates a list of lat,lon. Recognizes options General Settings. Sorting should be disabled.
'-cc', '--circle' - 'Create circles from a geofence instance. Requires -geo <name>. (defaults to false).'
'-ccr', '--ccradius' - 'Maximum radius (in meters) for the circle sizes (defaults to 70).'

Just Sorting
No other options will be recognized for the below options.
'-js', '--justsort' - 'Sorts the points in the given text file of lat,lon coordinates (defaults to false).'
'-jsf', '--justsortfile' - 'Specifies the file to be sorted (defaults to infile).'

Sort Settings
'-ns', '--nosort' - 'Do not sort the output from the search (defaults to false).'
'-spt', '--startpt' - 'Specify the line index as an int of the coordinate you want TSP to keep as the starting point (defaults to None).'
'-fpt', '--finishpt' - 'Specify the line index as an int of the coordinate you want TSP to keep as the finishing point (defaults to None).'
```

You must specify an instance to use in the `geofence` parameter so the script can search for it. Instances with multiple geofences are acceptable. The script will read and apply each geofence to the query.

If searching for clusters, you must choose to include either spawnpoints, gyms, or pokestops for the query.

Once you have the config file on your system you can run the command `python3 cluster.py` to to have it evaluate the coordinates, sort them by TSP, and output them to outfile file.

## Notes
This has been tested on Ubuntu 18.04. 

Thanks to https://github.com/dmishin/tsp-solver for the original TSP code. We have diverged slightly since then.
