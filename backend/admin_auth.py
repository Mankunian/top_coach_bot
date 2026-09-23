"""Independent, persistent administrator authentication. No Telegram credentials."""
import hashlib
import hmac
import os
import secrets
import time
from http.cookies import SimpleCookie
from .database import connect

COOKIE = 'topcoach_admin'
TTL = 8 * 3600

def digest(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 310000).hex()

def seed():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS admin_accounts (username TEXT PRIMARY KEY, salt TEXT NOT NULL, hash TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS admin_sessions (token TEXT PRIMARY KEY, username TEXT NOT NULL, csrf TEXT NOT NULL, expires BIGINT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS admin_attempts (address TEXT PRIMARY KEY, attempts INTEGER NOT NULL, expires BIGINT NOT NULL)')
        username, password = os.getenv('ADMIN_USERNAME', '').strip(), os.getenv('ADMIN_PASSWORD', '')
        if username and password:
            if len(password) < 14:
                raise ValueError('ADMIN_PASSWORD must contain at least 14 characters')
            row = db.execute('SELECT * FROM admin_accounts WHERE username=?', (username,)).fetchone()
            if not row or not hmac.compare_digest(row['hash'], digest(password, row['salt'])):
                salt = secrets.token_hex(16)
                db.execute('INSERT INTO admin_accounts VALUES (?,?,?) ON CONFLICT(username) DO UPDATE SET salt=excluded.salt, hash=excluded.hash', (username, salt, digest(password, salt)))
                db.execute('DELETE FROM admin_sessions WHERE username=?', (username,))

def login(username, password, address):
    if not isinstance(username, str) or not isinstance(password, str) or len(password)>1024:
        raise ValueError('Неверный логин или пароль')
    now = int(time.time())
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM admin_attempts WHERE expires<=?', (now,))
        db.execute('DELETE FROM admin_sessions WHERE expires<=?', (now,))
        attempt = db.execute('SELECT * FROM admin_attempts WHERE address=?', (address,)).fetchone()
        if attempt and attempt['attempts'] >= 10:
            return None, 429
        row = db.execute('SELECT * FROM admin_accounts WHERE username=?', (username,)).fetchone()
        actual = digest(password, row['salt'] if row else '00'*16)
        if not row or not hmac.compare_digest(row['hash'], actual):
            db.execute('INSERT INTO admin_attempts VALUES (?,1,?) ON CONFLICT(address) DO UPDATE SET attempts=admin_attempts.attempts+1', (address, now+900))
            return None, 401
        db.execute('DELETE FROM admin_attempts WHERE address=?', (address,))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.execute('INSERT INTO admin_sessions VALUES (?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), username, csrf, now+TTL))
        return dict(token=token, csrf=csrf, username=username), 200

def session(headers):
    cookie = SimpleCookie()
    try: cookie.load(headers.get('Cookie', ''))
    except Exception: return None
    if COOKIE not in cookie: return None
    token = hashlib.sha256(cookie[COOKIE].value.encode()).hexdigest()
    with connect() as db:
        row = db.execute('SELECT * FROM admin_sessions WHERE token=? AND expires>?', (token, int(time.time()))).fetchone()
    return dict(row) if row else None

def cookie(value, expired=False):
    secure = os.getenv('ADMIN_COOKIE_SECURE', 'true').lower() != 'false'
    return f'{COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if expired else TTL}' + ('; Secure' if secure else '')

if __name__ == '__main__':
    from .database import initialize
    initialize()
    seed()
    print('Admin schema initialized; env account seeded if supplied.')
