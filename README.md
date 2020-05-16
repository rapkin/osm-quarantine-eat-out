# OSM quarantine eat out

![Places in Ukraine](/preview.jpg)

__Main idea__: use OSM data about pubs/restaurants/etc ([amenity in OSM](https://wiki.openstreetmap.org/wiki/Key:amenity)) to display places where you can eat or drink on quarantine.
By law in Ukraine you can visit places with outdor seatings (which marked in OSM as [outdoor_seating=yes](https://wiki.openstreetmap.org/wiki/Key:outdoor_seating)).
Feel free to reuse this code for your own purpose.

In this project I used [osm2geojson](https://github.com/aspectumapp/osm2geojson) to conver OSM data to GeoJSON.


## Installation

You should install `python >= 3.5` ([Installation guide](https://wiki.python.org/moin/BeginnersGuide/Download)).
To install dependencies for this project you should run `pip install -r requirements.txt`.


## Usage

In file `download_data.py` located helpfull methods to download all required data.
But main method that you can use is `get_outdoor_seatings_for_country`.
As argument to this method you should pass name of country or id of this country in OSM.
In result you will get geojson data with all found places.

Here example:

```python
from download_data import get_outdoor_seatings_for_country

get_outdoor_seatings_for_country('Ukraine')
# >> { "type": "FeatureCollection", "features": [ ... ] }
```
