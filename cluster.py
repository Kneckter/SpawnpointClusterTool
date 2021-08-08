import configargparse,time,sys,os,peewee,json,numpy,matplotlib,geopy,s2sphere,multiprocessing
from math import radians, sin, cos, acos, sqrt
from tsp_solver import solve_tsp
from geopy import distance
from matplotlib.path import Path
from multiprocessing.managers import BaseManager, SyncManager

manager = SyncManager()

def pointDistance(pos1, pos2):
    R = 6378137.0
    if pos1 == pos2:
        return 0.0

    lat1 = radians(pos1[0])
    lon1 = radians(pos1[1])
    lat2 = radians(pos2[0])
    lon2 = radians(pos2[1])

    a = sin(lat1) * sin(lat2) + cos(lat1) * cos(lat2) * cos(lon2 - lon1)

    if a > 1:
        return 0.0

    return acos(a) * R
    
def cluster(points, radius, maxClusterList, ms):
    if len(maxClusterList) > 0:
        ii = 0
        while ii < len(points):
            for cluster in maxClusterList:
                dist = pointDistance(cluster, points[ii])
                if dist <= radius:
                    points.remove(points[ii])
                    ii=ii-1
                    break
            ii=ii+1
    global mpPoints, mpRadius, clustersList, mpMS
    mpPoints = points
    mpRadius = radius
    mpMS = ms
    clustersList = manager.list()
    pool = multiprocessing.Pool(processes=len(os.sched_getaffinity(0)))
    pool.map(getMpPoints, points)
    staticClustersList = clustersList._getvalue()
    pool.map(rmSmallClusters, staticClustersList)
    if len(clustersList) > 0:
        maxCluster = max(clustersList, key=len)
        print("The max cluster seen was {}.".format(len(maxCluster)-1))
        done = 0
    else:
        print("There were no clusters found that fit the minimal cluster: {}.".format(ms))
        done = 1
    clustersList = clustersList._getvalue()
    while len(clustersList) > 0 and done == 0:
        start_time = time.time()
#        print(len(clustersList))
        longestList = max(clustersList, key=len)
        if len(longestList)-1 >= ms and len(longestList)-1 > 0:
            clustersList.remove(longestList)
            for item in longestList:
                if type(item[0]) is str:
                    maxClusterList.append(item[1])
                else:
                    rmLongestList(item, ms)
#                    staticClustersList = clustersList._getvalue()
#                    for cluster in staticClustersList:
#                        cluster.append(item)
#                    pool.map(rmMpLongestList, staticClustersList)
        else:
            done = 1
#        print('Completed one cluster in {} seconds.\n'.format(time.time() - start_time))

    pool.close()
    pool.join()
    return maxClusterList

def getMpPoints(point):
    global clustersList, mpPoints
    ii = 0
    pointsList = []
    while ii < len(mpPoints):
        dist = pointDistance(mpPoints[ii], point)
        if dist <= mpRadius:
            pointsList.append(mpPoints[ii])
        if dist == 0.0:
            pointsList.append(tuple(("center",mpPoints[ii])))
        ii=ii+1
    clustersList.append(pointsList)

def rmSmallClusters(cluster):
    global clustersList
    if len(cluster)-1 < mpMS:
        clustersList.remove(cluster)

def rmMpLongestList(cluster):
    global clustersList
    item = cluster.pop()
    if len(cluster)-1 < mpMS:
        clustersList.remove(cluster)
    else:
        for cpoint in cluster:
            if type(cpoint[0]) is not str and item == cpoint:
                clustersList.remove(cluster)
                cluster.remove(cpoint)
                clustersList.append(cluster)
                break

def rmLongestList(item, ms):
    global clustersList
    for cluster in clustersList:
        if len(cluster)-1 < ms:
            clustersList.remove(cluster)
        else:
            for cpoint in cluster:
                if type(cpoint[0]) is not str and item == cpoint:
                    cluster.remove(cpoint)
                    break

