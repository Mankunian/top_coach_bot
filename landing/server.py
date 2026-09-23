import functools
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path in ('/admin','/admin/'):
            target=os.getenv('ADMIN_URL','' if os.getenv('RAILWAY_ENVIRONMENT') else 'http://127.0.0.1:8080/admin')
            parsed=urlsplit(target)
            if parsed.scheme not in ('http','https') or not parsed.netloc or any(c in target for c in '\r\n'):
                self.send_error(503,'Admin URL is not configured'); return
            self.send_response(302); self.send_header('Location',target); self.send_header('Cache-Control','no-store'); self.end_headers(); return
        super().do_GET()

if __name__ == '__main__':
    handler=functools.partial(Handler,directory=str(Path(__file__).parent/'public'))
    ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT','4181'))),handler).serve_forever()
