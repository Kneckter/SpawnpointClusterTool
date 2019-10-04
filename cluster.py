import configargparse,time,sys,os,peewee,json,numpy,matplotlib,utils
from tsp_solver import solve_tsp

class Spawnpoint(object):
    def __init__(self, data):
        try:
            self.position = (float(data[0]), float(data[1]))
        except KeyError:
            self.position = (float(data['lat']), float(data['lng']))
        
    def serialize(self):
        obj = dict()

        obj['latitude'] = self.position[0]
        obj['longitude'] = self.position[1]

        return obj
        
class Spawncluster(object):
    def __init__(self, spawnpoint):
        self._spawnpoints = [spawnpoint]
        self.centroid = spawnpoint.position
        
    def __getitem__(self, key):
        return self._spawnpoints[key]
    
    def __iter__(self):
        for x in self._spawnpoints:
            yield x
      
    def __contains__(self, item):
        return item in self._spawnpoints
          
    def __len__(self):
        return len(self._spawnpoints)
        
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
    
def cluster(spawnpoints, radius):
    clusters = []

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
            SELECT data
            FROM instance
            WHERE name = '%s';
            ''' % args.geofence
        instance = db.execute_sql(cmd_sql)
    
    return instance

def getPoints(args, db, coordstr):
    with db:
        cmd_sql = 'SELECT * FROM ('
        if args.spawnpoints:
            cmd_sql = cmd_sql + '''
                SELECT lat,lon
                FROM spawnpoint
                WHERE ST_CONTAINS(
                ST_GEOMFROMTEXT('POLYGON((
                %s
                ))'), point(spawnpoint.lat, spawnpoint.lon))
                ''' % coordstr
            if args.timers:
                cmd_sql = cmd_sql + ' AND despawn_sec IS NOT NULL'
        if args.pokestops:
            if args.spawnpoints:
                cmd_sql = cmd_sql + ' UNION '
            cmd_sql = cmd_sql + '''
                SELECT lat,lon
                FROM pokestop
                WHERE ST_CONTAINS(
                ST_GEOMFROMTEXT('POLYGON((
                %s
                ))'), point(pokestop.lat, pokestop.lon))
                ''' % coordstr
        if args.gyms:
            if args.spawnpoints or args.pokestops:
                cmd_sql = cmd_sql + ' UNION '
            cmd_sql = cmd_sql + '''
                SELECT lat,lon
                FROM gym
                WHERE ST_CONTAINS(
                ST_GEOMFROMTEXT('POLYGON((
                %s
                ))'), point(gym.lat, gym.lon))
                ''' % coordstr

        cmd_sql = cmd_sql + ') x;'
        pointssql = db.execute_sql(cmd_sql)
        return pointssql

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

    for g in geofences:
        # Loop through the geofences
        numcoords = len(g) # Get the number of coordinates in this geofence
        i=1
        coordstr=''
        for c in g:
            # Loop through the coordinates in each geofence and build the string for the query
            if i < numcoords:
                #print(g.index(c))
                coord = str(c['lat'])+' '+str(c['lon'])+',\n'
                i=i+1
            else:
                coord = str(c['lat'])+' '+str(c['lon'])
            coordstr = coordstr + coord

        pointssql = getPoints(args, db, coordstr)
        points = pointssql.fetchall()

        rows = []
        for p in points:
            rows.append(p)

        spawnpoints = [Spawnpoint(x) for x in rows]

        print('Processing', len(spawnpoints), 'points...')
        start_time = time.time()
        clusters = cluster(spawnpoints, radius)

        try:
            for c in clusters:
                for p in c:
                    assert utils.distance(p.position, c.centroid) <= radius
        except AssertionError:
            print('error: something\'s seriously broken.')
            raise

        rows = ''
        rowcount = 0
        filename = str(args.output)+str(geofences.index(g))+'.txt'
        f = open(filename, 'w')

        for c in clusters:
            if len([x.serialize() for x in c]) > ms:
                rows = str(str(c.centroid[0]) + ',' + str(c.centroid[1]) +'\n')
                f.write(str(rows))
                rowcount += 1
        f.close()
        print('{} clusters with more than {} points in them.'.format(rowcount, ms))

        print('Sorting coordinates...')
        tspsolver(filename)

        end_time = time.time()
        print('Coordinates written to the {} file.'.format(filename))
        print('Completed in {:.2f} seconds.\n'.format(end_time - start_time))

    # Done with the geofences, close it down
    db.close()
    print('Database connection closed')

if __name__ == "__main__":

    defaultconfigfiles = []
    if '-cf' not in sys.argv and '--config' not in sys.argv:
        defaultconfigfiles = [os.getenv('servAP_CONFIG', os.path.join(os.path.dirname(__file__), './config.ini'))]
    parser = configargparse.ArgParser(default_config_files=defaultconfigfiles,auto_env_var_prefix='servAP_',description='Cluster close spawnpoints.')
    parser.add_argument('-cf', '--config', is_config_file=True, help='Set configuration file (defaults to ./config.ini).')

    parser.add_argument('-of', '--output', help='The base filename without extension to write cluster data to (defaults to outfile).', default='outfile')
    parser.add_argument('-r', '--radius', type=float, help='Maximum radius (in meters) where spawnpoints are considered close (defaults to 70).', default=70)
    parser.add_argument('-ms', '--min', type=int, help='The minimum amount of spawnpoints to include in clusters that are written out (defaults to 3).', default=3)
    parser.add_argument('-geo', '--geofence', help='The name of the RDM quest instance to use as a geofence (required).', required=True)

    parser.add_argument('-sp', '--spawnpoints', help='Have spawnpoints included in cluster search (defaults to false).', action='store_true', default=False)
    parser.add_argument('-ct', '--timers', help='Only use spawnpoints with confirmed timers (defaults to false).', action='store_true', default=False)
    parser.add_argument('-ps', '--pokestops', help='Have pokestops included in the cluster search (defaults to false).', action='store_true', default=False)
    parser.add_argument('-gym', '--gyms', help='Have gyms included in the cluster search (defaults to false).', action='store_true', default=False)

    group = parser.add_argument_group('Database')
    group.add_argument('--db-name', help='Name of the database to be used (required).', required=True)
    group.add_argument('--db-user', help='Username for the database (required).', required=True)
    group.add_argument('--db-pass', help='Password for the database (required).', required=True)
    group.add_argument('--db-host', help='IP or hostname for the database (defaults to 127.0.0.1).', default='127.0.0.1')
    group.add_argument('--db-port', help='Port for the database (defaults to 3306).', type=int, default=3306)
    
    args = parser.parse_args()

    if not args.spawnpoints and not args.pokestops and not args.gyms:
        print('You must choose to include either spawnpoints, gyms, or pokestops for the query.')
        sys.exit(1)
    if not args.spawnpoints and args.timers:
        print('You cannot enable confirmed timers without spawnpoints.')
        sys.exit(1)

    main(args)

# Maybe use the RDM API to write to an instance after the coordinates are sorted