def getInstance(db):
    with db:
        cmd_sql = '''
            SELECT type
            FROM instance
            WHERE name = '%s';
            ''' % args.geofence
        inttype = db.execute_sql(cmd_sql)
        inttypesql = inttype.fetchone()

        try:
            datajson = inttypesql[0] # Get the first item in the tuple and convert it to json
        except:
            print('No instance found with name {}.'.format(args.geofence))
            sys.exit(1)

        if inttypesql[0] == 'auto_quest' or  inttypesql[0] == 'pokemon_iv':
            cmd_sql = '''
                SELECT data
                FROM instance
                WHERE name = '%s';
                ''' % args.geofence
            instance = db.execute_sql(cmd_sql)
            return instance
        else:
            print('{} is not a geofence instance (quest or IV).'.format(args.geofence))
            sys.exit(1)

def getPoints(geofences, db, args):
    scmd_sql=''
    pcmd_sql=''
    gcmd_sql=''
    j=1

    if args.spawnpoints:
        scmd_sql = '''
            SELECT lat,lon
            FROM spawnpoint
            WHERE
            '''
        if args.timers == 'yes':
            scmd_sql = scmd_sql + ' despawn_sec IS NOT NULL AND '
        elif args.timers == 'no':
            scmd_sql = scmd_sql + ' despawn_sec IS NULL AND '
        elif args.timers == 'all':
            # No change needed
            scmd_sql = scmd_sql
        elif args.timers != 'yes' or args.timers != 'no' or args.timers != 'all':
            print('{} is not a valid argument for --timers'.format(args.timers))
            sys.exit(1)

        if args.lastupdated > 0:
            updatetimer = time.time() - (args.lastupdated * 3600 * 24)
            scmd_sql = scmd_sql + ' updated > %s AND ' % updatetimer

        scmd_sql = scmd_sql + ' ('

    if args.pokestops:
        pcmd_sql = '''
            SELECT lat,lon
            FROM pokestop
            WHERE (
            '''

    if args.gyms:
        gcmd_sql = '''
            SELECT lat,lon
            FROM gym
            WHERE (
            '''

    for g in geofences:
    # Loop through the geofences
        numcoords = len(g) # Get the number of coordinates in this geofence
        i=1
        coordstr=''
        for c in g:
            # Loop through the coordinates in each geofence and build the string for the query
            if i < numcoords:
                coord = str(c['lat'])+' '+str(c['lon'])+',\n'
                i=i+1
            else:
                coord = str(c['lat'])+' '+str(c['lon'])
            coordstr = coordstr + coord

        if j == 1:
            coord_sql = '''
                ST_CONTAINS(
                ST_GEOMFROMTEXT('POLYGON((
                %s
                ''' % coordstr
            j=j+1
        else:
            coord_sql = '''
                OR ST_CONTAINS(
                ST_GEOMFROMTEXT('POLYGON((
                %s
                ''' % coordstr

        scmd_sql = scmd_sql + coord_sql + "))'), point(spawnpoint.lat, spawnpoint.lon)) "
        pcmd_sql = pcmd_sql + coord_sql + "))'), point(pokestop.lat, pokestop.lon)) "
        gcmd_sql = gcmd_sql + coord_sql + "))'), point(gym.lat, gym.lon)) "

    scmd_sql = scmd_sql + ");"
    pcmd_sql = pcmd_sql + ");"
    gcmd_sql = gcmd_sql + ");"

    try:
        spawnpointssql = db.execute_sql(scmd_sql)
    except:
        spawnpointssql=''
        if args.spawnpoints:
            print('Failed to execute query for spawnpoints')

    try:
        pokestoppointssql = db.execute_sql(pcmd_sql)
    except:
        pokestoppointssql=''
        if args.pokestops:
            print('Failed to execute query for pokestops')

    try:
        gympointssql = db.execute_sql(gcmd_sql)
    except:
        gympointssql=''
        if args.gyms:
            print('Failed to execute query for gyms')

    return spawnpointssql,pokestoppointssql,gympointssql

