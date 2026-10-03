"""Private capability-URL workbench, bound exclusively to IPv4 loopback."""
from __future__ import annotations
import base64
import binascii
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import webbrowser
from .engine import InputError,MAX_BYTES,safe_name
from .runner import JobManager

WEB=Path(__file__).resolve().parent.parent/'web'
FIXTURES=Path(__file__).resolve().parent.parent/'fixtures'
MAX_REQUEST=2*((MAX_BYTES+2)//3*4)+16384

class LocalServer(HTTPServer):
    def __init__(self,address):
        if address[0]!='127.0.0.1':raise InputError('Only IPv4 loopback binding is supported.')
        self.token=secrets.token_urlsafe(32);self.manager=JobManager()
        super().__init__(address,Handler)
    @property
    def url(self):return f'http://127.0.0.1:{self.server_port}/{self.token}/'
    def server_close(self):self.manager.close();super().server_close()

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*args):pass
    def setup(self):super().setup();self.connection.settimeout(10)
    def _send(self,status,body=b'',content_type='application/json',download=None):
        self.send_response(status)
        self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer');self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        if download:self.send_header('Content-Disposition',f'attachment; filename="{download}"')
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def _json(self,status,data):self._send(status,json.dumps(data,ensure_ascii=False,allow_nan=False).encode())
    def _path(self):
        origin=f'http://127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host')!=origin.removeprefix('http://'):
            self._json(403,{'error':'Invalid local host.'});return None
        if self.headers.get('Origin') not in (None,origin) or self.headers.get('Sec-Fetch-Site')=='cross-site':
            self._json(403,{'error':'Cross-origin requests are rejected.'});return None
        prefix=f'/{self.server.token}/'
        if not self.path.startswith(prefix) or '?' in self.path or '#' in self.path:
            self._json(404,{'error':'Not found.'});return None
        return self.path[len(prefix):]
    def do_GET(self):
        path=self._path()
        if path is None:return
        types={'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','model.js':'text/javascript; charset=utf-8','styles.css':'text/css; charset=utf-8','favicon.svg':'image/svg+xml'}
        if path=='' or path in types:
            name=path or 'index.html'
            if not (WEB/name).is_file():self._json(404,{'error':'Asset unavailable.'});return
            self._send(200,(WEB/name).read_bytes(),types[name]);return
        if path=='api/demo':
            self._json(200,{kind:dict(name=f'demo-{kind}.gpx',data=base64.b64encode((FIXTURES/f'{kind}.gpx').read_bytes()).decode()) for kind in ('before','after')});return
        match=re.fullmatch(r'api/jobs/([a-f0-9]{32})(?:/(packet\.zip))?',path)
        if not match:self._json(404,{'error':'Not found.'});return
        job=self.server.manager.get(match[1])
        if not job:self._json(404,{'error':'This analysis is no longer available.'});return
        state=job.snapshot()
        if not match[2]:self._json(200,state);return
        if state['status']!='done' or state.get('result',{}).get('kind')!='comparison':
            self._json(409,{'error':'Comparison report is not available.'});return
        with self.server.manager.lock:
            if self.server.manager.job is not job:self._json(404,{'error':'Analysis replaced.'});return
            file=job.work/'packet.zip'
            if not file.is_file():self._json(404,{'error':'Report unavailable.'});return
            content=file.read_bytes()
        self._send(200,content,'application/zip','segment-seam-report.zip')
    def do_POST(self):
        path=self._path()
        if path is None:return
        if self.headers.get('Content-Type')!='application/json':self._json(415,{'error':'JSON requests are required.'});return
        if self.headers.get('Transfer-Encoding'):self._json(400,{'error':'Transfer encoding is unsupported.'});return
        length=self.headers.get('Content-Length','')
        if not length.isdecimal() or not 0<int(length)<=MAX_REQUEST:
            self._json(413,{'error':'Request size exceeds the supported limit.'});return
        try:
            raw=self.rfile.read(int(length))
            if len(raw)!=int(length):raise InputError('Incomplete request body.')
            data=json.loads(raw)
            if not isinstance(data,dict):raise InputError('Expected a JSON object.')
            if path=='api/jobs':
                mode=data.get('mode')
                if mode not in ('inspect','compare'):raise InputError('Select inspect or compare mode.')
                options={'mode':mode}
                if mode=='compare':
                    if data.get('confirmed') is not True:raise InputError('Explicit same-logical-track confirmation is required.')
                    for field in ('before_track','after_track'):
                        value=data.get(field)
                        if type(value) is not int or not 1<=value<=256:raise InputError('Choose a valid 1-based track index.')
                        options[field]=value
                    options['confirmed']=True
                files=[]
                for kind in ('before','after'):
                    part=data.get(kind)
                    if not isinstance(part,dict) or not isinstance(part.get('data'),str) or not isinstance(part.get('name'),str):
                        raise InputError('Choose before and after GPX files.')
                    if len(part['name'])>512:raise InputError('Filename is too long.')
                    if len(part['data'])>((MAX_BYTES+2)//3*4):raise InputError('Each GPX must be at most 4 MiB.')
                    blob=base64.b64decode(part['data'],validate=True)
                    if not blob or len(blob)>MAX_BYTES:raise InputError('Each GPX must be nonempty and at most 4 MiB.')
                    files.append(blob);options[kind+'_name']=safe_name(part['name'])
                try:job=self.server.manager.start(*files,**options)
                except InputError as exc:
                    if 'already running' in str(exc):self._json(409,{'error':str(exc)});return
                    raise
                self._json(202,{'id':job.id});return
            match=re.fullmatch(r'api/jobs/([a-f0-9]{32})/cancel',path)
            if match:
                job=self.server.manager.get(match[1])
                if not job:self._json(404,{'error':'Analysis no longer available.'});return
                self._json(200,job.cancel());return
            self._json(404,{'error':'Not found.'})
        except (ValueError,TypeError,binascii.Error,UnicodeError,RecursionError) as exc:
            self._json(400,{'error':str(exc) if isinstance(exc,InputError) else 'Invalid request data.'})
        except TimeoutError:self._json(408,{'error':'Upload timed out.'})
        except OSError:self._json(500,{'error':'Local processing could not start. Check disk space and permissions.'})

def serve(port=0,open_browser=True):
    server=LocalServer(('127.0.0.1',port))
    print(f'Segment Seam local workbench: {server.url}',flush=True)
    print('Keep this capability URL private. Ctrl+C stops workers and removes temporary inputs.',flush=True)
    if open_browser:threading.Timer(.3,lambda:webbrowser.open(server.url)).start()
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:server.server_close()
