import json, uuid, time, os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from .database import connect
from .service import read_user, save_user, send
from .catalog import cities
TZ=timezone(timedelta(hours=5))
def ident():return str(uuid.uuid4())
def required(value,maxlen=250):
    if not isinstance(value,str) or not value.strip() or len(value)>maxlen:raise ValueError('Заполните обязательные поля')
    return value.strip()
def members(state,coach):return [r['player'] for r in state['requests'] if r['coach']==coach and r['status']=='accepted']
def balance_key(coach,player):return str(coach)+':'+str(player)
def date(value):return datetime.strptime(value,'%Y-%m-%d').date()
def duration(value):
    if type(value)!=int or value not in [30,60,90,120]:raise ValueError('Выберите длительность: 30, 60, 90 или 120 минут')
    return value

def assign_member(state,db,user,g,pid):
    if type(pid)!=int or pid not in members(state,user['telegramId']):raise ValueError('Ученик ещё не принят')
    if pid in g['members']:return
    if g['type']=='Индивидуальная' and g['members']:raise ValueError('В индивидуальной группе может быть только один ученик')
    g['members'].append(pid)
    for session in state['sessions']:
        if session['group']==g['id'] and session['status']=='scheduled' and pid not in session['members']:session['members'].append(pid)
    upcoming=sorted([session for session in state['sessions'] if session['group']==g['id'] and session['status']=='scheduled' and session['ends']>time.time()],key=lambda session:session['begins'])
    next_text=(f"\nБлижайшая тренировка: {upcoming[0]['date']} в {upcoming[0]['time']}." if upcoming else '\nРасписание появится после назначения тренировки.')
    send(db,pid,f"🎾 Тренер {user['fullName']} добавил вас в группу «{g['name']}».\n📍 {g['place']}"+next_text+'\nДо встречи на корте!')

def add_selected_members(state,db,user,g,data):
    selected=data.get('members',[])
    if not isinstance(selected,list):raise ValueError('Проверьте список учеников')
    for pid in selected:assign_member(state,db,user,g,pid)

def generate(state,g):
    start=max(date(g['start']),datetime.now(TZ).date());end=min(date(g['end']) if g['end'] else start+timedelta(days=90),start+timedelta(days=90))
    existing={(s['group'],s['date']) for s in state['sessions']}
    while start<=end:
        ds=start.isoformat()
        if (start.weekday()+1)%7 in g['days'] and (g['id'],ds) not in existing:
            begins=datetime.fromisoformat(ds+'T'+g['time']).replace(tzinfo=TZ).timestamp()
            minutes=g.get('durationMinutes',60)
            if begins+minutes*60>time.time():state['sessions'].append(dict(id=ident(),group=g['id'],coach=g['coach'],name=g['name'],place=g['place'],date=ds,time=g['time'],begins=begins,ends=begins+minutes*60,durationMinutes=minutes,members=list(g['members']),absent=[],status='scheduled',reminded=[]))
        start+=timedelta(days=1)
def tick(state,db,now=None):
    now=now or time.time()
    for g in state['groups']:generate(state,g)
    for s in state['sessions']:
        if s['status']!='scheduled':continue
        if now>=s['ends']:
            s['status']='completed';s['charges']=[]
            for pid in s['members']:
                key=balance_key(s['coach'],pid);charged=pid not in s['absent'] and state['balances'].get(key,0)>0
                if charged:state['balances'][key]-=1
                s['charges'].append(dict(player=pid,hours=1 if charged else 0))
                send(db,pid,f"🏁 Тренировка «{s['name']}» завершена.\n"+('Списан 1 час.' if charged else 'Часы не списаны.')+f"\nОстаток: {state['balances'].get(key,0)} ч.")
            send(db,s['coach'],f"🏁 Тренировка группы «{s['name']}» завершена.\n{s['date']} · {s['time']}\nСписано часов: {sum(c['hours'] for c in s['charges'])}.")
            continue
        if now>=s['begins'] and not s.get('startNotified'):
            for recipient in set([s['coach']]+[p for p in s['members'] if p not in s['absent']]):
                send(db,recipient,f"🎾 Тренировка группы «{s['name']}» началась!\n🕒 {s['time']} · {s['date']}\n📍 {s['place']}")
            s['startNotified']=True
        for hours in [3]:
            # Avoid sending both missed reminders after downtime.
            delta=s['begins']-now
            if hours not in s['reminded'] and hours*3600-180<=delta<=hours*3600:
                for uid in set([s['coach']]+s['members']):send(db,uid,f"🎾 {s['name']} — {s['date']} в {s['time']}\n📍 {s['place']}\nДо тренировки {hours} ч.")
                s['reminded'].append(hours)
