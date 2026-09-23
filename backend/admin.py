"""Read-only CRM administration and a persistent club/court directory."""
import csv
import io
import json
import uuid
from datetime import datetime, timedelta
from .database import connect
from .catalog import CITIES, VENUES
from .crm import TZ

RESOURCES = ('coaches', 'players', 'groups', 'sessions', 'requests', 'finance', 'clubs', 'courts')

def initialize():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS admin_directory (id TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS admin_audit (id TEXT PRIMARY KEY, username TEXT NOT NULL, action TEXT NOT NULL, created TEXT NOT NULL, data TEXT NOT NULL)')
        if not db.execute('SELECT id FROM migrations WHERE id=?', ('admin-directory-v1',)).fetchone():
            for venue in VENUES:
                db.execute('INSERT INTO admin_directory VALUES (?,?,?) ON CONFLICT(id) DO NOTHING', (venue['id'], 'clubs', json.dumps(venue, ensure_ascii=False)))
            db.execute('INSERT INTO migrations VALUES (?)', ('admin-directory-v1',))

def period(query):
    today = datetime.now(TZ).date()
    start = datetime.strptime(query.get('from', (today-timedelta(days=29)).isoformat()), '%Y-%m-%d').date()
    end = datetime.strptime(query.get('to', today.isoformat()), '%Y-%m-%d').date()
    if end < start or (end-start).days > 366: raise ValueError('Период: от 1 до 367 дней')
    return start.isoformat(), end.isoformat()

def snapshot():
    with connect() as db:
        # Keep the shared JSON state and profiles consistent with concurrent CRM writes.
        db.execute('BEGIN IMMEDIATE')
        state = json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data'])
        users = [json.loads(row['data']) for row in db.execute('SELECT data FROM users').fetchall()]
        directory = [dict(json.loads(row['data']), kind=row['kind']) for row in db.execute('SELECT * FROM admin_directory').fetchall()]
    people = {u['telegramId']: u for u in users}
    def enriched(row):
        item = dict(row)
        for key in ('coach', 'player'):
            if key in row: item[key+'Name'] = people.get(row[key], {}).get('fullName', str(row[key]))
        if 'members' in item: item['memberCount'] = len(item['members'])
        if 'created' in item: item['createdDate'] = datetime.fromtimestamp(item['created'], TZ).date().isoformat()
        if 'city' not in item and 'coach' in row: item['city'] = people.get(row['coach'], {}).get('city', '')
        return item
    public_fields = ('telegramId', 'fullName', 'username', 'email', 'city', 'cityId', 'venue', 'bio', 'role')
    profiles = [dict({k: u.get(k, '') for k in public_fields}, id=str(u['telegramId'])) for u in users if u.get('step') == 'done']
    return dict(coaches=[u for u in profiles if u['role']=='coach'], players=[u for u in profiles if u['role'] in ('player','parent')],
                **{key: [enriched(x) for x in state[key]] for key in ('groups','sessions','requests')},
                finance=[enriched(p) for p in state['payments']],
                clubs=[d for d in directory if d['kind']=='clubs'], courts=[d for d in directory if d['kind']=='courts'])

def filtered(resource, query, data):
    rows = data[resource]
    start, end = period(query)
    date_field = {'sessions':'date', 'finance':'date', 'requests':'createdDate'}.get(resource)
    if date_field: rows = [r for r in rows if start <= r.get(date_field, '') <= end]
    for field in ('status', 'city', 'coach'):
        if query.get(field): rows = [r for r in rows if str(r.get(field,'')) == query[field]]
    term = query.get('q','').strip().casefold()
    if term: rows = [r for r in rows if term in ' '.join(str(v) for v in r.values()).casefold()]
    return sorted(rows, key=lambda r: (str(r.get(date_field or 'fullName', r.get('name',''))), str(r['id'])), reverse=bool(date_field))

def listing(resource, query):
    rows = filtered(resource, query, snapshot())
    page, size = int(query.get('page',1)), int(query.get('pageSize',20))
    if page<1 or not 1<=size<=100: raise ValueError('Некорректная страница')
    return dict(items=rows[(page-1)*size:page*size], total=len(rows), page=page, pageSize=size,
                summary={'amount':sum(r['amount'] for r in rows),'hours':sum(r.get('hours',0) for r in rows)} if resource=='finance' else None)

def dashboard(query):
    data = snapshot(); start,end = period(query)
    sessions = filtered('sessions', query, data); payments = filtered('finance', query, data)
    counts = {status:sum(s['status']==status for s in sessions) for status in ('scheduled','completed','cancelled')}
    days=[]; day=datetime.fromisoformat(start).date()
    while day.isoformat()<=end:
        label=day.isoformat()
        days.append(dict(date=label, payments=sum(p['amount'] for p in payments if p['date']==label), completed=sum(s['status']=='completed' and s['date']==label for s in sessions)))
        day+=timedelta(days=1)
    return dict(start=start,end=end,timezone='Asia/Almaty (UTC+5)', coaches=len(data['coaches']), players=len(data['players']),
                groups=len(data['groups']), pending=sum(r['status']=='pending' for r in data['requests']),
                completed=counts['completed'], payments=sum(p['amount'] for p in payments), paymentCount=len(payments), statuses=counts, series=days)

def mutate(resource, payload, username):
    if resource not in ('clubs','courts'): raise ValueError('Раздел доступен только для просмотра')
    operation=payload.get('operation'); identifier=payload.get('id')
    if operation not in ('create','update','delete'): raise ValueError('Неизвестное действие')
    if operation!='create' and (not isinstance(identifier,str) or len(identifier)>100): raise ValueError('Некорректный ID')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT data FROM admin_directory WHERE id=? AND kind=?',(identifier,resource)).fetchone() if identifier else None
        if operation!='create' and not old: raise ValueError('Запись не найдена')
        if operation=='delete':
            if resource=='clubs':
                courts=[json.loads(r['data']) for r in db.execute("SELECT data FROM admin_directory WHERE kind='courts'").fetchall()]
                if any(c['clubId']==identifier for c in courts): raise ValueError('Сначала удалите корты клуба')
                users=[json.loads(r['data']) for r in db.execute('SELECT data FROM users').fetchall()]
                if any(u.get('venueId')==identifier for u in users): raise ValueError('Клуб используется в профилях; удаление запрещено')
            db.execute('DELETE FROM admin_directory WHERE id=?',(identifier,)); record=json.loads(old['data'])
        else:
            source=payload.get('data',{})
            if not isinstance(source,dict): raise ValueError('Проверьте поля')
            record=json.loads(old['data']) if old else {'id':str(uuid.uuid4())}
            fields=('name','cityId','address') if resource=='clubs' else ('name','clubId','surface','status')
            for field in fields:
                value=source.get(field,record.get(field,''))
                if not isinstance(value,str) or not value.strip() or len(value)>250: raise ValueError('Заполните поле '+field)
                record[field]=value.strip()
            if resource=='clubs':
                city=next((c for c in CITIES if c['id']==record['cityId']),None)
                if not city: raise ValueError('Выберите город')
                record['city']=city['name']
                if old and json.loads(old['data'])['cityId']!=record['cityId']:
                    users=[json.loads(r['data']) for r in db.execute('SELECT data FROM users').fetchall()]
                    if any(u.get('venueId')==identifier for u in users): raise ValueError('Нельзя сменить город клуба, выбранного в профилях')
            else:
                club=db.execute("SELECT data FROM admin_directory WHERE id=? AND kind='clubs'",(record['clubId'],)).fetchone()
                if not club: raise ValueError('Выберите клуб')
                if record['status'] not in ('active','maintenance','closed'): raise ValueError('Выберите статус')
            identifier=record['id']
            db.execute('INSERT INTO admin_directory VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(identifier,resource,json.dumps(record,ensure_ascii=False)))
        db.execute('INSERT INTO admin_audit VALUES (?,?,?,?,?)',(str(uuid.uuid4()),username,resource+'.'+operation,datetime.now(TZ).isoformat(),json.dumps({'before':json.loads(old['data']) if old else None,'after':record if operation!='delete' else None},ensure_ascii=False)))
    return {'ok':True,'id':identifier}

REPORT_FIELDS={
    'coaches':['id','fullName','email','city','venue'], 'players':['id','fullName','role','email','city'],
    'groups':['id','name','coachName','city','place','memberCount','start','end'],
    'sessions':['id','name','coachName','date','time','status','memberCount'],
    'requests':['id','playerName','coachName','createdDate','status'],
    'finance':['id','date','coachName','playerName','payer','amount','hours','group'],
    'clubs':['id','name','city','address'], 'courts':['id','name','clubId','surface','status']}

def report(resource, query):
    rows=filtered(resource,query,snapshot()); start,end=period(query)
    stream=io.StringIO(); writer=csv.writer(stream)
    fields=REPORT_FIELDS[resource]
    writer.writerow(['period_from','period_to','timezone']+[('amount_KZT' if f=='amount' else f) for f in fields])
    def safe(value):
        value=str(value)
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value
    for row in rows:
        writer.writerow([start,end,'Asia/Almaty (UTC+5)']+[safe(f"{row.get(f,0)/100:.2f}" if f=='amount' else row.get(f,'')) for f in fields])
    return ('\ufeff'+stream.getvalue()).encode('utf-8')