def tspsolver(filename, args):
    tsppoints = []
    rows = ''

    # Read everything from the file and put it in a list
    with (open(filename,'rU')) as f:
        for line in f:
            line = line.rstrip('\n')
            (lat,lon) = [numpy.float64(x) for x in line.split(',')]
            tsppoints.append((lat,lon))

    # Create a matrix and fill it with distances based on all the possible combinations
    D = numpy.zeros((len(tsppoints),len(tsppoints)))
    for i in range(len(tsppoints)):
        for j in range(len(tsppoints)):
            D[i][j]=numpy.linalg.norm(numpy.subtract(tsppoints[i],tsppoints[j]))

    # Apply the greedy TSP to the distances and return a list of indices
    tour = solve_tsp(D, startpt = args.startpt, finishpt=args.finishpt)

    # Write everything to the file based on the indices
    f = open(filename, 'w')
    for i in tour:
        rows = tsppoints[i][0].astype(str) + ',' + tsppoints[i][1].astype(str) + '\n'
        f.write(str(rows))
    f.close()

def get_new_coords(init_loc, distance, bearing):
    origin = geopy.Point(init_loc[0], init_loc[1])
    destination = geopy.distance.distance(kilometers=distance).destination(origin, bearing)
    return (destination.latitude, destination.longitude)

def get_geofenced_coordinates(coordinates, geofenced_areas, step_distance):
    print('Found {} circles that cover the geofenced area. Removing the ones outside the geofence...\n'.format(len(coordinates)))
    geofenced_coordinates = []
    for c in coordinates:
        # Coordinate is geofenced if in one geofenced area.
        if in_area(c, geofenced_areas):
            geofenced_coordinates.append(c)
        else:
            # Do a check if the radius is in the geofence even if the center is not
            for i in range(0, 6):
                star_loc = get_new_coords(c, step_distance, 90 + 60 * i)
                if in_area(star_loc, geofenced_areas):
                    geofenced_coordinates.append(c)
                    break

    return geofenced_coordinates

def in_area(coordinate, area):
    point = {'lat': coordinate[0], 'lon': coordinate[1]}
    polygon = area
    pointTuple = (point['lat'], point['lon'])
    polygonTupleList = []
    for c in polygon:
        coordinateTuple = (c['lat'], c['lon'])
        polygonTupleList.append(coordinateTuple)

    polygonTupleList.append(polygonTupleList[0])
    path = Path(polygonTupleList)
    return path.contains_point(pointTuple)

