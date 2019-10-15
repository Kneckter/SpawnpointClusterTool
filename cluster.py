import configargparse,time,sys,os,peewee,json,numpy,matplotlib
from tsp_solver import solve_tsp
from math import acos, atan2, cos, degrees, radians, sin, sqrt

class utils:
    def distance(pos1, pos2):
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


    def intermediate_point(pos1, pos2, f):
        if pos1 == pos2:
            return pos1

        lat1 = radians(pos1[0])
        lon1 = radians(pos1[1])
        lat2 = radians(pos2[0])
        lon2 = radians(pos2[1])

        a = sin(lat1) * sin(lat2) + cos(lat1) * cos(lat2) * cos(lon2 - lon1)

        if a > 1:  # too close
            return pos1 if f < 0.5 else pos2

        delta = acos(a)

        if delta == 0:  # too close
            return pos1 if f < 0.5 else pos2

        a = sin((1 - f) * delta) / delta
        b = sin(f * delta) / delta
        x = a * cos(lat1) * cos(lon1) + b * cos(lat2) * cos(lon2)
        y = a * cos(lat1) * sin(lon1) + b * cos(lat2) * sin(lon2)
        z = a * sin(lat1) + b * sin(lat2)

        lat3 = atan2(z, sqrt(x**2 + y**2))
        lon3 = atan2(y, x)

        def normalize(pos):
            return ((pos[0] + 540) % 360) - 180, ((pos[1] + 540) % 360) - 180

        return normalize((degrees(lat3), degrees(lon3)))

class Spawnpoint(object):
    def __init__(self, data):
        self.position = (float(data[0]), float(data[1]))

class Spawncluster(object):
    def __init__(self, spawnpoint):
        self._spawnpoints = [spawnpoint]
        self.centroid = spawnpoint.position
    
    def __iter__(self):
        for x in self._spawnpoints:
            yield x
        
    def append(self, spawnpoint):
        # update centroid
        f = len(self._spawnpoints) / (len(self._spawnpoints) + 1.0)
        self.centroid = utils.intermediate_point(spawnpoint.position, self.centroid, f)
        
        self._spawnpoints.append(spawnpoint)
            
    def simulate_centroid(self, spawnpoint):
        f = len(self._spawnpoints) / (len(self._spawnpoints) + 1.0)
        new_centroid = utils.intermediate_point(spawnpoint.position, self.centroid, f)
        
        return new_centroid
            
def check_cluster(spawnpoint, cluster, radius):
    # discard infinite cost or too far away
    if utils.distance(spawnpoint.position, cluster.centroid) > 2 * radius:
        return False

    new_centroid = cluster.simulate_centroid(spawnpoint)
    
    # we'd be removing ourselves
    if utils.distance(spawnpoint.position, new_centroid) > radius:
        return False
    
    # we'd be removing x
    if any(utils.distance(x.position, new_centroid) > radius for x in cluster):
        return False
        
    return True
    
def cluster(spawnpoints, radius, clusters):
    for p in spawnpoints:
        if len(clusters) == 0:
            clusters.append(Spawncluster(p))
        else:
            c = min(clusters, key=lambda x: utils.distance(p.position, x.centroid))

            if check_cluster(p, c, radius):
                c.append(p)
            else:
                c = Spawncluster(p)
                clusters.append(c)

    return clusters

def getInstance(db):
    with db:
        cmd_sql = '''
            SELECT type
            FROM instance
            WHERE name = '%s';
            ''' % args.geofence
        inttype = db.execute_sql(cmd_sql)
        inttypesql = inttype.fetchone()

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
        if args.timers:
            scmd_sql = scmd_sql + ' despawn_sec IS NOT NULL AND '
        if args.lastupdated > 0:
            updatetimer = time.time() - (args.lastupdated * 3600)
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

def tspsolver(filename):
    tsppoints = []
    rows = ''

    with (open(filename,'rU')) as f:
        for line in f:
            line = line.rstrip('\n')
            (lat,lon) = [numpy.float64(x) for x in line.split(',')]
            tsppoints.append((lat,lon))

    tour = [i for i in range(len(tsppoints))]

    D = numpy.zeros((len(tsppoints),len(tsppoints)))
    for i in range(len(tsppoints)):
        for j in range(len(tsppoints)):
            D[i][j]=numpy.linalg.norm(numpy.subtract(tsppoints[i],tsppoints[j]))

    tour = solve_tsp(D)

    f = open(filename, 'w')
    for i in tour:
        rows = tsppoints[i][0].astype(str) + ',' + tsppoints[i][1].astype(str) + '\n'
        f.write(str(rows))
    f.close()

