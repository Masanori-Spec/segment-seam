"""Deterministic synthetic benchmark; not a promise for arbitrary inputs."""
import argparse
import json
import platform
from pathlib import Path
import sys
import time
import tracemalloc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from segment_seam.engine import compare,NS,packet_bytes

def input_gpx(n,group):
    points=[f'<trkpt lat="0" lon="{i/10000:.4f}"><ele>0</ele></trkpt>' for i in range(n)]
    segs=''.join('<trkseg>'+''.join(points[i:i+group])+'</trkseg>' for i in range(0,n,group))
    return f'<gpx xmlns="{NS}" version="1.1" creator="synthetic benchmark"><trk>{segs}</trk></gpx>'.encode()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    results=[]
    for count in (100,1000,10000,20000):
        before,after=input_gpx(count,100),input_gpx(count,200)
        tracemalloc.start();start=time.perf_counter()
        result=compare(before,after,before_track=1,after_track=1,confirmed=True)
        packet=packet_bytes(result);seconds=time.perf_counter()-start;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        results.append(dict(points=count,input_bytes=len(before)+len(after),seconds=seconds,tracemalloc_peak_bytes=peak,packet_bytes=len(packet),status=result['status'],removed=result['summary']['removed_boundaries']))
    output=dict(python=platform.python_version(),platform=platform.platform(),dataset='Synthetic equatorial points, boundaries every 100 → 200 points',measurement='In-process engine+packet, tracemalloc Python allocations only; worker overhead and total RSS excluded',results=results)
    args.out.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
if __name__=='__main__':main()
