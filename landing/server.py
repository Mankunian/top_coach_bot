import functools
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __name__ == '__main__':
    handler=functools.partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).parent/'public'))
    ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT','4181'))),handler).serve_forever()
