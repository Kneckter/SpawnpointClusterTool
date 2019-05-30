import argparse
import json
import time
import random

import utils

class Spawnpoint(object):
    def __init__(self, data):
        try:
            self.position = (float(data['latitude']), float(data['longitude']))
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
  
def main(args):
    radius = args.radius
    
    with open(args.filename, 'r') as f:
        rows = json.loads(f.read())

    spawnpoints = [Spawnpoint(x) for x in rows]
      
    print 'Processing', len(spawnpoints), 'spawnpoints...'

    start_time = time.time()
    clusters = cluster(spawnpoints, radius)
    end_time = time.time()

    print 'Completed in {:.2f} seconds.'.format(end_time - start_time)
    print len(clusters), 'clusters found.'
    print '{:.2f}% compression achieved.'.format(100.0 * len(clusters) / len(spawnpoints))
    
    try:
        for c in clusters:
            for p in c:
                assert utils.distance(p.position, c.centroid) <= radius
    except AssertionError:
        print 'error: something\'s seriously broken.'
        raise

    rows = ''
    rowcount = 0
    f = open(args.output_clusters, 'w')
    for c in clusters:
        if len([x.serialize() for x in c]) > 3:
            rows = str(str(c.centroid[0]) + ',' + str(c.centroid[1]) +'\n')
            f.write(str(rows))
            rowcount += 1
    f.close()
    print rowcount, 'clusters with more than 3 spawnpoints in them written to the file.'

          
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Cluster close spawnpoints.')
    parser.add_argument('filename', help='Your spawnpoints.json file.')
    parser.add_argument('-oc', '--output-clusters', help='The filename to write cluster data to (defaults to outfile.txt).', default='outfile.txt')
    parser.add_argument('-r', '--radius', type=float, help='Maximum radius (in meters) where spawnpoints are considered close (defaults to 70).', default=70)
    
    args = parser.parse_args()
    
    main(args)