def main(args):
    radius = args.radius
    ms = args.min
    mspoints = []

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

    geofences = datajson['area'] # Get the geofence(s) from the json
    for fence in geofences:
        firstpt = fence[0]
        lastpt = fence[len(fence)-1]
        if firstpt != lastpt:
            fence.append(firstpt)
            print('Updated last point in geofence to match the first point')
    print('Gatherng points from {} geofence(s)...\n'. format(len(geofences)))

    spawnpointssql,pokestoppointssql,gympointssql = getPoints(geofences, db, args)
    start_time = time.time()

    if args.spawnpoints:
        points = spawnpointssql.fetchall()

        rows = []
        for p in points:
            rows.append(p)

        spawnpoints = [Spawnpoint(x) for x in rows]

        print('Processing', len(spawnpoints), 'spawnpoints...')
        clusters = cluster(spawnpoints, radius, [])

        try:
            for c in clusters:
                for p in c:
                    assert utils.distance(p.position, c.centroid) <= radius
        except AssertionError:
            print('error: something\'s seriously broken.')
            raise

        rows = ''
        rowcount = 0
        filename = str(args.output)+'.txt'
        f = open(filename, 'w')

        for c in clusters:
            if len([x for x in c]) >= ms:
                rows = str(str(c.centroid[0]) + ',' + str(c.centroid[1]) +'\n')
                mspoints.append(c)
                f.write(str(rows))
                rowcount += 1
        f.close()
        print('{} clusters with {} or more spawnpoints in them.\n'.format(rowcount, ms))

    if args.pokestops:
        points = pokestoppointssql.fetchall()

        rows = []
        for p in points:
            rows.append(p)

        spawnpoints = [Spawnpoint(x) for x in rows]

        print('Processing', len(spawnpoints), 'pokestops...')
        clusters = cluster(spawnpoints, args.raidradius, mspoints)

        try:
            for c in clusters:
                for p in c:
                    assert utils.distance(p.position, c.centroid) <= args.raidradius
        except AssertionError:
            print('error: something\'s seriously broken.')
            raise

        rows = ''
        mspoints = []
        rowcount = 0
        filename = str(args.output)+'.txt'
        f = open(filename, 'w')

        for c in clusters:
            if len([x for x in c]) >= args.minraid:
                rows = str(str(c.centroid[0]) + ',' + str(c.centroid[1]) +'\n')
                mspoints.append(c)
                f.write(str(rows))
                rowcount += 1
        f.close()
        if args.spawnpoints:
            print('{} clusters with spawnpoints and with {} or more pokestops in them.\n'.format(rowcount, args.minraid))
        else:
            print('{} clusters with {} or more pokestops in them.\n'.format(rowcount, args.minraid))

    if args.gyms:
        points = gympointssql.fetchall()

        rows = []
        for p in points:
            rows.append(p)

        spawnpoints = [Spawnpoint(x) for x in rows]

        print('Processing', len(spawnpoints), 'gyms...')
        clusters = cluster(spawnpoints, args.raidradius, mspoints)

        try:
            for c in clusters:
                for p in c:
                    assert utils.distance(p.position, c.centroid) <= args.raidradius
        except AssertionError:
            print('error: something\'s seriously broken.')
            raise

        rows = ''
        mspoints = []
        rowcount = 0
        filename = str(args.output)+'.txt'
        f = open(filename, 'w')

        for c in clusters:
            if len([x for x in c]) >= args.minraid:
                rows = str(str(c.centroid[0]) + ',' + str(c.centroid[1]) +'\n')
                f.write(str(rows))
                rowcount += 1
        f.close()
        if args.spawnpoints and args.pokestops:
            print('{} clusters with spawnpoints, pokestops, and with {} or more gyms in them.\n'.format(rowcount, args.minraid))
        elif args.spawnpoints:
            print('{} clusters with spawnpoints and with {} or more gyms in them.\n'.format(rowcount, args.minraid))
        elif args.pokestops:
            print('{} clusters with pokestops and with {} or more gyms in them.\n'.format(rowcount, args.minraid))
        else:
            print('{} clusters with more than {} gyms in them.\n'.format(rowcount, args.minraid))

    print('Sorting coordinates...\n')
    tspsolver(filename)

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
        cmd_sql = '''
            SELECT pokemon_id,SUM(`count`) AS `count`
            FROM pokemon_stats
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
        filename = str(args.output)+'.txt'
        f = open(filename, 'w')

        for d in datajson:
            f.write(str(d)+'\n')
        f.close()
        print('IV list written to the {} file.'.format(filename))

if __name__ == "__main__":

    defaultconfigfiles = []
    if '-cf' not in sys.argv and '--config' not in sys.argv:
        defaultconfigfiles = [os.getenv('servAP_CONFIG', os.path.join(os.path.dirname(__file__), './config.ini'))]

    parser = configargparse.ArgParser(default_config_files=defaultconfigfiles,auto_env_var_prefix='servAP_',description='Cluster coordinate pairs that are close together.')

    gensets = parser.add_argument_group('General Settings')
    gensets.add_argument('-cf', '--config', is_config_file=True, help='Set configuration file (defaults to ./config.ini).')
    gensets.add_argument('-of', '--output', help='The base filename without extension to write cluster data to (defaults to outfile).', default='outfile')
    gensets.add_argument('-geo', '--geofence', help='The name of the RDM quest instance to use as a geofence (required).', required=True)

    spawns = parser.add_argument_group('Spawnpoints')
    spawns.add_argument('-sp', '--spawnpoints', help='Have spawnpoints included in cluster search (defaults to false).', action='store_true', default=False)
    spawns.add_argument('-r', '--radius', type=float, help='Maximum radius (in meters) where spawnpoints are considered close (defaults to 70).', default=70)
    spawns.add_argument('-ms', '--min', type=int, help='The minimum amount of spawnpoints to include in clusters that are written out (defaults to 3).', default=3)
    spawns.add_argument('-ct', '--timers', help='Only use spawnpoints with confirmed timers (defaults to false).', action='store_true', default=False)
    spawns.add_argument('-lu', '--lastupdated', type=int, help='Only use spawnpoints that were last updated in x hours. Use 0 to disable this option (defaults to 0).', default=0)

    sng = parser.add_argument_group('Stops and Gyms')
    sng.add_argument('-ps', '--pokestops', help='Have pokestops included in the cluster search (defaults to false).', action='store_true', default=False)
    sng.add_argument('-gym', '--gyms', help='Have gyms included in the cluster search (defaults to false).', action='store_true', default=False)
    sng.add_argument('-mr', '--minraid', type=int, help='The minimum amount of gyms or pokestops to include in clusters that are written out (defaults to 1).', default=1)
    sng.add_argument('-rr', '--raidradius', type=float, help='Maximum radius (in meters) where gyms or pokestops are considered close (defaults to 500).', default=500)

    dbsets = parser.add_argument_group('Database')
    dbsets.add_argument('--db-name', help='Name of the database to be used (required).', required=True)
    dbsets.add_argument('--db-user', help='Username for the database (required).', required=True)
    dbsets.add_argument('--db-pass', help='Password for the database (required).', required=True)
    dbsets.add_argument('--db-host', help='IP or hostname for the database (defaults to 127.0.0.1).', default='127.0.0.1')
    dbsets.add_argument('--db-port', help='Port for the database (defaults to 3306).', type=int, default=3306)

    ivl = parser.add_argument_group('IV List',description='No cluster options will be recognized for the below options.')
    ivl.add_argument('-giv', '--genivlist', help='Skip all the normal functionality and just generate an IV list using RDM data (defaults to false).', action='store_true', default=False)
    ivl.add_argument('-mp', '--maxpoke', type=int, help='The maximum number to be used for the end of the IV list (defaults to 809).', default=809)
    ivl.add_argument('--excludepoke', help=('List of Pokemon to exclude from the IV list. Specified as Pokemon ID. Use this only in the config file (defaults to none).'), action='append', default=[])

    args = parser.parse_args()

    if args.genivlist:
        genivs(args)
        sys.exit(1)

    if not args.spawnpoints and not args.pokestops and not args.gyms:
        print('You must choose to include either spawnpoints, gyms, or pokestops for the query.')
        sys.exit(1)
    if not args.spawnpoints and args.timers:
        print('You cannot enable confirmed timers without spawnpoints.')
        sys.exit(1)

    main(args)

# Maybe use the RDM API to write to an instance after the coordinates are sorted
# Maybe add a geofence generator. If a geofence is generated, read it from the file to use it for clustering?
# Maybe add a circle generator for bootstrapping
# Maybe add an IV list generator
# Maybe change logic to look for max spawns first and then find lower amounts of spawns until the min. as per Mermao

# There is pokemon ID 0 in my poke_stats table. IDK if this will be an issue later

# As reported by Hunch. He got this warning with MySQL 5.7
# The warning is probably fine because it doesn't stop the queries.
#   Warning: (3090, "Changing sql mode 'NO_AUTO_CREATE_USER' is deprecated. It will be removed in a future release.")

# This error is caused if the geofence does not end with the starting coordinate or if mysql returns an error instead of data.
# Added a check that will write the first point to the end of the geo if they aren't equal.
#   File "cluster.py", line 233, in main
#   points = spawnpointssql.fetchall()
#   AttributeError: 'str' object has no attribute 'fetchall'

# As reported by Fossi, instances with single brackets in "area" can cause the below error. 
# Single bracket should not be used in RDM because it doesn't allow for multiple geofences.
# This usually happens if someone tries to use a pokemon instance.
# Added a check that it is either a quest or IV instance.
#    File "cluster.py", line 133, in getPoints
#    coord = str(c['lat'])+' '+str(c['lon'])+',\n'
#    TypeError: string indices must be integers
