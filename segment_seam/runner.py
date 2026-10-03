"""Disposable POSIX worker, strict resource limits, cancellation and cleanup."""
from __future__ import annotations
import multiprocessing as mp
import os
from pathlib import Path
import queue
import resource
import shutil
import tempfile
import threading
import time
import uuid
from .engine import run_files, InputError, MAX_BYTES

WALL_SECONDS=30
CPU_SECONDS=20
MEMORY_BYTES=512*1024*1024


def _worker(before,after,path,options,events):
    resource.setrlimit(resource.RLIMIT_AS,(MEMORY_BYTES,MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU,(CPU_SECONDS,CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024*1024,16*1024*1024))
    resource.setrlimit(resource.RLIMIT_NOFILE,(32,32))
    try:
        events.put(('progress','Reading bounded GPX and checking selected point sequences'))
        result=run_files(before,after,path,**options)
        events.put(('done',result))
    except InputError as exc: events.put(('error',str(exc)))
    except (MemoryError,OSError):events.put(('error','Processing exceeded a resource limit or local storage was unavailable.'))
    except Exception:events.put(('error','GPX could not be processed safely. No comparison conclusion is available.'))


class Job:
    def __init__(self,before,after,**options):
        if not isinstance(before,bytes) or not isinstance(after,bytes) or not before or not after or len(before)>MAX_BYTES or len(after)>MAX_BYTES:
            raise InputError('Each GPX must be nonempty and at most 4 MiB.')
        self.id=uuid.uuid4().hex
        self.work=Path(tempfile.mkdtemp(prefix='segment-seam-'))
        try:
            os.chmod(self.work,0o700)
            (self.work/'before.gpx').write_bytes(before);(self.work/'after.gpx').write_bytes(after)
        except OSError:
            shutil.rmtree(self.work,ignore_errors=True)
            raise
        self.lock=threading.RLock();self.status='running';self.progress='Starting bounded local worker'
        self.result=None;self.error=None;self.started=time.monotonic();self.closed=False
        context=mp.get_context('spawn');self.events=context.Queue()
        self.process=context.Process(target=_worker,args=(str(self.work/'before.gpx'),str(self.work/'after.gpx'),str(self.work),options,self.events),daemon=True)
        try:self.process.start()
        except Exception as exc:
            self.events.close();shutil.rmtree(self.work,ignore_errors=True)
            raise InputError('Could not start the local worker.') from exc
        self.monitor=threading.Thread(target=self._monitor,daemon=True);self.monitor.start()

    def _stop(self):
        if self.process.is_alive():self.process.kill()
        self.process.join(timeout=3)

    def _monitor(self):
        while True:
            with self.lock:
                if self.status!='running':return
                if time.monotonic()-self.started>WALL_SECONDS:
                    self._stop();self.status='error';self.error='Processing exceeded the 30-second wall-clock limit.';return
            try:kind,value=self.events.get(timeout=.1)
            except queue.Empty:
                with self.lock:
                    if self.status!='running':return
                    if not self.process.is_alive():
                        self.process.join(timeout=1);self.status='error';self.error='The worker stopped unexpectedly or exceeded a resource limit.';return
                continue
            with self.lock:
                if self.status!='running':return
                if kind=='progress':self.progress=value
                elif kind=='done':
                    self.result=value;self.status='done';self.progress='Local review complete';self._stop();return
                else:self.error=value;self.status='error';self.progress='Processing stopped safely';self._stop();return

    def snapshot(self):
        with self.lock:
            data=dict(id=self.id,status=self.status,progress=self.progress)
            if self.result is not None:data['result']=self.result
            if self.error:data['error']=self.error
            return data

    def cancel(self):
        with self.lock:
            self._stop();self.status='cancelled';self.progress='Cancelled; report and temporary inputs removed'
            self.result=None;self.error=None;shutil.rmtree(self.work,ignore_errors=True)
        return self.snapshot()

    def close(self):
        self.cancel();self.monitor.join(timeout=3)
        with self.lock:
            if not self.closed:
                self.events.close();self.events.join_thread();self.closed=True


class JobManager:
    def __init__(self):self.job=None;self.lock=threading.Lock()
    def start(self,before,after,**options):
        with self.lock:
            if self.job and self.job.snapshot()['status']=='running':
                raise InputError('An analysis is already running. Cancel it before starting another.')
            if self.job:self.job.close()
            self.job=Job(before,after,**options);return self.job
    def get(self,job_id):
        with self.lock:return self.job if self.job and self.job.id==job_id else None
    def close(self):
        with self.lock:
            if self.job:self.job.close();self.job=None
