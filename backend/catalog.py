import json
import pathlib
import re

source = (pathlib.Path(__file__).resolve().parents[1] / 'dist' / 'venues.js').read_text()
CITIES = json.loads(re.search(r'const cities=(.*?);', source, re.S).group(1))
VENUES = json.loads(re.search(r'const venues=(.*?);', source, re.S).group(1))
for venue in VENUES:
    venue['cityId'] = next(c['id'] for c in CITIES if c['name'] == venue['city'])

def cities():
    return CITIES

def venues(city_id):
    return [v for v in VENUES if v['cityId'] == city_id]
