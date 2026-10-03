import base64
import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile
from segment_seam.engine import InputError,MAX_BYTES
from segment_seam.runner import Job,JobManager
from segment_seam.server import LocalServer,MAX_REQUEST

ROOT=Path(__file__).resolve().parent.parent
BEFORE=(ROOT/'fixtures/before.gpx').read_bytes();AFTER=(ROOT/'fixtures/after.gpx').read_bytes()

def wait(job):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        state=job.snapshot()
        if state['status']!='running':return state
        time.sleep(.01)
    raise AssertionError('Worker failed to finish within test deadline')

def payload(mode='inspect'):
    return dict(mode=mode,before=dict(name='before.gpx',data=base64.b64encode(BEFORE).decode()),after=dict(name='after.gpx',data=base64.b64encode(AFTER).decode()),before_track=1,after_track=1,confirmed=True)

class RuntimeTests(unittest.TestCase):
    def test_worker_inspect_compare_cleanup(self):
        for mode in ('inspect','compare'):
            args=dict(mode=mode)
            if mode=='compare':args.update(before_track=1,after_track=1,confirmed=True)
            job=Job(BEFORE,AFTER,**args)
            try:
                result=wait(job);self.assertEqual(result['status'],'done',result)
                self.assertEqual(result['result']['kind'],'inventory' if mode=='inspect' else 'comparison')
                self.assertEqual((job.work/'packet.zip').exists(),mode=='compare')
                self.assertEqual(job.work.stat().st_mode&0o777,0o700)
            finally:job.close()
            self.assertFalse(job.work.exists())
    def test_cancel_running_and_done(self):
        for terminal in (False,True):
            job=Job(BEFORE,AFTER,mode='compare',before_track=1,after_track=1,confirmed=True)
            try:
                if terminal:wait(job)
                state=job.cancel();self.assertEqual(state['status'],'cancelled');self.assertNotIn('result',state)
                self.assertFalse(job.process.is_alive());self.assertFalse(job.work.exists())
                self.assertEqual(job.cancel()['status'],'cancelled')
            finally:job.close()
    def test_malformed_worker_is_error(self):
        job=Job(b'<bad',AFTER,mode='inspect')
        try:self.assertEqual(wait(job)['status'],'error');self.assertFalse((job.work/'packet.zip').exists())
        finally:job.close()
    def test_worker_crash(self):
        job=Job(BEFORE,AFTER,mode='inspect')
        try:
            job.process.kill();self.assertEqual(wait(job)['status'],'error')
        finally:job.close()
    def test_wall_timeout(self):
        with patch('segment_seam.runner.WALL_SECONDS',-1):
            job=Job(BEFORE,AFTER,mode='inspect')
            try:
                state=wait(job);self.assertEqual(state['status'],'error');self.assertIn('wall-clock',state['error'])
            finally:job.close()
    def test_manager_replaces_terminal_job(self):
        manager=JobManager()
        try:
            first=manager.start(BEFORE,AFTER,mode='inspect');wait(first)
            second=manager.start(BEFORE,AFTER,mode='inspect')
            self.assertIsNone(manager.get(first.id));self.assertFalse(first.work.exists());self.assertIs(manager.get(second.id),second)
        finally:manager.close()
    def test_manager_rejects_running(self):
        manager=JobManager()
        try:
            first=manager.start(BEFORE,AFTER,mode='inspect')
            with first.lock:
                with self.assertRaises(InputError):manager.start(BEFORE,AFTER,mode='inspect')
        finally:manager.close()
    def test_worker_at_document_point_limit(self):
        from segment_seam.engine import NS
        points=''.join(f'<trkpt lat="0" lon="{i/10000:.4f}"/>' for i in range(20000))
        data=f'<gpx xmlns="{NS}" version="1.1" creator="tests"><trk><trkseg>{points}</trkseg></trk></gpx>'.encode()
        job=Job(data,data,mode='compare',before_track=1,after_track=1,confirmed=True)
        try:
            state=wait(job);self.assertEqual(state['status'],'done',state)
            self.assertEqual(state['result']['summary']['points'],20000)
        finally:job.close()
    def test_worker_input_limits(self):
        with self.assertRaises(InputError):Job(b'',AFTER,mode='inspect')
        with self.assertRaises(InputError):Job(b'x'*(MAX_BYTES+1),AFTER,mode='inspect')

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=LocalServer(('127.0.0.1',0));cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,method='GET',data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        body=None if data is None else json.dumps(data)
        hs={'Content-Type':'application/json'} if method=='POST' else {}
        if headers:hs.update(headers)
        conn.request(method,'/'+self.server.token+'/'+path,body,hs)
        response=conn.getresponse();result=(response.status,dict(response.headers),response.read());conn.close();return result
    def test_demo(self):
        status,headers,body=self.request('api/demo');self.assertEqual(status,200)
        data=json.loads(body);self.assertEqual(base64.b64decode(data['before']['data']),BEFORE)
        self.assertIn("connect-src 'self'",headers['Content-Security-Policy']);self.assertEqual(headers['Cache-Control'],'no-store')
    def test_host_origin_cross_site_rejected(self):
        for headers in ({'Host':'evil.test'},{'Origin':'https://evil.test'},{'Sec-Fetch-Site':'cross-site'}):
            with self.subTest(headers=headers):self.assertEqual(self.request('api/demo',headers=headers)[0],403)
    def test_paths_and_token(self):
        for path in ('../README.md','api/demo?x=1','%2e%2e/README.md','api/jobs/invalid'):
            self.assertEqual(self.request(path)[0],404)
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        conn.request('GET','/wrong/api/demo');response=conn.getresponse();self.assertEqual(response.status,404);response.read();conn.close()
    def test_body_type_size_and_fields(self):
        self.assertEqual(self.request('api/jobs','POST',{},headers={'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('api/jobs','POST',{},headers={'Content-Length':str(MAX_REQUEST+1)})[0],413)
        self.assertEqual(self.request('api/jobs','POST',[],headers={})[0],400)
        for changed in ({'mode':'other'},{'confirmed':False},{'before_track':True},{'before_track':0},{'after':{'name':'x','data':'%%%'}}):
            data=payload('compare');data.update(changed)
            with self.subTest(changed=changed):self.assertEqual(self.request('api/jobs','POST',data)[0],400)
    def test_real_compare_packet_and_cancel(self):
        status,_,body=self.request('api/jobs','POST',payload('compare'));self.assertEqual(status,202,body)
        id=json.loads(body)['id'];job=self.server.manager.get(id);state=wait(job);self.assertEqual(state['status'],'done',state)
        self.assertEqual(self.request('api/jobs/'+id)[0],200)
        status,headers,packet=self.request('api/jobs/'+id+'/packet.zip');self.assertEqual(status,200);self.assertEqual(headers['Content-Type'],'application/zip')
        with zipfile.ZipFile(io.BytesIO(packet)) as z:self.assertEqual(json.loads(z.read('report.json'))['summary']['removed_boundaries'],1)
        self.assertEqual(json.loads(self.request('api/jobs/'+id+'/cancel','POST',{})[2])['status'],'cancelled')
        self.assertEqual(self.request('api/jobs/'+id+'/packet.zip')[0],409)
    def test_inspect_has_no_packet(self):
        status,_,body=self.request('api/jobs','POST',payload());self.assertEqual(status,202,body)
        id=json.loads(body)['id'];wait(self.server.manager.get(id));self.assertEqual(self.request('api/jobs/'+id+'/packet.zip')[0],409)
    def test_nonloopback_binding_rejected(self):
        with self.assertRaises(InputError):LocalServer(('0.0.0.0',0))

class CLITests(unittest.TestCase):
    def command(self,*args):return subprocess.run([sys.executable,'-m','segment_seam',*map(str,args)],cwd=ROOT,capture_output=True,text=True,timeout=10)
    def test_inspect(self):
        r=self.command('inspect','fixtures/before.gpx','fixtures/after.gpx');self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['kind'],'inventory')
    def test_comparison_exit_codes_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as temp:
            for filename,code in [('after.gpx',1),('unchanged.gpx',0),('changed-point.gpx',2)]:
                output=Path(temp)/filename.replace('.gpx','.zip')
                args=['compare','fixtures/before.gpx','fixtures/'+filename,'--before-track','1','--after-track','1','--confirm-same-track','--output',output]
                result=self.command(*args);self.assertEqual(result.returncode,code,result.stderr);self.assertTrue(output.is_file())
                before=output.read_bytes();again=self.command(*args);self.assertEqual(again.returncode,2);self.assertEqual(output.read_bytes(),before)
    def test_source_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'before.gpx';source.write_bytes(BEFORE)
            r=self.command('compare',source,'fixtures/after.gpx','--before-track','1','--after-track','1','--confirm-same-track','--output',source)
            self.assertEqual(r.returncode,2);self.assertEqual(source.read_bytes(),BEFORE)

if __name__=='__main__':unittest.main()
