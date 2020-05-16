import os

OVERPASS = "https://overpass-api.de/api/interpreter/"
DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIR, 'data')
CACHE_DIR = os.path.join(DATA_DIR, 'cache')
GEOMETRY_DIR = os.path.join(DATA_DIR, 'geometry')
SPLIT_SIZE = 1.5 # optimal value for countries
