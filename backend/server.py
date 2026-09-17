import functools
import hmac
import json
import os
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .catalog import cities, venues
from .database import initialize
from .crm import perform
from .service import authenticate, connect, flush_outbox, process_update, read_user, save_user

ROOT = Path(__file__).resolve().parents[1] / 'dist'

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, format, *args):
        # No request bodies or auth headers in logs.
        pass

    def result(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def user(self):
        token = os.environ.get('BOT_TOKEN', '')
        if not token:
            raise ValueError('Not configured')
        uid = authenticate(self.headers.get('X-Telegram-Init-Data', ''), token)
        with connect() as db:
            user = read_user(db, uid)
        if not user or user['step'] != 'done':
            raise ValueError('Registration required')
        return user

    def do_GET(self):
        route = urllib.parse.urlparse(self.path)
        if route.path == '/health':
            with connect() as db:
                db.execute('SELECT 1')
            return self.result(200, {'status': 'ok', 'version':'crm-5', 'database':'postgresql' if db.pg else 'sqlite'})
        if route.path == '/api/cities':
            return self.result(200, cities())
        if route.path == '/api/venues':
            city_id = urllib.parse.parse_qs(route.query).get('cityId', [''])[0]
            if not any(c['id'] == city_id for c in cities()):
                return self.result(400, {'error': 'Unknown city'})
            return self.result(200, venues(city_id))
        if route.path == '/api/state':
            try:
                return self.result(200, perform(self.user(), 'view', {}))
            except (ValueError, KeyError, TypeError):
                return self.result(401, {'error':'Откройте приложение из бота после регистрации.'})
        if route.path == '/api/me':
            try:
                return self.result(200, self.user())
            except (ValueError, KeyError, TypeError):
                return self.result(401, {'error': 'Откройте Mini App из бота после регистрации.'})
        if route.path.startswith('/api/'):
            return self.result(404, {'error': 'Not found'})
        if route.path in ['/', '/index.html']:
            self.path='/mini.html'
        if route.path == '/app.js':
            return self.result(404, {'error':'Demo assets are not served by the production API'})
        return super().do_GET()

    def do_POST(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 65536:
                return self.result(413, {'error': 'Invalid body size'})
            if self.path == '/telegram/webhook':
                expected = os.environ.get('WEBHOOK_SECRET', '')
                supplied = self.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
                if not expected or not hmac.compare_digest(expected, supplied):
                    return self.result(403, {'error': 'Forbidden'})
                process_update(json.loads(self.rfile.read(size)))
                return self.result(200, {'ok': True})
            if self.path == '/api/action':
                try:
                    user = self.user()
                except (ValueError, KeyError, TypeError):
                    return self.result(401, {'error':'Откройте приложение заново из бота.'})
                data = json.loads(self.rfile.read(size))
                return self.result(200, perform(user, data.get('action'), data))
            if self.path == '/api/me':
                try:
                    user = self.user()
                except (ValueError, KeyError, TypeError):
                    return self.result(401, {'error': 'Откройте приложение заново из бота.'})
                data = json.loads(self.rfile.read(size))
                name, bio = data.get('fullName'), data.get('bio')
                if not isinstance(name, str) or not name.strip() or len(name) > 120 or not isinstance(bio, str) or len(bio) > 1000:
                    return self.result(400, {'error': 'Проверьте ФИО и описание.'})
                city=next((c for c in cities() if c['id']==data.get('cityId',user.get('cityId'))),None)
                if not city: return self.result(400, {'error':'Выберите город'})
                changed=city['id']!=user.get('cityId')
                venue_id=data.get('venueId')
                selected=next((v for v in venues(city['id']) if v['id']==venue_id),None) if venue_id else None
                if venue_id and not selected:return self.result(400, {'error':'Корт не относится к выбранному городу'})
                user.update(fullName=name.strip(),bio=bio.strip(),cityId=city['id'],cityCode=city['code'],city=city['name'])
                if user.get('role')=='coach':
                    user.update(venueId=venue_id or None,venue=selected['name'] if selected else str(data.get('venue','' if changed else user.get('venue','')))[:250],address=selected['address'] if selected else str(data.get('address','' if changed else user.get('address','')))[:250])
                    user.pop('customVenue',None)
                with connect() as db:
                    save_user(db, user)
                return self.result(200, user)
            return self.result(404, {'error': 'Not found'})
        except (ValueError, KeyError, TypeError) as error:
            return self.result(400, {'error': str(error) if isinstance(error,ValueError) else 'Проверьте данные запроса'})
        except Exception:
            return self.result(500, {'error': 'Server error'})

def delivery_worker():
    while True:
        try:
            flush_outbox()
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                from .crm import tick
                state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data'])
                tick(state,db)
                db.execute('UPDATE crm SET data=? WHERE id=1',(json.dumps(state,ensure_ascii=False),))
        except Exception:
            print('Delivery worker unavailable; retrying', flush=True)
        time.sleep(3)

if __name__ == '__main__':
    if os.environ.get('RAILWAY_ENVIRONMENT') and not os.environ.get('DATABASE_URL') and not os.environ.get('DB_PATH', '').startswith('/data/'):
        raise SystemExit('Railway requires persistent volume /data and DB_PATH=/data/topcoach.sqlite3')
    initialize()
    if os.environ.get('BOT_TOKEN'):
        threading.Thread(target=delivery_worker, daemon=True).start()
    port = int(os.environ.get('PORT', '8080'))
    print(f'TopCoach API listening on port {port}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), functools.partial(Handler, directory=str(ROOT))).serve_forever()
