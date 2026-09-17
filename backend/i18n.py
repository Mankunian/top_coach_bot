import json
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=3)
def catalog(language):
    if language not in ('ru','en','kaz'):language='ru'
    return json.loads((Path(__file__).resolve().parents[1]/'dist'/'locales'/(language+'.json')).read_text())

def language(db,uid):
    row=db.execute('SELECT data FROM users WHERE telegram_id=?',(uid,)).fetchone()
    return json.loads(row['data']).get('language','ru') if row else 'ru'

def tr(language,key,**values):
    return catalog(language).get(key,catalog('ru').get(key,key)).format(**values)

def duration_text(minutes,lang='ru'):
    h,m=divmod(max(0,round(minutes)),60)
    def word(n,forms):
        return forms[2] if 11<=n%100<=14 else forms[0] if n%10==1 else forms[1] if 2<=n%10<=4 else forms[2]
    parts=[]
    if h:parts.append(f"{h} "+('сағат' if lang=='kaz' else ('hour' if h==1 else 'hours') if lang=='en' else word(h,['час','часа','часов'])))
    if m or not h:parts.append(f"{m} "+('минут' if lang=='kaz' else ('minute' if m==1 else 'minutes') if lang=='en' else word(m,['минута','минуты','минут'])))
    return ' '.join(parts)