def state_view(state,user,db):
    uid=user['telegramId'];coach=user['role']=='coach'
    profiles=[json.loads(r['data']) for r in db.execute('SELECT data FROM users').fetchall()]
    people={u['telegramId']:u for u in profiles}
    public=lambda u:{k:u.get(k,'') for k in ['telegramId','fullName','city','cityId','bio','venue','address']}
    req=[r for r in state['requests'] if r['coach']==uid] if coach else [r for r in state['requests'] if r['player']==uid]
    ids=members(state,uid) if coach else [uid]
    def card(pid):
        u=people.get(pid,{});c=uid if coach else next((r['coach'] for r in req if r['status']=='accepted'),0)
        return dict(public(u),displayName=state.get('names',{}).get(balance_key(c,pid),u.get('fullName','Игрок')),hours=state['balances'].get(balance_key(c,pid),0),comment=state['comments'].get(balance_key(c,pid),''),username=u.get('username'))
    return dict(user=user,cities=cities(),paidTotal=sum(p['amount'] for p in state['payments'] if p['player']==uid and any(r['coach']==p['coach'] and r['status']=='accepted' for r in req)) if not coach else 0,requests=[dict(r,playerName=people.get(r['player'],{}).get('fullName','Игрок'),coachName=people.get(r['coach'],{}).get('fullName','Тренер')) for r in req],students=[card(pid) for pid in ids if pid in people],groups=[g for g in state['groups'] if g['coach']==uid or (not coach and uid in g['members'])],sessions=[s for s in state['sessions'] if s['coach']==uid or (not coach and uid in s['members'])],payments=[p for p in state['payments'] if p['coach']==uid] if coach else [],trainers=[dict(public(u),username=u.get('username') if any(r['coach']==u['telegramId'] and r['status']=='accepted' for r in req) else None) for u in profiles if u.get('role')=='coach' and u.get('step')=='done' and u.get('cityId')==user.get('cityId')])
