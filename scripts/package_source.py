"""Reproducible source archive plus byte and SHA-256 manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','node_modules','__pycache__','browser-artifacts','test-results','playwright-report'}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    output=args.out.resolve()
    if output==ROOT or ROOT in output.parents:raise SystemExit('Place archive output outside the source tree.')
    output.mkdir(parents=True,exist_ok=True)
    files=[]
    for file in sorted(ROOT.rglob('*')):
        relative=file.relative_to(ROOT)
        if not file.is_file() or file.is_symlink() or any(p in EXCLUDED for p in relative.parts) or file.suffix in ('.pyc','.log') or file.name=='benchmark-ci.json':continue
        files.append(file)
    archive=output/'segment-seam.zip';entries=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as target:
        for file in files:
            blob=file.read_bytes();relative=file.relative_to(ROOT).as_posix()
            entries.append(dict(path=relative,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()))
            info=zipfile.ZipInfo('segment-seam/'+relative,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            target.writestr(info,blob)
    manifest=dict(project='segment-seam',version='0.1.0',fileCount=len(entries),files=entries,archive=dict(name=archive.name,bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    (output/'segment-seam-source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(archive=str(archive),fileCount=len(entries),sha256=manifest['archive']['sha256'])))
if __name__=='__main__':main()