def main(args):
    mspoints = []
    filename = str(args.output)

    print('Connecting to MySQL database {} on {}:{}...\n'.format(args.db_name, args.db_host, args.db_port))
    db = peewee.MySQLDatabase(
        args.db_name,
        user=args.db_user,
        password=args.db_pass,
        host=args.db_host,
        port=args.db_port,
        charset='utf8mb4')
    db.connect()
    start_time = time.time()

    # Get the instance from args and query the DB for spawnpoints
    instance = getInstance(db)
    instancesql = instance.fetchone() # Get the first row in the cursor object
    try:
        datajson = json.loads(instancesql[0]) # Get the first item in the tuple and convert it to json
    except:
        print('No data was returned for the instance name {}.'.format(args.geofence))
        sys.exit(1)

    geofences = datajson['area'] # Get the geofence(s) from the json
    for fence in geofences:
        firstpt = fence[0]
        lastpt = fence[len(fence)-1]
        if firstpt != lastpt:
            fence.append(firstpt)
            print('Updated last point in geofence to match the first point')
    print('Gatherng points from {} geofence(s)...\n'.format(len(geofences)))

    spawnpointssql,pokestoppointssql,gympointssql = getPoints(geofences, db, args)
    manager.start()

    if args.spawnpoints:
        points = spawnpointssql.fetchall()

        rows = []
        for p in points:
            if p not in rows:
                rows.append(p)

        print('Processing', len(rows), 'spawnpoints...')
        clusters = cluster(rows, args.radius, [], args.min)

        rowcount = 0
        f = open(filename, 'w')

        for c in clusters:
            mspoints.append(c)
            f.write(str(str(c[0]) + ',' + str(c[1]) +'\n'))
            rowcount += 1
        f.close()
        print('{} clusters with {} or more spawnpoints in them.\n'.format(rowcount, args.min))

    if args.pokestops:
        points = pokestoppointssql.fetchall()

        rows = []
        for p in points:
            if p not in rows:
                rows.append(p)

        print('Processing', len(rows), 'pokestops...')
        clusters = cluster(rows, args.raidradius, mspoints, args.minraid)

        mspoints = []
        rowcount = 0
        f = open(filename, 'w')

        for c in clusters:
            mspoints.append(c)
            f.write(str(str(c[0]) + ',' + str(c[1]) +'\n'))
            rowcount += 1
        f.close()
        if args.spawnpoints:
            print('{} clusters with {} or more spawnpoints and {} or more pokestops in them.\n'.format(rowcount, args.min, args.minraid))
        else:
            print('{} clusters with {} or more pokestops in them.\n'.format(rowcount, args.minraid))

    if args.gyms:
        points = gympointssql.fetchall()

        rows = []
        for p in points:
            if p not in rows:
                rows.append(p)

        print('Processing', len(rows), 'gyms...')
        clusters = cluster(rows, args.raidradius, mspoints, args.minraid)

        mspoints = []
        rowcount = 0
        f = open(filename, 'w')

        for c in clusters:
            mspoints.append(c)
            f.write(str(str(c[0]) + ',' + str(c[1]) +'\n'))
            rowcount += 1
        f.close()
        if args.spawnpoints and args.pokestops:
            print('{} clusters with {} or more spawnpoints, {} or more pokestops, and {} or more gyms in them.\n'.format(rowcount, args.min, args.minraid, args.minraid))
        elif args.spawnpoints:
            print('{} clusters with {} or more spawnpoints and {} or more gyms in them.\n'.format(rowcount, args.min, args.minraid))
        elif args.pokestops:
            print('{} clusters with {} or more pokestops and gyms in them.\n'.format(rowcount, args.minraid))
        else:
            print('{} clusters with {} or more gyms in them.\n'.format(rowcount, args.minraid))

    if args.s2cells:
        #points = gympointssql.fetchall()
        points = s2cellpoints(geofences, args)

        print('Processing', len(points), 'S2Cells...')
        clusters = cluster(points, args.s2radius, mspoints, args.s2min)

        rowcount = 0
        f = open(filename, 'w')

        for c in clusters:
            f.write(str(str(c[0]) + ',' + str(c[1]) +'\n'))
            rowcount += 1
        f.close()
        if args.spawnpoints and args.pokestops and args.gyms:
            print('{} clusters with {} or more spawnpoints, {} or more pokestops, {} or more gyms, and {} or more S2Cells in them.\n'.format(rowcount, args.min, args.minraid, args.minraid, args.s2min))
        elif args.spawnpoints and args.pokestops:
            print('{} clusters with {} or more spawnpoints, {} or more pokestops, and {} or more S2Cells in them.\n'.format(rowcount, args.min, args.minraid, args.s2min))
        elif args.spawnpoints and args.gyms:
            print('{} clusters with {} or more spawnpoints, {} or more gyms, and {} or more S2Cells in them.\n'.format(rowcount, args.min, args.minraid, args.s2min))
        elif args.pokestops and args.gyms:
            print('{} clusters with {} or more pokestops, {} or more gyms, and {} or more S2Cells in them.\n'.format(rowcount, args.minraid, args.minraid, args.s2min))
        elif args.spawnpoints:
            print('{} clusters with {} or more spawnpoints and {} or more S2Cells in them.\n'.format(rowcount, args.min, args.s2min))
        elif args.pokestops:
            print('{} clusters with {} or more pokestops and {} or S2Cells in them.\n'.format(rowcount, args.minraid, args.s2min))
        elif args.gyms:
            print('{} clusters with {} or more gyms and {} or S2Cells in them.\n'.format(rowcount, args.minraid, args.s2min))
        else:
            print('{} clusters with {} or more S2Cells in them.\n'.format(rowcount, args.s2min))

    if args.nosort:
        print('Skipping the sort...\n')
    else:
        print('Sorting coordinates...\n')
        try:
            tspsolver(filename, args)
        except:
            print("Could not sort this many coordinates due to your system's limits.\n")

    end_time = time.time()
    print('Coordinates written to the {} file.'.format(filename))
    print('Completed in {:.2f} seconds.\n'.format(end_time - start_time))

    # Done with the geofences, close it down
    db.close()
    print('Database connection closed')

