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
  p=perform(self.player,'view',{});self.assertEqual(p['students'][0]['hours'],5);self.assertEqual(p['payments'],[])
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
