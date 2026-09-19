import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from .catalog import cities, venues
from .i18n import tr

WELCOME = ('🎾 Добро пожаловать в TopCoach!\n\n'
           'Больше тенниса — меньше рутины.\n\n'
           '🧑‍🏫 Тренеру — ученики, группы, расписание и учёт оплат в одном месте.\n'
           '🎾 Игроку — связь с тренером, ближайшие занятия и остаток часов.\n'
           '👨‍👩‍👧 Родителю — занятия ребёнка под рукой.\n\n'
           'Начнём с короткой регистрации?')

from .database import connect

def keyboard(rows):
    return {'inline_keyboard': [[{'text': text, 'callback_data': data} for text, data in row] for row in rows]}

def read_user(db, telegram_id):
    row = db.execute('SELECT data FROM users WHERE telegram_id=?', (telegram_id,)).fetchone()
    return json.loads(row['data']) if row else None

def save_user(db, user):
    db.execute('INSERT INTO users VALUES (?,?) ON CONFLICT(telegram_id) DO UPDATE SET data=excluded.data',
               (user['telegramId'], json.dumps(user, ensure_ascii=False)))

def enqueue(db, method, payload):
    db.execute('INSERT INTO outbox(method,payload) VALUES (?,?)', (method, json.dumps(payload, ensure_ascii=False)))

def send(db, chat_id, text, markup=None):
    payload = {'chat_id': chat_id, 'text': text}
    if markup:
        payload['reply_markup'] = markup
    enqueue(db, 'sendMessage', payload)

def show_cities(db, user):
    send(db, user['telegramId'], '📍 В каком городе вы занимаетесь?',
         keyboard([[(c['code'] + ' · ' + c['name'], 'city:' + c['id'])] for c in cities()]))

def show_venues(db, user):
    rows = [[(v['name'] + ' · ' + v['address'], 'venue:' + v['id'])] for v in venues(user['cityId'])]
    rows += [[('✍️ Указать свою площадку', 'venue:custom')], [('Позже', 'venue:skip')]]
    send(db, user['telegramId'], '🏟 Выберите клуб или корт. Если его пока нет в списке, укажите свой или заполните позже в Mini App.', keyboard(rows))

def finish(db, user):
    user['step'] = 'done'
    user.setdefault('registeredAt', int(time.time()))
    url = os.environ.get('MINI_APP_URL', '')
    lang=user.get('language','ru')
    markup = {'inline_keyboard': [[{'text': tr(lang,'bot.open'), 'web_app': {'url': url}}]]} if url.startswith('https://') else None
    send(db,user['telegramId'],tr(lang,'bot.ready',name=user['fullName']),markup)

def process_update(update):
    if not isinstance(update, dict) or not isinstance(update.get('update_id'), int):
        raise ValueError('Invalid update')
    callback = update.get('callback_query')
    message = callback.get('message', {}) if callback else update.get('message', {})
    sender = callback.get('from', {}) if callback else message.get('from', {})
    if message.get('chat', {}).get('type') != 'private' or not isinstance(sender.get('id'), int):
        return
    uid = sender['id']
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM updates WHERE id=?', (update['update_id'],)).fetchone():
            return
        user = read_user(db, uid) or {'id': str(uuid.uuid4()), 'telegramId': uid, 'fullName': ' '.join(filter(None, [sender.get('first_name'), sender.get('last_name')])) or 'Player', 'username': sender.get('username'), 'step': 'welcome', 'bio': '', 'language': 'en'}
        data = callback.get('data', '') if callback else ''
        text = message.get('text', '')
        if callback:
            enqueue(db, 'answerCallbackQuery', {'callback_query_id': callback['id']})
        if text.split(' ')[0] == '/start':
            if user['step'] == 'done':
                finish(db, user)
            else:
                send(db, uid, WELCOME, keyboard([[('🚀 Пройти регистрацию', 'register')]]))
        elif data == 'register' and user['step'] != 'done':
            user['step'] = 'role'
            send(db, uid, '👋 Как вы будете пользоваться TopCoach?\n\nИмя возьмём из вашего Telegram-профиля. Его можно будет уточнить в Mini App.',
                 keyboard([[('🧑‍🏫 Я тренер', 'role:coach')], [('🎾 Я игрок', 'role:player')], [('👨‍👩‍👧 Я родитель', 'role:parent')]]))
        elif data.startswith('role:') and user['step'] == 'role' and data[5:] in ['coach', 'player', 'parent']:
            user['role'] = data[5:]
            user['step'] = 'city'
            show_cities(db, user)
        elif data.startswith('city:') and user['step'] == 'city':
            city = next((c for c in cities() if c['id'] == data[5:]), None)
            if city:
                user.update(cityId=city['id'], cityCode=city['code'], city=city['name'], step='venue')
                if user['role']=='coach':
                    show_venues(db, user)
                else:
                    user['venueId']=None
                    finish(db, user)
        elif data.startswith('venue:') and user['step'] == 'venue':
            value = data[6:]
            if value == 'custom':
                user['step'] = 'custom_venue'
                send(db, uid, '✍️ Напишите название клуба или корта и адрес одним сообщением.\n\nНапример: «Открытый корт, ул. Абая, 10».', keyboard([[('Заполнить позже', 'skip')]]))
            elif value == 'skip':
                user['venueId'] = None
                finish(db, user)
            else:
                venue = next((v for v in venues(user['cityId']) if v['id'] == value), None)
                if venue:
                    user.update(venueId=venue['id'], venue=venue['name'], address=venue['address'])
                    finish(db, user)
        elif data == 'skip' and user['step'] == 'custom_venue':
            user['venueId'] = None
            finish(db, user)
        elif text and user['step'] == 'custom_venue' and not text.startswith('/'):
            if len(text.strip()) > 250:
                send(db, uid, 'Пожалуйста, сократите название и адрес до 250 символов.')
            else:
                user.update(venueId=None, customVenue=text.strip())
                finish(db, user)
        else:
            send(db, uid, tr(user.get('language','ru'),'bot.menu'))
        save_user(db, user)
        db.execute('INSERT INTO updates VALUES (?,?)', (update['update_id'], int(time.time())))

def telegram(method, payload):
    token = os.environ.get('BOT_TOKEN')
    if not token:
        raise RuntimeError('BOT_TOKEN not configured')
    req = urllib.request.Request('https://api.telegram.org/bot' + token + '/' + method,
                                 data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError('Telegram request failed')
    return result['result']

def flush_outbox():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute('SELECT * FROM outbox WHERE sent=0 AND attempts<10 ORDER BY id LIMIT 20').fetchall()
        for row in rows:
            try:
                telegram(row['method'], json.loads(row['payload']))
                db.execute('UPDATE outbox SET sent=1 WHERE id=?', (row['id'],))
            except Exception:
                db.execute('UPDATE outbox SET attempts=attempts+1 WHERE id=?', (row['id'],))
                # Do not log exception URLs: they may contain the token.
                print('Telegram delivery failed; queued for retry', flush=True)
                break

def authenticate(init_data, token):
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    values = dict(pairs)
    if len(pairs) != len(values):
        raise ValueError('Duplicate fields')
    supplied = values.pop('hash', '')
    check = '\n'.join(k + '=' + v for k, v in sorted(values.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ValueError('Invalid signature')
    age = time.time() - int(values.get('auth_date', '0'))
    if age < -30 or age > 3600:
        raise ValueError('Expired auth')
    return json.loads(values['user'])['id']