def genivs(args):
    print('Connecting to MySQL database {} on {}:{}...\n'.format(args.db_name, args.db_host, args.db_port))
    db = peewee.MySQLDatabase(
        args.db_name,
        user=args.db_user,
        password=args.db_pass,
        host=args.db_host,
        port=args.db_port,
        charset='utf8mb4')
    db.connect()

    with db:
        date_sql = ' WHERE `date` >= DATE_SUB(CURRENT_DATE(),INTERVAL '+str(args.days)+' DAY) '
        cmd_sql = '''
            SELECT pokemon_id,SUM(`count`) AS `count`
            FROM pokemon_stats
            '''+date_sql+'''
            GROUP BY pokemon_id
            ORDER BY `count` ASC;
            ''' 

        try:
            intlist = db.execute_sql(cmd_sql)
            intlistsql = intlist.fetchall()
            print('{} pokemon found in the pokemon_stats table.\n'.format(len(intlistsql)))
        except:
            print('Querying the pokemon_stats table failed. Exiting...')
            sys.exit(1)

        # Only keep the dex numbers
        datajson = []
        for row in intlistsql:
            datajson.append(row[0])

        # Move Unown to the top of the list
        print('Setting unown to the top of the list.\n')
        if 201 in datajson:
            datajson.remove(201)
        datajson.insert(0,201)

        # Loop through the list to fill in the blanks
        print('Adding missing IDs up to {}.\n'.format(args.maxpoke))
        i = 1
        while i <= args.maxpoke:
            if i not in datajson:
                datajson.insert(1,i)
            i=i+1

        # Loop through and remove the excluded pokemon
        print('Removing IDs: {}.\n'.format(args.excludepoke))
        for idex in args.excludepoke:
            if int(idex) in datajson:
                datajson.remove(int(idex))

        # Write output to a file
        filename = str(args.output)
        f = open(filename, 'w')

        for d in datajson:
            f.write(str(d)+'\n')
        f.close()
        print('IV list written to the {} file.'.format(filename))

