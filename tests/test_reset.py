import json,os,tempfile,unittest
from pathlib import Path
from backend.database import initialize,connect
from backend.reset_test_data import reset
class ResetTests(unittest.TestCase):
 def test_preview_backup_and_reset(self):
  with tempfile.TemporaryDirectory() as temp:
   os.environ['DB_PATH']=temp+'/db';initialize()
   with connect() as db:
    db.execute('INSERT INTO users VALUES (?,?)',(12,json.dumps({'fullName':'Test','role':'player'})))
    db.execute('INSERT INTO updates VALUES (?,?)',(44,123))
    db.execute('INSERT INTO outbox(method,payload) VALUES (?,?)',('sendMessage','{}'))
   reset(False,temp)
   with connect() as db:self.assertIsNotNone(db.execute('SELECT * FROM users').fetchone())
   backup=reset(True,temp)
   self.assertEqual(len(json.loads(Path(backup).read_text())['users']),1)
   with connect() as db:
    self.assertIsNone(db.execute('SELECT * FROM users').fetchone())
    self.assertIsNone(db.execute('SELECT * FROM outbox').fetchone())
    self.assertIsNotNone(db.execute('SELECT * FROM updates').fetchone())
    self.assertIsNotNone(db.execute('SELECT * FROM migrations WHERE id=?',('sqlite-users-v1',)).fetchone())