def perform(user,action,data):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE');state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data']);tick(state,db)
        uid=user['telegramId'];coach=user['role']=='coach'
        def own_group():
            g=next((g for g in state['groups'] if g['id']==data.get('id') and g['coach']==uid),None)
            if not g:raise ValueError('Группа недоступна')
            return g
        if action=='request':
            if coach:raise ValueError('Заявка доступна игроку')
            target=read_user(db,int(data['coach']))
            if not target or target.get('role')!='coach' or target.get('step')!='done' or target.get('cityId')!=user.get('cityId'):raise ValueError('Тренер недоступен')
            if any(r['player']==uid and r['status'] in ['pending','accepted'] for r in state['requests']):raise ValueError('Заявка уже отправлена или принята')
            state['requests'].append(dict(id=ident(),coach=target['telegramId'],player=uid,status='pending',comment=str(data.get('comment',''))[:500],created=time.time()))
            app_url=os.getenv('MINI_APP_URL','')
            markup=None
            if app_url.startswith('https://'):
                url=urlsplit(app_url);query=dict(parse_qsl(url.query));query['page']='requests'
                link=urlunsplit((url.scheme,url.netloc,url.path,urlencode(query),url.fragment))
                markup={'inline_keyboard':[[{'text':'📩 Открыть заявки','web_app':{'url':link}}]]}
            comment=str(data.get('comment','')).strip()[:500] or 'Не указан'
            send(db,target['telegramId'],f"📩 Новая заявка на тренировки\n\n👤 Ученик: {user['fullName']}\n📍 Город: {user.get('city','—')}\n\n💬 Комментарий:\n{comment}\n\nПримите или отклоните заявку в TopCoach.",markup)
        elif action in ['decision','group','edit_group','assign','rename','delete','payment','comment','student_name','attendance','cancel']:
            if not coach:raise ValueError('Действие доступно тренеру')
            if action=='decision':
                r=next((r for r in state['requests'] if r['id']==data.get('id') and r['coach']==uid),None)
                if not r or r['status']!='pending' or data.get('status') not in ['accepted','rejected']:raise ValueError('Заявка недоступна')
                r['status']=data['status'];r['decided']=time.time();state['comments'][balance_key(uid,r['player'])]=r['comment']
                send(db,r['player'],f"✅ Тренер {user['fullName']} принял вашу заявку!\n\nСкоро тренер свяжется с вами или определит вас в группу. Расписание появится в TopCoach." if r['status']=='accepted' else 'Заявка отклонена. Свяжитесь с тренером для уточнения.')
            elif action=='group':
                name=required(data.get('name'),60);place=required(data.get('place'));start=date(data['start']);end=date(data['end']) if data.get('end') else None
                days=data.get('days',[]);kind=data.get('type');clock=datetime.strptime(data['time'],'%H:%M')
                if not days or any(type(d)!=int or d not in range(7) for d in days) or kind not in ['Групповая','Индивидуальная'] or (end and end<start):raise ValueError('Проверьте расписание')
                g=dict(id=ident(),coach=uid,name=name,place=place,city=user.get('city'),start=start.isoformat(),end=end.isoformat() if end else '',days=days,time=clock.strftime('%H:%M'),type=kind,durationMinutes=duration(data.get('durationMinutes',60)),members=[])
                state['groups'].append(g);generate(state,g);add_selected_members(state,db,user,g,data)
            elif action in ['assign','rename','delete','edit_group']:
                g=own_group()
                if action=='edit_group':
                    g['name']=required(data.get('name',g['name']),60)
                    g['durationMinutes']=duration(data.get('durationMinutes',g.get('durationMinutes',60)))
                    # Preserve started/completed sessions; change only future defaults.
                    for session in state['sessions']:
                        if session['group']==g['id'] and session['status']=='scheduled' and session['begins']>time.time():
                            session.update(name=g['name'],durationMinutes=g['durationMinutes'],ends=session['begins']+g['durationMinutes']*60)
                    add_selected_members(state,db,user,g,data)
                if action=='assign':assign_member(state,db,user,g,int(data['player']))
                if action=='rename':
                    g['name']=required(data.get('name'),60)
                    for s in state['sessions']:
                        if s['group']==g['id'] and s['status']=='scheduled':s['name']=g['name']
                if action=='delete':
                    if any(s['group']==g['id'] and s['status']=='scheduled' and s['begins']-time.time()<=86400 for s in state['sessions']):raise ValueError('Нельзя удалить группу с тренировкой в ближайшие 24 часа')
                    state['groups'].remove(g)
                    for s in state['sessions']:
                        if s['group']==g['id'] and s['status']=='scheduled':s['status']='cancelled';s['reason']='Группа удалена'
            elif action in ['payment','comment','student_name']:
                pid=int(data['player'])
                if pid not in members(state,uid):raise ValueError('Ученик недоступен')
                key=balance_key(uid,pid)
                if action=='student_name':state.setdefault('names',{})[key]=required(data.get('name'),120)
                elif action=='comment':state['comments'][key]=str(data.get('comment',''))[:500]
                else:
                    hours=data.get('hours')
                    try:amount=Decimal(str(data['amount']))
                    except InvalidOperation:raise ValueError('Укажите сумму оплаты')
                    paid=date(data['date']);nonce=required(data.get('nonce'),80)
                    if type(hours)!=int or not 0<hours<=100000 or not amount.is_finite() or amount<0 or amount>1000000000 or amount*100!=int(amount*100) or paid>datetime.now(TZ).date():raise ValueError('Проверьте часы, сумму и дату')
                    if not any(p['nonce']==nonce and p['coach']==uid for p in state['payments']):
                        g=next((g for g in state['groups'] if g['coach']==uid and pid in g['members']),None)
                        state['payments'].append(dict(id=ident(),nonce=nonce,coach=uid,player=pid,name=state.get('names',{}).get(key,read_user(db,pid)['fullName']),hours=hours,amount=int(amount*100),date=paid.isoformat(),created=time.time(),payer=required(data.get('payer'),120),comment=str(data.get('comment',''))[:500],group=g['name'] if g else 'Без группы',type=g['type'] if g else 'Не назначен'))
                        state['balances'][key]=state['balances'].get(key,0)+hours
                        send(db,pid,f"✅ Тренер {user['fullName']} добавил {hours} ч.\n💳 Оплачено: {amount:,.2f} ₸\n📅 Дата оплаты: {paid.isoformat()}\n🎾 На балансе: {state['balances'][key]} ч.")
            else:
                s=next((s for s in state['sessions'] if s['id']==data.get('id') and s['coach']==uid),None)
                if not s or s['status']!='scheduled':raise ValueError('Тренировка завершена или недоступна')
                if action=='cancel':
                    if s['begins']-time.time()<=86400:raise ValueError('Отмена доступна более чем за 24 часа')
                    s['reason']=required(data.get('reason'),500);s['status']='cancelled'
                    for pid in set([uid]+s['members']):send(db,pid,f"Тренировка «{s['name']}» {s['date']} отменена. Причина: {s['reason']}. Часы не снимутся.")
                else:
                    pid=int(data['player'])
                    if pid not in s['members'] or type(data.get('present'))!=bool:raise ValueError('Некорректный участник')
                    s['absent']=[p for p in s['absent'] if p!=pid]
                    if not data['present']:s['absent'].append(pid)
        elif action=='absence':
            s=next((s for s in state['sessions'] if s['id']==data.get('id') and uid in s['members']),None)
            if not s or s['status']!='scheduled' or s['begins']-time.time()<86400:raise ValueError('До занятия осталось менее суток')
            if uid not in s['absent']:s['absent'].append(uid);send(db,s['coach'],f"{user['fullName']} не придёт на {s['name']} {s['date']}.")
        elif action!='view':raise ValueError('Неизвестное действие')
        db.execute('UPDATE crm SET data=? WHERE id=1',(json.dumps(state,ensure_ascii=False),))
        return state_view(state,user,db)