def createcircles(args):
    print('Connecting to MySQL database {} on {}:{}...\n'.format(args.db_name, args.db_host, args.db_port))
    db = peewee.MySQLDatabase(
        args.db_name,
        user=args.db_user,
        password=args.db_pass,
        host=args.db_host,
        port=args.db_port,
        charset='utf8mb4')
    db.connect()

    # Get the instance from args and query the DB for spawnpoints
    instance = getInstance(db)
    instancesql = instance.fetchone() # Get the first row in the cursor object
    try:
        datajson = json.loads(instancesql[0]) # Get the first item in the tuple and convert it to json
    except:
        print('No data was returned for the instance name {}.'.format(args.geofence))
        sys.exit(1)

    centroid = []
    maxdistance = []
    i=0
    geofences = datajson['area'] # Get the geofence(s) from the json
    for fence in geofences:
        firstpt = fence[0]
        lastpt = fence[len(fence)-1]
        if firstpt != lastpt:
            fence.append(firstpt)
            print('Updated last point in geofence to match the first point')

        # Calculate the center of the geofences for the starting location
        xpt = [p['lat'] for p in fence]
        ypt = [p['lon'] for p in fence]
        centroid.append((sum(xpt) / len(fence), sum(ypt) / len(fence)))

        # Calculate the max distance from the edge so we can set the step limit
        maxdistance.append(0)
        for p in fence:
            dist = geopy.distance.vincenty(centroid[i], (p['lat'],p['lon'])).m
            if dist > maxdistance[i]:
                maxdistance[i] = dist
        i=i+1
    print('Generating {}m circles for {} geofence(s)...\n'. format(args.ccradius, len(geofences)))

    start_time = time.time()

    # Process each geofence separately so we can reduce overlap
    endresults = []
    numresults = 0
    ii=0
    for fence in geofences:
        # dist between column centers
        step_distance = args.ccradius/1000
        step_limit = int((maxdistance[ii]/args.ccradius)+1) # A step is "(step_limit * step_distance) + step_distance/2". Each step basically adds a layer of 70m points to the calculation
        scan_location = centroid[ii] # This is the center of each geofence
        ii=ii+1

        xdist = sqrt(3) * step_distance

        results = []
        loc = scan_location
        results.append((loc[0], loc[1]))
        # This will loop thorugh all the rings in the hex from the centre
        # moving outwards
        for ring in range(1, step_limit):
            for i in range(0, 6):
                # star_locs will contain the locations of the 6 vertices of
                # the current ring (90,150,210,270,330 and 30 degrees from
                # origin) to form a star
                star_loc = get_new_coords(scan_location, xdist * ring, 90 + 60 * i)
                for j in range(0, ring):
                    # Then from each point on the star, create locations
                    # towards the next point of star along the edge of the
                    # current ring
                    loc = get_new_coords(star_loc, xdist * (j), 210 + 60 * i)
                    results.append((loc[0], loc[1]))

        numresults = numresults + len(results)
        endresults.append(get_geofenced_coordinates(results, fence, step_distance))

    #write to the file. They should already be sorted
    rows = ''
    rowcount = 0
    filename = str(args.output)
    f = open(filename, 'w')

    for r in endresults:
        for c in r:
            rows = str(str(c[0]) + ',' + str(c[1]) +'\n')
            f.write(str(rows))
            rowcount += 1
    f.close()

    if args.nosort:
        print('{} circles checked and {} circles with a {}m radius found in geofence(s). Skipping the sort...\n'.format(numresults, rowcount, args.ccradius))
    else:
        print('{} circles checked and {} circles with a {}m radius found in geofence(s). Sorting coordinates...\n'.format(numresults, rowcount, args.ccradius))
        try:
            tspsolver(filename, args)
        except:
            print("Could not sort this many coordinates due to your system's limits.\n")

    end_time = time.time()
    print('Circle coordinates written to the {} file.'.format(filename))
    print('Completed in {:.2f} seconds.\n'.format(end_time - start_time))

    # Done with the geofences, close it down
    db.close()
    print('Database connection closed')

