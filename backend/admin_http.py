"""Admin HTTP boundary; all CRM reads require a server-side session."""
import hmac
import json
import urllib.parse
from pathlib import Path
from . import admin, admin_auth
from .database import connect

ROOT=Path(__file__).resolve().parents[1]/'admin'

def respond(handler,status,body,content_type='application/json; charset=utf-8',cookie=None,extra=None):
    if not isinstance(body,bytes): body=json.dumps(body,ensure_ascii=False).encode()
    handler.send_response(status)
    for key,value in {'Content-Type':content_type,'Content-Length':str(len(body)), 'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",**(extra or {})}.items(): handler.send_header(key,value)
    if cookie: handler.send_header('Set-Cookie',cookie)
    handler.end_headers(); handler.wfile.write(body)

def handle(handler):
    route=urllib.parse.urlsplit(handler.path); path=route.path
    if not (path=='/admin' or path.startswith('/admin/') or path.startswith('/api/admin/')): return False
    try:
        account=admin_auth.session(handler.headers)
        if path in ('/admin/admin.css','/admin/admin.js') and handler.command=='GET':
            asset=path.rsplit('/',1)[-1]
            respond(handler,200,(ROOT/asset).read_bytes(),'text/css' if asset.endswith('.css') else 'text/javascript'); return True
        if path=='/admin' or path.startswith('/admin/'):
            if handler.command!='GET': respond(handler,405,{'error':'Method not allowed'}); return True
            if not account and path!='/admin/login':
                respond(handler,302,b'',extra={'Location':'/admin/login'}); return True
            respond(handler,200,(ROOT/'index.html').read_bytes(),'text/html; charset=utf-8'); return True
        if handler.command=='POST':
            origin=handler.headers.get('Origin')
            if origin and urllib.parse.urlsplit(origin).netloc!=handler.headers.get('Host'):
                respond(handler,403,{'error':'Недопустимый источник запроса'}); return True
            if handler.headers.get('Content-Type','').split(';')[0]!='application/json':
                respond(handler,415,{'error':'JSON required'}); return True
            size=int(handler.headers.get('Content-Length',0))
            if not 0<size<=16384: raise ValueError('Некорректный размер запроса')
            payload=json.loads(handler.rfile.read(size))
            if not isinstance(payload,dict): raise ValueError('JSON object required')
            if path=='/api/admin/login':
                # Do not trust spoofable forwarded IP headers. Proxy deployments share a limit.
                result,status=admin_auth.login(payload.get('username'),payload.get('password'),handler.client_address[0])
                respond(handler,status,{'username':result['username'],'csrf':result['csrf']} if result else {'error':'Слишком много попыток. Повторите через 15 минут.' if status==429 else 'Неверный логин или пароль'},cookie=admin_auth.cookie(result['token']) if result else None)
                return True
        if not account:
            respond(handler,401,{'error':'Войдите в кабинет'}); return True
        query={k:v[-1] for k,v in urllib.parse.parse_qs(route.query).items()}
        if handler.command=='GET':
            if path=='/api/admin/me': result={k:account[k] for k in ('username','csrf')}
            elif path=='/api/admin/dashboard': result=admin.dashboard(query)
            elif path=='/api/admin/options':
                data=admin.snapshot()
                result=dict(cities=admin.CITIES,clubs=data['clubs'],coaches=[{'id':u['id'],'name':u['fullName']} for u in data['coaches']])
            elif path=='/api/admin/report':
                resource=query.get('resource','finance')
                if resource not in admin.RESOURCES: raise ValueError('Неизвестный отчёт')
                respond(handler,200,admin.report(resource,query),'text/csv; charset=utf-8',extra={'Content-Disposition':f'attachment; filename="topcoach-{resource}.csv"'}); return True
            elif path.removeprefix('/api/admin/') in admin.RESOURCES: result=admin.listing(path.rsplit('/',1)[-1],query)
            else: respond(handler,404,{'error':'Not found'}); return True
            respond(handler,200,result); return True
        if handler.command=='POST':
            if not hmac.compare_digest(handler.headers.get('X-CSRF-Token',''),account['csrf']):
                respond(handler,403,{'error':'Обновите страницу и повторите'}); return True
            if path=='/api/admin/logout':
                with connect() as db: db.execute('DELETE FROM admin_sessions WHERE token=?',(account['token'],))
                respond(handler,200,{'ok':True},cookie=admin_auth.cookie('',True)); return True
            if path.rsplit('/',1)[-1] in ('clubs','courts'):
                try: result=admin.mutate(path.rsplit('/',1)[-1],payload,account['username'])
                except ValueError as error:
                    respond(handler,400,{'error':str(error)}); return True
                respond(handler,200,result); return True
        respond(handler,404,{'error':'Not found'})
    except (ValueError,TypeError,KeyError,OverflowError):
        respond(handler,400,{'error':'Проверьте поля запроса и выбранный период'})
    except Exception:
        respond(handler,500,{'error':'Не удалось выполнить запрос. Повторите позже.'})
    return True
