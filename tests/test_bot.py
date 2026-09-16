import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
import urllib.parse
from backend.catalog import cities, venues
from backend.service import authenticate, connect, process_update, read_user

class BotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ['DB_PATH'] = self.temp.name + '/test.sqlite3'
        self.number = 0

    def tearDown(self):
        self.temp.cleanup()

    def update(self, text=None, callback=None, user=101):
        self.number += 1
        sender = {'id': user, 'first_name': 'Анна', 'last_name': 'Иванова'}
        message = {'from': sender, 'chat': {'id': user, 'type': 'private'}}
        data = {'update_id': self.number}
        if callback:
            data['callback_query'] = {'id': str(self.number), 'from': sender, 'data': callback, 'message': message}
        else:
            message['text'] = text
            data['message'] = message
        process_update(data)
        return data

    def test_all_roles_and_dedup(self):
        for i, role in enumerate(['coach', 'player', 'parent']):
            uid = i + 1
            self.update('/start', user=uid)
            self.update(callback='register', user=uid)
            self.update(callback='role:' + role, user=uid)
            self.update(callback='city:' + cities()[0]['id'], user=uid)
            event = self.update(callback='venue:' + venues(cities()[0]['id'])[0]['id'], user=uid)
            with connect() as db:
                user = read_user(db, uid)
                count = db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]
            self.assertEqual(user['step'], 'done')
            self.assertEqual(user['fullName'], 'Анна Иванова')
            process_update(event)
            with connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0], count)

    def test_invalid_city_and_venue(self):
        self.update('/start'); self.update(callback='register'); self.update(callback='role:player')
        self.update(callback='city:forged')
        with connect() as db:
            self.assertEqual(read_user(db, 101)['step'], 'city')
        self.update(callback='city:' + cities()[1]['id'])
        self.update(callback='venue:1')
        with connect() as db:
            self.assertEqual(read_user(db, 101)['step'], 'venue')
        self.update(callback='venue:skip')
        with connect() as db:
            self.assertEqual(read_user(db, 101)['step'], 'done')

    def test_custom_venue(self):
        self.update('/start'); self.update(callback='register'); self.update(callback='role:coach')
        self.update(callback='city:' + cities()[1]['id']); self.update(callback='venue:custom')
        self.update('Мой корт, ул. Абая, 10')
        with connect() as db:
            self.assertEqual(read_user(db, 101)['customVenue'], 'Мой корт, ул. Абая, 10')

    def test_signed_init_data(self):
        token = 'test-token'
        fields = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': 101})}
        check = '\n'.join(k + '=' + v for k, v in sorted(fields.items()))
        secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
        fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(authenticate(urllib.parse.urlencode(fields), token), 101)
        fields['user'] = json.dumps({'id': 999})
        with self.assertRaises(ValueError):
            authenticate(urllib.parse.urlencode(fields), token)

if __name__ == '__main__':
    unittest.main()