def s2cellpoints(geofences, args):
    coordinates = []
    points = []
    levels = {0: 7842000,1: 5004000,2: 2489000,3: 1310000,4: 636000,
              5: 315000,6: 156000,7: 78000,8: 39000,9: 20000,
              10: 10000,11: 5000,12: 2000,13: 1225,14: 613,
              15: 306,16: 153,17: 77,18: 38,19: 19,
              20: 10,21: 5,22: 2,23: 1.2,24: 0.6,
              25: 0.3,26: 0.15,27: 0.07,28: 0.04,29: 0.018,30: 0.009}
    # Calc the step
    step_distance = (levels[args.s2level]/2)/1000

    for geofence in geofences:
        # Get the max and min lats
        seq = [x['lat'] for x in geofence]
        lowLat = min(seq)
        hiLat = max(seq)
        # Get the max and min lons
        seq = [x['lon'] for x in geofence]
        lowLon = min(seq)
        hiLon = max(seq)

        r = s2sphere.RegionCoverer()
        r.min_level = args.s2level
        r.max_level = args.s2level
        p1 = s2sphere.LatLng.from_degrees(lowLat, hiLon)
        p2 = s2sphere.LatLng.from_degrees(hiLat, lowLon)
        cell_ids = r.get_covering(s2sphere.LatLngRect.from_point_pair(p1, p2))

        for cell_id in cell_ids:
            center = cell_id.to_lat_lng()
            coordinates.append((float(center.lat().degrees), float(center.lng().degrees)))
        for point in get_geofenced_coordinates(coordinates, geofence, step_distance):
            if point not in points:
                points.append(point)
    return points

