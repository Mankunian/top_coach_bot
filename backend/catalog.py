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
    # Existing clients consume the same catalog; admin edits persist in the DB.
    from .database import connect
    with connect() as db:
        if db.pg:
            exists = db.execute("SELECT to_regclass('admin_directory') AS name").fetchone()['name']
        else:
            exists = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_directory'").fetchone()
        if exists:
            records = [json.loads(r['data']) for r in db.execute("SELECT data FROM admin_directory WHERE kind='clubs'").fetchall()]
        else:
            records = VENUES
    return [v for v in records if v['cityId'] == city_id]
