"""Operator-only reset, never exposed through HTTP. Run inside Railway Console."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .database import connect

EMPTY = dict(requests=[], groups=[], sessions=[], payments=[], balances={}, comments={}, names={})

def reset(execute=False, backup_dir='/data/backups'):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        users=[dict(r) for r in db.execute('SELECT telegram_id,data FROM users').fetchall()]
        row=db.execute('SELECT data FROM crm WHERE id=1').fetchone()
        state=json.loads(row['data']) if row else EMPTY
        summary={key:len(state.get(key,[])) for key in ['requests','groups','sessions','payments']}
        summary['users']=len(users)
        print(json.dumps(summary,ensure_ascii=False))
        if not execute:
            for u in users:
                data=json.loads(u['data'])
                print(f"{u['telegram_id']} | {data.get('role','')} | {data.get('fullName','')}")
            print('Preview only. No changes made.')
            return None
        # Abort before any deletion if backup cannot be written.
        directory=Path(backup_dir);directory.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup=directory/f'topcoach-before-reset-{stamp}.json'
        outbox=[dict(r) for r in db.execute('SELECT * FROM outbox').fetchall()]
        with backup.open('x',encoding='utf-8') as output:
            os.chmod(backup,0o600)
            json.dump({'users':users,'crm':state,'outbox':outbox},output,ensure_ascii=False)
            output.flush();os.fsync(output.fileno())
        db.execute('DELETE FROM outbox')
        db.execute('DELETE FROM users')
        db.execute('UPDATE crm SET data=? WHERE id=1',(json.dumps(EMPTY),))
        # Keep incoming update deduplication and prevent legacy SQLite resurrection.
        db.execute('INSERT INTO migrations VALUES (?) ON CONFLICT(id) DO NOTHING',('sqlite-users-v1',))
    print(f'Reset complete. Backup: {backup}. Send /start in the bot to register again.')
    return backup

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Reset all test accounts and CRM data with backup')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--backup-dir',default='/data/backups')
    args=parser.parse_args()
    reset(args.execute,args.backup_dir)
