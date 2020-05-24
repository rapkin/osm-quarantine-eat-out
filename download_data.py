import requests
import urllib
import codecs
import json
import zlib
import time
import os
from pathlib import Path
from shapely import geometry
from shapely.strtree import STRtree
from osm2geojson import json2geojson
from config import OVERPASS, DIR, DATA_DIR, CACHE_DIR, GEOMETRY_DIR, SPLIT_SIZE

Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
Path(GEOMETRY_DIR).mkdir(parents=True, exist_ok=True)


def measure(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print('%r  %2.2f ms' % (method.__name__, (te - ts) * 1000))
        return result
    return timed


# source from https://snorfalorpagus.net/blog/2016/03/13/splitting-large-polygons-for-faster-intersections/
def katana(shape, threshold, count=0):
    """Split a Polygon into two parts across it's shortest dimension"""
    bounds = shape.bounds
    if len(bounds) == 0:
        # emptry geometry, usual situation
        width = 0
        height = 0
    else:
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]

    if max(width, height) <= threshold or count == 250:
        # either the polygon is smaller than the threshold, or the maximum
        # number of recursions has been reached
        return [shape]
    if height >= width:
        # split left to right
        a = geometry.box(bounds[0], bounds[1], bounds[2], bounds[1]+height/2)
        b = geometry.box(bounds[0], bounds[1]+height/2, bounds[2], bounds[3])
    else:
        # split top to bottom
        a = geometry.box(bounds[0], bounds[1], bounds[0]+width/2, bounds[3])
        b = geometry.box(bounds[0]+width/2, bounds[1], bounds[2], bounds[3])
    result = []
    for d in (a, b,):
        c = shape.intersection(d)
        if not isinstance(c, geometry.GeometryCollection):
            c = [c]
        for e in c:
            if isinstance(e, (geometry.Polygon, geometry.MultiPolygon)):
                result.extend(katana(e, threshold, count+1))
    if count > 0:
        return result
    # convert multipart into singlepart
    final_result = []
    for g in result:
        if isinstance(g, geometry.MultiPolygon):
            final_result.extend(g)
        else:
            final_result.append(g)
    return final_result


def overpass_call(query):
    encoded = urllib.parse.quote(query.encode('utf-8'), safe='~()*!.\'')
    r = requests.post(OVERPASS,
                      data=f"data={encoded}",
                      headers={'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
    if not r.status_code is 200:
        raise requests.exceptions.HTTPError('Overpass server respond with status '+str(r.status_code))
    return r.text


def cached_overpass_call(query):
    name = os.path.join(CACHE_DIR, str(zlib.adler32(query.encode())) + '.json')
    if os.path.exists(name):
        with codecs.open(name, 'r', encoding='utf8') as data:
            return data.read()
    data = overpass_call(query)
    save_file(data, name)
    return data


def save_data(data, geom_file):
    json_data = json.dumps(data, indent=2)
    save_file(json_data, geom_file)


def save_file(data, file):
    f = codecs.open(file, 'w')
    f.write(data)
    f.close()


def get_name_from_tags(el):
    return el['tags'].get('int_name', el['tags'].get('name:en', el['tags'].get('name', 'noname')))


def get_city_center(id):
    if id is None:
        return None

    elements = json.loads(cached_overpass_call(f"""
        [out:json];
        node({id});
        out;
    """))['elements']

    if len(elements) < 1:
        return None

    center = elements[0]
    return {
        'lat': center['lat'],
        'lon': center['lon'],
        'name': get_name_from_tags(center)
    }


def get_countries():
    file = os.path.join(DATA_DIR, 'countries.json')
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)

    data = cached_overpass_call(f"""
        [out:json];
        rel[admin_level=2];
        out;
    """)
    json_data = json.loads(data)

    countries = []
    for el in json_data['elements']:
        admin_centre_ref = None
        for m in el['members']:
            if 'role' in m and m['role'] == 'admin_centre':
                admin_centre_ref = m['ref']

        name = get_name_from_tags(el)
        admin_center = get_city_center(admin_centre_ref)

        if admin_center is None:
            print('Admin center not found', id, name)
            continue

        countries.append({
            'id': el['id'],
            'name': name,
            'admin_center': admin_center
        })

    save_data(countries, file)
    return countries


def find_country(name_or_id):
    countries = get_countries()
    found = None
    for country in countries:
        if country['name'] == name_or_id or country['id'] == name_or_id:
            found = country
    return found


def get_border(id):
    file = os.path.join(GEOMETRY_DIR, f"border_{id}.geojson")
    if os.path.exists(file):
        with open(file, encoding='utf-8') as d:
            return json.load(d)['features'][0]

    data = cached_overpass_call(f"""
        [out:json];
        rel({id});
        out geom;
    """)
    geojson_data = json2geojson(data)

    border = None
    for f in geojson_data['features']:
        if f['properties']['tags']['type'] == 'boundary':
            border = f

    if border is not None:
        geojson_data['features'] = [border]
        save_data(geojson_data, file)
    return border


def get_features_inside_shape(geojson_data, border_shape):
    optimized_shapes = katana(border_shape, SPLIT_SIZE)
    tree = STRtree(optimized_shapes)

    inside_shape = []
    for feature in geojson_data['features']:
        shape = geometry.shape(feature['geometry'])
        for segment in tree.query(shape):
            if segment.contains(shape):
                inside_shape.append(feature)
    geojson_data['features'] = inside_shape
    return geojson_data


def get_outdoor_seating_nodes(id):
    file = os.path.join(GEOMETRY_DIR, f"seatings_{id}.geojson")
    if os.path.exists(file):
        with open(file, encoding='utf-8') as f:
            return json.load(f)

    border = get_border(id)
    border_shape = geometry.shape(border['geometry'])
    minlon, minlat, maxlon, maxlat = border_shape.bounds
    bbox = f"({minlat}, {minlon}, {maxlat}, {maxlon})"
    amenities = ['restaurant', 'pub', 'bar', 'cafe', 'fast_food', 'bbq', 'biergarten', 'food_court']

    data = cached_overpass_call(f"""
        [out:json];
        node[outdoor_seating=yes][amenity~"^{'$|^'.join(amenities)}$"]{bbox};
        out geom;
    """)

    geojson_data = json2geojson(data, filter_used_refs=False)
    geojson_data = get_features_inside_shape(geojson_data, border_shape)
    for feature in geojson_data['features']:
        feature['properties']['name'] = feature['properties']['tags'].get('name', 'noname')
    save_data(geojson_data, file)
    return geojson_data


def get_outdoor_seatings_for_country(name_or_id):
    country = find_country(name_or_id)
    if country is None:
        return None

    return get_outdoor_seating_nodes(country['id'])