if __name__ == "__main__":

    defaultconfigfiles = []
    if '-cf' not in sys.argv and '--config' not in sys.argv:
        defaultconfigfiles = [os.getenv('servAP_CONFIG', os.path.join(os.path.dirname(__file__), './config.ini'))]

    parser = configargparse.ArgParser(default_config_files=defaultconfigfiles,auto_env_var_prefix='servAP_',description='Cluster coordinate pairs that are close together.')

    dbsets = parser.add_argument_group('Database')
    dbsets.add_argument('--db-name', help='Name of the database to be used (required).', required=True)
    dbsets.add_argument('--db-user', help='Username for the database (required).', required=True)
    dbsets.add_argument('--db-pass', help='Password for the database (required).', required=True)
    dbsets.add_argument('--db-host', help='IP or hostname for the database (defaults to 127.0.0.1).', default='127.0.0.1')
    dbsets.add_argument('--db-port', help='Port for the database (defaults to 3306).', type=int, default=3306)

    gensets = parser.add_argument_group('General Settings')
    gensets.add_argument('-cf', '--config', is_config_file=True, help='Set configuration file (defaults to ./config.ini).')
    gensets.add_argument('-geo', '--geofence', help='The name of the RDM quest instance to use as a geofence (required).')
    gensets.add_argument('-of', '--output', help='The base filename without extension to write cluster data to (defaults to outfile.txt).', default='outfile.txt')

    spawns = parser.add_argument_group('Spawnpoints')
    spawns.add_argument('-sp', '--spawnpoints', help='Have spawnpoints included in cluster search (defaults to false).', action='store_true', default=False)
    spawns.add_argument('-r', '--radius', type=float, help='Maximum radius (in meters) where spawnpoints are considered close (defaults to 70).', default=70)
    spawns.add_argument('-ms', '--min', type=int, help='The minimum amount of spawnpoints to include in clusters that are written out (defaults to 3).', default=3)
    spawns.add_argument('-ct', '--timers', help='Choose whether to use confirmed spawn timers (yes), use unconfirmed timers (no), or all timers (all) (defaults to all).', default='all')
    spawns.add_argument('-lu', '--lastupdated', type=float, help='Only use spawnpoints that were last updated in x days. Use 0 to disable this option (defaults to 0).', default=0)

    sng = parser.add_argument_group('Stops and Gyms')
    sng.add_argument('-ps', '--pokestops', help='Have pokestops included in the cluster search (defaults to false).', action='store_true', default=False)
    sng.add_argument('-gym', '--gyms', help='Have gyms included in the cluster search (defaults to false).', action='store_true', default=False)
    sng.add_argument('-mr', '--minraid', type=int, help='The minimum amount of gyms or pokestops to include in clusters that are written out (defaults to 1).', default=1)
    sng.add_argument('-rr', '--raidradius', type=float, help='Maximum radius (in meters) where gyms or pokestops are considered close (defaults to 500).', default=500)

    s2c = parser.add_argument_group('S2Cells',description='**Still a WIP**')
    s2c.add_argument('-s2c', '--s2cells', help='Have the S2Cells included in the cluster search (defaults to false).', action='store_true', default=False)
    s2c.add_argument('-s2l', '--s2level', type=float, help='Specify the level for the S2Cell (defaults to 15).', default=15)
    s2c.add_argument('-s2m', '--s2min', type=int, help='The minimum amount of S2Cell centers to include in clusters that are written out (defaults to 1).', default=1)
    s2c.add_argument('-s2r', '--s2radius', type=float, help='Maximum radius (in meters) where S2Cell centers are considered close (defaults to 500).', default=500)

    ivl = parser.add_argument_group('IV List',description='No cluster options will be recognized for the below options.')
    ivl.add_argument('-giv', '--genivlist', help='Skip all the normal functionality and just generate an IV list using RDM data (defaults to false).', action='store_true', default=False)
    ivl.add_argument('-mp', '--maxpoke', type=int, help='The maximum number to be used for the end of the IV list (defaults to 809).', default=809)
    ivl.add_argument('--excludepoke', help=('List of Pokemon to exclude from the IV list. Specified as Pokemon ID. Use this only in the config file (defaults to none).'), action='append', default=[])
    ivl.add_argument('-d', '--days', help='Only include data from x days in the IV list\'s query. 0 for today, 1 for yesterday & today, etc. (defaults to 7).', default=7)

    cc = parser.add_argument_group('Create Circles',description='Creates a list of lat,lon. Recognizes options General Settings. Sorting should be disabled.')
    cc.add_argument('-cc', '--circle', help='Create circles from a geofence instance. Requires -geo <name>. (defaults to false).', action='store_true', default=False)
    cc.add_argument('-ccr', '--ccradius', type=float, help='Maximum radius (in meters) for the circle sizes (defaults to 70).', default=70)

    js = parser.add_argument_group('Sorting',description='No other options will be recognized for the below options.')
    js.add_argument('-js', '--justsort', help='Sorts the points in the given text file of lat,lon coordinates (defaults to false).', action='store_true', default=False)
    js.add_argument('-jsf', '--justsortfile', help='Specifies the file to be sorted (defaults to infile).', default='infile')

    sort = parser.add_argument_group('Sort Settings')
    sort.add_argument('-ns', '--nosort', help='Do not sort the output from the search (defaults to false).', action='store_true', default=False)
    sort.add_argument('-spt', '--startpt', type=int, help='Specify the line index as an int of the coordinate you want TSP to keep as the starting point (defaults to None).', default=None)
    sort.add_argument('-fpt', '--finishpt', type=int, help='Specify the line index as an int of the coordinate you want TSP to keep as the finishing point (defaults to None).', default=None)

    args = parser.parse_args()

    if args.genivlist:
        genivs(args)
        sys.exit(1)
    if args.justsort:
        print('Sorting coordinates...\n')
        try:
            tspsolver(args.justsortfile, args)
            print("Done!")
        except:
            print("Could not sort this many coordinates due to your system's limits.\n")
        sys.exit(1)
    if not args.geofence:
        print('You must specify a geofence to continue.')
        sys.exit(1)
    if args.circle:
        createcircles(args)
        sys.exit(1)
    if not args.spawnpoints and not args.pokestops and not args.gyms and not args.s2cells:
        print('You must choose to include either spawnpoints, gyms, pokestops, or S2Cells for the query.')
        sys.exit(1)

    main(args)

# Maybe use the RDM API to write to an instance after the coordinates are sorted
# Maybe add a geofence generator. If a geofence is generated, read it from the file to use it for clustering?

# As reported by Hunch. He got this warning with MySQL 5.7
# The warning is probably fine because it doesn't stop the queries.
#   Warning: (3090, "Changing sql mode 'NO_AUTO_CREATE_USER' is deprecated. It will be removed in a future release.")
