import os
import tempfile
import unittest
from unittest.mock import patch
from backend.database import initialize
from backend import admin_auth as auth

class AdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ, DB_PATH=self.tmp.name+'/db', ADMIN_USERNAME='owner', ADMIN_PASSWORD='a-long-test-password')
        self.env.start(); initialize(); auth.seed()
    def tearDown(self):
        self.env.stop(); self.tmp.cleanup()
    def test_login_session_rotation(self):
        result,status=auth.login('owner','a-long-test-password','local')
        self.assertEqual(status,200)
        headers={'Cookie':auth.COOKIE+'='+result['token']}
        self.assertEqual(auth.session(headers)['username'],'owner')
        self.assertIsNone(auth.session({'Cookie':auth.COOKIE+'=invalid'}))
        os.environ['ADMIN_PASSWORD']='another-long-password'; auth.seed()
        self.assertIsNone(auth.session(headers))
    def test_persistent_limit(self):
        for _ in range(10): self.assertEqual(auth.login('owner','bad','local')[1],401)
        self.assertEqual(auth.login('owner','a-long-test-password','local')[1],429)
    def test_period_totals_paging_and_report(self):
        import json
        from backend import admin
        from backend.database import connect
        admin.initialize()
        with connect() as db:
            state=json.loads(db.execute('SELECT data FROM crm WHERE id=1').fetchone()['data'])
            state['payments']=[dict(id='p1',date='2026-09-01',amount=12345,coach=1,player=2,payer='=HYPERLINK("bad")'),dict(id='p2',date='2026-08-31',amount=100,coach=1,player=2)]
            db.execute('UPDATE crm SET data=? WHERE id=1',(json.dumps(state),))
        q={'from':'2026-09-01','to':'2026-09-01'}
        self.assertEqual(admin.dashboard(q)['payments'],12345)
        self.assertEqual(admin.listing('finance',q)['total'],1)
        report=admin.report('finance',q).decode()
        self.assertIn('123.45',report); self.assertIn("'=HYPERLINK",report)
        with self.assertRaises(ValueError): admin.period({'from':'2026-09-02','to':'2026-09-01'})
    def test_directory_references_and_audit(self):
        from backend import admin
        from backend.database import connect
        admin.initialize()
        club=admin.mutate('clubs',{'operation':'create','data':{'name':'Test','cityId':admin.CITIES[0]['id'],'address':'Court street'}},'owner')['id']
        court=admin.mutate('courts',{'operation':'create','data':{'name':'Court 1','clubId':club,'surface':'Hard','status':'active'}},'owner')['id']
        with self.assertRaises(ValueError): admin.mutate('clubs',{'operation':'delete','id':club},'owner')
        admin.mutate('courts',{'operation':'update','id':court,'data':{'name':'Court 2'}},'owner')
        admin.mutate('courts',{'operation':'delete','id':court},'owner')
        admin.mutate('clubs',{'operation':'delete','id':club},'owner')
        with connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM admin_audit').fetchone()['n'],5)
    def test_http_security_boundary(self):
        import functools
        import json
        import threading
        import urllib.request
        import urllib.error
        from http.server import ThreadingHTTPServer
        from backend import admin
        from backend.server import Handler, ROOT
        admin.initialize()
        server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        def request(path,body=None,headers=None):
            req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
            try: response=urllib.request.urlopen(req)
            except urllib.error.HTTPError as e: response=e
            return response.status,response.headers,response.read()
        try:
            for resource in ('me','options','dashboard','coaches','players','groups','sessions','requests','finance','clubs','courts','report'):
                self.assertEqual(request('/api/admin/'+resource)[0],401)
            code,headers,body=request('/api/admin/login',{'username':'owner','password':'a-long-test-password'})
            self.assertEqual(code,200); self.assertIn('HttpOnly',headers['Set-Cookie']); self.assertIn('Secure',headers['Set-Cookie'])
            auth_headers={'Cookie':headers['Set-Cookie'].split(';')[0]}
            self.assertEqual(request('/api/admin/me',headers=auth_headers)[0],200)
            self.assertEqual(request('/api/admin/clubs',{'operation':'delete','id':'1'},auth_headers)[0],403)
            auth_headers['X-CSRF-Token']=json.loads(body)['csrf']
            self.assertEqual(request('/api/admin/logout',{},dict(auth_headers,Origin='https://evil.test'))[0],403)
            self.assertEqual(request('/api/admin/dashboard?from=bad',headers=auth_headers)[0],400)
            self.assertEqual(request('/api/admin/report?resource=finance',headers=auth_headers)[0],200)
            self.assertEqual(request('/api/admin/logout',{},auth_headers)[0],200)
            self.assertEqual(request('/api/admin/me',headers=auth_headers)[0],401)
            self.assertEqual(request('/health')[0],200)
            self.assertEqual(request('/mini.html')[0],200)
        finally:
            server.shutdown();server.server_close();thread.join()
    def test_catalog_reuses_directory(self):
        from backend import admin
        from backend.catalog import venues
        admin.initialize()
        city=admin.CITIES[0]['id']
        record=admin.mutate('clubs',{'operation':'create','data':{'name':'Shared catalog','cityId':city,'address':'Street'}},'owner')
        self.assertTrue(any(v['id']==record['id'] for v in venues(city)))
