"""CLI entrypoint. Exit 0 scoped unchanged, 1 changed, 2 unsupported/error."""
import argparse
import json
from pathlib import Path
import sys
import time
from .engine import InputError,read_bounded,render_text
from .runner import Job

def main():
    parser=argparse.ArgumentParser(description='Local GPX 1.1 segment-boundary evidence review; no route safety conclusion.')
    sub=parser.add_subparsers(dest='command',required=True)
    serve_parser=sub.add_parser('serve',help='Open loopback-only bilingual workbench (Linux, POSIX limits required)')
    serve_parser.add_argument('--port',type=int,default=0);serve_parser.add_argument('--no-browser',action='store_true')
    inspect_parser=sub.add_parser('inspect',help='List track indices without comparing')
    compare_parser=sub.add_parser('compare',help='Compare explicitly selected unchanged point sequences')
    for p in (inspect_parser,compare_parser):p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    compare_parser.add_argument('--before-track',type=int,required=True);compare_parser.add_argument('--after-track',type=int,required=True)
    compare_parser.add_argument('--confirm-same-track',action='store_true',required=True)
    compare_parser.add_argument('--output',type=Path,required=True,help='New .zip packet path; existing files are not overwritten')
    args=parser.parse_args()
    try:
        if args.command=='serve':
            from .server import serve
            serve(args.port,not args.no_browser);return 0
        before,after=read_bounded(args.before),read_bounded(args.after)
        names=dict(before_name=args.before.name,after_name=args.after.name)
        options=dict(mode=args.command,**names)
        if args.command=='compare':
            options.update(before_track=args.before_track,after_track=args.after_track,confirmed=args.confirm_same_track)
        job=Job(before,after,**options)
        try:
            while (state:=job.snapshot())['status']=='running':time.sleep(.02)
            if state['status']!='done':raise InputError(state.get('error','Analysis was cancelled.'))
            result=state['result']
            if args.command=='inspect':
                print(json.dumps(result,ensure_ascii=False,indent=2));return 0
            content=(job.work/'packet.zip').read_bytes()
            # Exclusive creation protects both source files and existing evidence packets.
            with args.output.open('xb') as target:target.write(content)
        finally:job.close()
        print(render_text(result),end='');print('Packet: '+str(args.output))
        return 2 if result['status']=='unsupported' else 1 if result['verdict']=='boundaries_changed' else 0
    except (InputError,OSError) as exc:
        print('No successful comparison: '+str(exc),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
