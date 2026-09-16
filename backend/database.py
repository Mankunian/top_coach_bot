"""PostgreSQL in production, SQLite for local tests; serialized CRM transactions."""
import os, sqlite3, json
from pathlib import Path

class Database:
    def __init__(self):
        self.pg=bool(os.getenv('DATABASE_URL'))
        if self.pg:
            import psycopg
            from psycopg.rows import dict_row
            self.db=psycopg.connect(os.environ['DATABASE_URL'],row_factory=dict_row)
        else:
            path=Path(os.getenv('DB_PATH','.data/topcoach.sqlite3'));path.parent.mkdir(parents=True,exist_ok=True)
            self.db=sqlite3.connect(path,timeout=30);self.db.row_factory=sqlite3.Row
    def execute(self,sql,args=()):
        if self.pg:
            if sql=='BEGIN IMMEDIATE':
                return self.db.execute('SELECT pg_advisory_xact_lock(734981)')
            sql=sql.replace('?', '%s')
        return self.db.execute(sql,args)
    def __enter__(self):return self
    def __exit__(self,t,v,tb):
        try:self.db.rollback() if t else self.db.commit()
        finally:self.db.close()

def connect():return Database()

def initialize():
    with connect() as db:
        serial='BIGSERIAL PRIMARY KEY' if db.pg else 'INTEGER PRIMARY KEY AUTOINCREMENT'
        db.execute('CREATE TABLE IF NOT EXISTS users (telegram_id BIGINT PRIMARY KEY, data TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS updates (id BIGINT PRIMARY KEY, created BIGINT NOT NULL)')
        db.execute(f'CREATE TABLE IF NOT EXISTS outbox (id {serial}, method TEXT NOT NULL,payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0)')
        db.execute('CREATE TABLE IF NOT EXISTS crm (id INTEGER PRIMARY KEY,data TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS migrations (id TEXT PRIMARY KEY)')
        db.execute('INSERT INTO crm VALUES (1,?) ON CONFLICT(id) DO NOTHING',(json.dumps(dict(requests=[],groups=[],sessions=[],payments=[],balances={},comments={})),))
        path=Path(os.getenv('DB_PATH','.data/topcoach.sqlite3'))
        if db.pg and path.exists():
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT id FROM migrations WHERE id=?',('sqlite-users-v1',)).fetchone():
                old=sqlite3.connect(path)
                try:
                    for uid,data in old.execute('SELECT telegram_id,data FROM users'):
                        db.execute('INSERT INTO users VALUES (?,?) ON CONFLICT(telegram_id) DO NOTHING',(uid,data))
                    db.execute('INSERT INTO migrations VALUES (?)',('sqlite-users-v1',))
                finally:old.close()
