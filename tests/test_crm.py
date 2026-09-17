import os, tempfile, unittest, json, time
from datetime import datetime, timedelta
from backend.database import initialize, connect
from backend.service import save_user
from backend.crm import perform, tick, TZ
from backend.catalog import cities

class CRMTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();os.environ['DB_PATH']=self.temp.name+'/db';initialize()
  self.coach=dict(telegramId=10,id='a',fullName='Coach',role='coach',step='done',cityId=cities()[0]['id'],city='Астана')
  self.player=dict(telegramId=20,id='b',fullName='Player',role='player',step='done',cityId=cities()[0]['id'],city='Астана')
  self.other=dict(self.coach,telegramId=30)
  with connect() as db:
   for u in [self.coach,self.player,self.other]:save_user(db,u)
 def tearDown(self):self.temp.cleanup()
 def setup_group(self):
  perform(self.player,'request',{'coach':10,'comment':'Пн 19:00'})
  s=perform(self.coach,'view',{});perform(self.coach,'decision',{'id':s['requests'][0]['id'],'status':'accepted'})
  day=datetime.now(TZ).date()+timedelta(days=2)
  s=perform(self.coach,'group',dict(name='Альфа',place='Корт',start=day.isoformat(),end=day.isoformat(),time='19:00',days=[(day.weekday()+1)%7],type='Групповая'))
  gid=s['groups'][0]['id'];perform(self.coach,'assign',dict(id=gid,player=20));return gid
 def test_full_flow_and_isolation(self):
  self.assertEqual(len(perform(self.player,'view',{})['trainers']),2)
  gid=self.setup_group()
  self.assertEqual(perform(self.other,'view',{})['students'],[])
  with self.assertRaises(ValueError):perform(self.other,'rename',dict(id=gid,name='Hijack'))
  with self.assertRaises(ValueError):perform(self.player,'group',{})
  data=dict(player=20,hours=5,amount='12000.50',date=datetime.now(TZ).date().isoformat(),payer='Parent',nonce='unique')
  perform(self.coach,'payment',data);perform(self.coach,'payment',data)
  p=perform(self.player,'view',{});self.assertEqual(p['paidTotal'],1200050);self.assertEqual(perform(self.other,'view',{})['paidTotal'],0);self.assertEqual(p['students'][0]['hours'],5);self.assertEqual(p['payments'],[])
  self.assertEqual(len(perform(self.coach,'view',{})['payments']),1)
  with self.assertRaises(ValueError):perform(self.player,'request',{'coach':30})
  session=p['sessions'][0]
  perform(self.player,'absence',{'id':session['id']})
  with connect() as db:
   state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data']);tick(state,db,session['ends']+1);tick(state,db,session['ends']+1)
   self.assertEqual(state['balances']['10:20'],5);self.assertEqual(state['sessions'][0]['status'],'completed')
 def test_charge_once_cancel(self):
  self.setup_group();perform(self.coach,'payment',dict(player=20,hours=2,amount='10',date=datetime.now(TZ).date().isoformat(),payer='Player',nonce='a'))
  with connect() as db:
   state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data']);s=state['sessions'][0];tick(state,db,s['ends']+1);tick(state,db,s['ends']+1)
   self.assertEqual(state['balances']['10:20'],1)
  s=perform(self.coach,'view',{})['sessions'][0];perform(self.coach,'cancel',dict(id=s['id'],reason='Дождь'))
  self.assertEqual(perform(self.player,'view',{})['sessions'][0]['status'],'cancelled')
 def test_bad_payments(self):
  self.setup_group()
  for amount in ['NaN','-1','1.001']:
   with self.assertRaises(ValueError):perform(self.coach,'payment',dict(player=20,hours=1,amount=amount,date=datetime.now(TZ).date().isoformat(),payer='P',nonce='a'))
 def test_notifications_names_and_start_once(self):
  self.setup_group()
  perform(self.coach,'student_name',dict(player=20,name='Иван Петров'))
  self.assertEqual(perform(self.coach,'view',{})['students'][0]['displayName'],'Иван Петров')
  with self.assertRaises(ValueError):perform(self.other,'student_name',dict(player=20,name='Чужое имя'))
  data=dict(player=20,hours=3,amount='30000',date=datetime.now(TZ).date().isoformat(),payer='Иван',nonce='notify')
  perform(self.coach,'payment',data);perform(self.coach,'payment',data)
  with connect() as db:
   payloads=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM outbox').fetchall()]
   texts=[p.get('text','') for p in payloads]
   self.assertTrue(any('Coach принял вашу заявку' in t for t in texts))
   self.assertTrue(any('добавил вас в группу' in t and 'Ближайшая тренировка' in t for t in texts))
   self.assertEqual(sum('добавил 3 ч' in t for t in texts),1)
   state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data']);s=state['sessions'][0]
   tick(state,db,s['begins']+1);tick(state,db,s['begins']+2)
   payloads=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM outbox').fetchall()]
   started=[p for p in payloads if 'началась!' in p.get('text','')]
   self.assertEqual(len(started),2);self.assertEqual({p['chat_id'] for p in started},{10,20})
 def test_three_hour_and_end_notifications(self):
  self.setup_group()
  with connect() as db:
   state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data']);s=state['sessions'][0]
   db.execute('DELETE FROM outbox')
   tick(state,db,s['begins']-48*3600)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0],0)
   tick(state,db,s['begins']-3*3600);tick(state,db,s['begins']-3*3600+1)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0],2)
   tick(state,db,s['ends']);tick(state,db,s['ends']+1)
   messages=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM outbox').fetchall()]
   self.assertEqual(sum('завершена' in m.get('text','') for m in messages),2)

 def test_request_notification_deep_link(self):
  from unittest.mock import patch
  with patch.dict(os.environ,{'MINI_APP_URL':'https://example.com/mini.html?source=bot'}):
   perform(self.player,'request',{'coach':10,'comment':'Вечерняя группа'})
  with connect() as db:
   payload=json.loads(db.execute('SELECT payload FROM outbox ORDER BY id DESC').fetchone()['payload'])
  self.assertIn('Player',payload['text']);self.assertIn('Вечерняя группа',payload['text'])
  self.assertIn('page=requests',payload['reply_markup']['inline_keyboard'][0][0]['web_app']['url'])
  self.assertIn('source=bot',payload['reply_markup']['inline_keyboard'][0][0]['web_app']['url'])

 def test_refresh_at_end_persists_completion_once(self):
  from unittest.mock import patch
  self.setup_group()
  perform(self.coach,'payment',dict(player=20,hours=2,amount='100',date=datetime.now(TZ).date().isoformat(),payer='Player',nonce='end-test'))
  session=perform(self.coach,'view',{})['sessions'][0]
  expected=datetime.fromisoformat(session['date']+'T19:00:00+05:00').timestamp()
  self.assertEqual(session['begins'],expected)
  self.assertEqual(session['ends'],expected+3600)
  with patch('backend.crm.time.time',return_value=session['ends']-0.001):
   self.assertEqual(perform(self.coach,'view',{})['sessions'][0]['status'],'scheduled')
  with patch('backend.crm.time.time',return_value=session['ends']):
   for user in [self.coach,self.player,self.coach]:
    refreshed=perform(user,'view',{})
    self.assertEqual(refreshed['sessions'][0]['status'],'completed')
    self.assertEqual(refreshed['students'][0]['hours'],1)
  with connect() as db:
   persisted=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data'])
   self.assertEqual(persisted['sessions'][0]['status'],'completed')
   messages=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM outbox').fetchall()]
   self.assertEqual(sum('завершена' in m.get('text','') for m in messages),2)

 def test_duration_and_multiple_groups(self):
  gid=self.setup_group()
  original=perform(self.coach,'view',{})['groups'][0]
  for minutes in [30,60,90,120]:
   data={k:original[k] for k in ['name','place','start','end','days','time','type']}
   data.update(durationMinutes=minutes,members=[20,20])
   result=perform(self.coach,'group',data);g=result['groups'][-1]
   self.assertEqual(g['members'],[20]);self.assertEqual(g['durationMinutes'],minutes)
   sessions=[s for s in result['sessions'] if s['group']==g['id']]
   self.assertTrue(sessions)
   self.assertTrue(all(s['ends']-s['begins']==minutes*60 for s in sessions))
  self.assertEqual(len(perform(self.coach,'view',{})['students']),1)
  self.assertEqual(len(perform(self.player,'view',{})['groups']),5)
  perform(self.coach,'assign',dict(id=gid,player=20))
  self.assertEqual(perform(self.coach,'view',{})['groups'][0]['members'],[20])
  for value in [0,1441,-30,True,'90',None]:
   with self.assertRaises(ValueError):perform(self.coach,'edit_group',dict(id=gid,durationMinutes=value))
  with self.assertRaises(ValueError):perform(self.other,'edit_group',dict(id=gid,durationMinutes=90))
  with self.assertRaises(ValueError):perform(self.coach,'edit_group',dict(id=gid,members=[30]))

 def test_edit_duration_preserves_started_and_history(self):
  from unittest.mock import patch
  gid=self.setup_group();s=perform(self.coach,'view',{})['sessions'][0]
  future=perform(self.coach,'edit_group',dict(id=gid,durationMinutes=90))['sessions'][0]
  self.assertEqual(future['ends'],s['begins']+5400)
  with patch('backend.crm.time.time',return_value=s['begins']):
   result=perform(self.coach,'edit_group',dict(id=gid,durationMinutes=120))
   self.assertEqual(result['groups'][0]['durationMinutes'],120)
   self.assertEqual(result['sessions'][0]['ends'],future['ends'])
  with patch('backend.crm.time.time',return_value=future['ends']):
   result=perform(self.coach,'edit_group',dict(id=gid,durationMinutes=30))
   self.assertEqual(result['sessions'][0]['status'],'completed')
   self.assertEqual(result['sessions'][0]['ends'],future['ends'])

 def test_legacy_duration_migration_is_idempotent(self):
  self.setup_group()
  with connect() as db:
   state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data'])
   for g in state['groups']:g.pop('durationMinutes',None)
   for s in state['sessions']:s.pop('durationMinutes',None)
   db.execute('UPDATE crm SET data=? WHERE id=1',(json.dumps(state),))
   db.execute('DELETE FROM migrations WHERE id=?',('group-duration-v1',))
  initialize();initialize()
  view=perform(self.coach,'view',{})
  self.assertEqual(view['groups'][0]['durationMinutes'],60)
  self.assertEqual(view['sessions'][0]['durationMinutes'],60)

 def test_edit_adds_existing_student_and_individual_limit(self):
  self.setup_group();original=perform(self.coach,'view',{})['groups'][0]
  data={k:original[k] for k in ['name','place','start','end','days','time']}
  data.update(type='Индивидуальная',durationMinutes=30)
  g=perform(self.coach,'group',data)['groups'][-1]
  result=perform(self.coach,'edit_group',dict(id=g['id'],members=[20,20]))
  self.assertEqual(result['groups'][-1]['members'],[20])
  self.assertEqual([s for s in result['sessions'] if s['group']==g['id']][0]['members'],[20])
  other_player=dict(self.player,telegramId=40)
  with connect() as db:save_user(db,other_player)
  perform(other_player,'request',dict(coach=10))
  r=perform(self.coach,'view',{})['requests'][-1]
  perform(self.coach,'decision',dict(id=r['id'],status='accepted'))
  with self.assertRaises(ValueError):perform(self.coach,'edit_group',dict(id=g['id'],members=[40]))
  self.assertEqual(perform(self.coach,'view',{})['groups'][-1]['members'],[20])

 def test_five_minute_completion_and_exact_minute_billing(self):
  from unittest.mock import patch
  gid=self.setup_group()
  perform(self.coach,'payment',dict(player=20,hours=1,amount='100',date=datetime.now(TZ).date().isoformat(),payer='Player',nonce='five'))
  s=perform(self.coach,'edit_group',dict(id=gid,durationMinutes=5))['sessions'][0]
  self.assertEqual(s['ends']-s['begins'],300)
  with patch('backend.crm.time.time',return_value=s['ends']-1):
   self.assertEqual(perform(self.coach,'view',{})['sessions'][0]['status'],'scheduled')
  with patch('backend.crm.time.time',return_value=s['ends']):
   for _ in range(2):
    view=perform(self.coach,'view',{})
    self.assertEqual(view['sessions'][0]['status'],'completed')
    self.assertEqual(round(view['students'][0]['hours']*60),55)
    self.assertEqual(view['sessions'][0]['charges'][0]['minutes'],5)

 def test_duration_billing_absence_insufficient_and_no_rounding_drift(self):
  gid=self.setup_group()
  with connect() as db:
   state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data'])
   original=state['sessions'][0];state['groups']=[];state['balances']['10:20']=1
   for i in range(12):
    s=dict(original,id=str(i),status='scheduled',begins=1000,ends=1300)
    state['sessions']=[s];tick(state,db,1300)
    self.assertEqual(round(state['balances']['10:20']*60),55-i*5)
   for minutes,balance,absent,expected in [(90,2,[],30),(120,0.5,[],0),(5,1,[20],60)]:
    state['balances']['10:20']=balance
    state['sessions']=[dict(original,status='scheduled',begins=1000,ends=1000+minutes*60,absent=absent)]
    tick(state,db,1000+minutes*60)
    self.assertEqual(round(state['balances']['10:20']*60),expected)
