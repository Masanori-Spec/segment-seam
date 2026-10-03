"""Bounded, local GPX 1.1 segment-boundary comparison. No external resources."""
from __future__ import annotations
import hashlib
import io
import json
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024
MAX_POINTS = 20_000
MAX_NODES = 120_000
MAX_DEPTH = 32
MAX_NAMESPACE_BINDINGS = 64
MAX_TRACKS = 256
MAX_SEGMENTS = 2_000
MAX_SEAMS = 2_000
MAX_OUTPUT = 12 * 1024 * 1024
NS = 'http://www.topografix.com/GPX/1/1'
XINCLUDE = 'http://www.w3.org/2001/XInclude'
TAG = '{' + NS + '}'
EARTH_RADIUS_M = 6_371_008.8
SCOPE = [
    'Only the explicitly selected before/after tracks are compared.',
    'Point order and normalized XML point content must remain unchanged; no near matching.',
    'Only segment boundaries and horizontal spherical edge distances are reviewed.',
    'Other tracks, waypoints, routes, and track/segment/file metadata are not compared.',
    'No conclusion about full GPX equivalence, recording truth, navigation, or route safety.'
]
METHOD = dict(name='spherical-haversine', radius_m=EARTH_RADIUS_M,
    description='Haversine central angle on a sphere with radius 6371008.8 m, using a directly computed complementary half-angle near antipodes for numerical stability. Horizontal only; not WGS84 ellipsoidal or elevation-aware. Numerical estimates, not measured travel.')

class InputError(ValueError):
    """Rejected or unprocessable input; never a successful comparison."""

@dataclass
class Point:
    lat: str
    lon: str
    elevation: dict
    time: dict
    signature: tuple
    segment: int

@dataclass
class Track:
    index: int
    name: str
    points: list[Point]
    lengths: list[int]
    def summary(self):
        return dict(index=self.index, name=self.name, points=len(self.points),
                    segments=len(self.lengths), empty_segments=self.lengths.count(0))

@dataclass
class Document:
    name: str
    sha256: str
    size: int
    tracks: list[Track]
    waypoints: int
    routes: int
    def inventory(self):
        return dict(name=self.name, sha256=self.sha256, bytes=self.size,
            tracks=[t.summary() for t in self.tracks], waypoints=self.waypoints, routes=self.routes)


def safe_name(value):
    value = str(value).replace('\\', '/').split('/')[-1]
    return ''.join(c if c.isprintable() and c not in '<>"' else '_' for c in value)[:120] or 'input.gpx'


def read_bounded(path):
    with Path(path).open('rb') as source:
        blob = source.read(MAX_BYTES + 1)
    if not blob or len(blob) > MAX_BYTES:
        raise InputError('Each GPX must be nonempty and at most 4 MiB.')
    return blob


def _coordinate(raw, name, lower, upper, exclusive=False):
    if raw is None or len(raw) > 64 or not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', raw):
        raise InputError(f'{name} must be a finite GPX decimal, without exponent notation.')
    try: value = Decimal(raw)
    except InvalidOperation as exc: raise InputError(f'Invalid {name}.') from exc
    if value < lower or value > upper or (exclusive and value == upper):
        raise InputError(f'{name} is outside the GPX 1.1 range.')
    return raw


def _signature(element, preserve_space=False, namespace_scopes=None, extension_context=False):
    # Expanded names and attribute-order independence. Only indentation-only
    # text around child elements is ignored; leaf and mixed text are exact
    # XML-decoded strings. Honor inherited xml:space='preserve'.
    extension_context = (extension_context or element.tag == TAG+'extensions'
                         or not element.tag.startswith(TAG))
    space = element.get('{http://www.w3.org/XML/1998/namespace}space')
    if space is not None:
        preserve_space = space != 'default'
    text = element.text or ''
    if (len(element) or element.tag == TAG + 'trkpt') and not preserve_space and not text.strip():
        text = ''
    children = []
    for child in element:
        tail = child.tail or ''
        if not preserve_space and not tail.strip():
            tail = ''
        children.append((_signature(child, preserve_space, namespace_scopes, extension_context), tail))
    context = ()
    values = [element.text or '', *element.attrib.values(), *(c.tail or '' for c in element)]
    unknown_attributes = any(key not in ('lat', 'lon', 'href',
                            '{http://www.w3.org/XML/1998/namespace}space')
                             for key in element.attrib)
    if namespace_scopes is not None and (extension_context or unknown_attributes) and any(v.strip() for v in values):
        # Unknown extension schemas can assign QName semantics to values. Keep
        # the complete in-scope binding context, without interpreting tokens.
        # These immutable tuples are shared across nodes in the same scope.
        context = namespace_scopes[element]
    return (element.tag, tuple(sorted(element.attrib.items())), text, tuple(children), context)


def _raw_field(point, key):
    fields = point.findall(TAG + key)
    if len(fields) > 1: raise InputError(f'Duplicate point {key} field.')
    if not fields: return dict(state='absent', text=None)
    if len(fields[0]): raise InputError(f'Point {key} field must contain text only.')
    # Explicitly raw: GPX decimal/dateTime semantic validity is not asserted.
    return dict(state='raw', text=fields[0].text or '')


def parse_gpx(blob, name='input.gpx'):
    if not isinstance(blob, bytes) or not blob or len(blob) > MAX_BYTES:
        raise InputError('Each GPX must be nonempty and at most 4 MiB.')
    try: text = blob.decode('utf-8-sig')
    except UnicodeError as exc: raise InputError('Only valid UTF-8 GPX is supported.') from exc
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I):
        raise InputError('DTD and entity declarations are rejected.')
    declaration = re.match(r'<\?xml\s+[^?]*\?>', text)
    if declaration:
        enc = re.search(r'encoding\s*=\s*[\'"]([^\'"]+)', declaration[0], re.I)
        if enc and enc[1].lower() not in ('utf-8', 'utf8'):
            raise InputError('XML encoding declarations must specify UTF-8.')
        rest = text[declaration.end():]
    else: rest = text
    if '<?' in rest: raise InputError('Processing instructions and external stylesheets are rejected.')
    depth = nodes = point_count = segment_count = 0
    ancestors = []; space_stack = []; point_spaces = {}
    namespace_stack = []; namespace_scopes = {}; pending_namespaces = []
    structural_parents = {TAG+'trk': [TAG+'gpx'],
                          TAG+'trkseg': [TAG+'gpx', TAG+'trk'],
                          TAG+'trkpt': [TAG+'gpx', TAG+'trk', TAG+'trkseg']}
    try:
        parser = ET.iterparse(io.StringIO(text), events=('start-ns', 'start', 'end'))
        for event, element in parser:
            if event == 'start-ns':
                prefix, uri = element
                if len(pending_namespaces) >= 32 or len(prefix) > 1024 or len(uri) > 4096:
                    raise InputError('XML namespace declaration limit exceeded.')
                pending_namespaces.append((prefix, uri))
                continue
            if event == 'start':
                scope, context = namespace_stack[-1] if namespace_stack else ({}, ())
                if pending_namespaces:
                    scope = dict(scope)
                    scope.update(pending_namespaces)
                    if len(scope) > MAX_NAMESPACE_BINDINGS:
                        raise InputError('XML in-scope namespace binding limit exceeded.')
                    context = tuple(sorted(scope.items()))
                if len(element.attrib)+len(pending_namespaces) > 32:
                    raise InputError('XML attribute limit exceeded.')
                pending_namespaces.clear()
                namespace_stack.append((scope, context))
                namespace_scopes[element] = context
                if element.tag in structural_parents and ancestors != structural_parents[element.tag]:
                    raise InputError('Track, segment and point elements must use their direct GPX paths.')
                ancestors.append(element.tag)
                preserve_space = space_stack[-1] if space_stack else False
                space = element.get('{http://www.w3.org/XML/1998/namespace}space')
                if space is not None:
                    preserve_space = space != 'default'
                space_stack.append(preserve_space)
                depth += 1; nodes += 1
                if depth > MAX_DEPTH or nodes > MAX_NODES:
                    raise InputError('XML nesting or node limit exceeded.')
                if element.tag.startswith('{' + XINCLUDE + '}'):
                    raise InputError('External XML includes are rejected.')
                if len(element.attrib) > 32 or any(len(k) > 1024 or len(v) > 4096 for k,v in element.attrib.items()):
                    raise InputError('XML attribute limit exceeded.')
                if element.tag == TAG + 'trkpt':
                    point_spaces[element] = preserve_space
                    point_count += 1
                    if point_count > MAX_POINTS: raise InputError('At most 20,000 track points per file are supported.')
                if element.tag == TAG + 'trkseg':
                    segment_count += 1
                    if segment_count > MAX_SEGMENTS: raise InputError('At most 2,000 segments per file are supported.')
            else:
                if len(element.text or '') > 8192 or len(element.tail or '') > 8192:
                    raise InputError('XML text field limit exceeded.')
                depth -= 1
                ancestors.pop(); space_stack.pop(); namespace_stack.pop()
        root = parser.root
    except ET.ParseError as exc: raise InputError('Malformed XML; comparison was not run.') from exc
    if root.tag != TAG + 'gpx' or root.get('version') != '1.1' or not root.get('creator'):
        raise InputError('A GPX 1.1 root with its official namespace, version and creator is required.')
    allowed_root = {'metadata','wpt','rte','trk','extensions'}
    if any(c.tag not in {TAG+n for n in allowed_root} for c in root):
        raise InputError('Unsupported root content; foreign data must be inside extensions.')
    tracks = []
    for element in root.findall(TAG + 'trk'):
        if len(tracks) >= MAX_TRACKS: raise InputError('At most 256 tracks per file are supported.')
        allowed = {'name','cmt','desc','src','link','number','type','extensions','trkseg'}
        if any(c.tag not in {TAG+n for n in allowed} for c in element):
            raise InputError('Unsupported track structure.')
        names = element.findall(TAG + 'name')
        if len(names)>1 or any(len(n) for n in names): raise InputError('Track name must be one text field.')
        name_value = (names[0].text or '').strip() if names else '(unnamed)'
        if len(name_value)>240: raise InputError('Track names are limited to 240 characters.')
        points=[]; lengths=[]
        for si, segment in enumerate(element.findall(TAG+'trkseg'),1):
            if any(c.tag not in (TAG+'trkpt', TAG+'extensions') for c in segment):
                raise InputError('Unsupported segment structure.')
            segment_points=segment.findall(TAG+'trkpt'); lengths.append(len(segment_points))
            for p in segment_points:
                if len(list(p.iter(TAG+'trkpt'))) != 1:
                    raise InputError('Nested track points are unsupported.')
                lat = _coordinate(p.get('lat'), 'Latitude', -90, 90)
                lon = _coordinate(p.get('lon'), 'Longitude', -180, 180, exclusive=True)
                points.append(Point(lat,lon,_raw_field(p,'ele'),_raw_field(p,'time'),_signature(p,point_spaces[p],namespace_scopes),si))
        tracks.append(Track(len(tracks)+1,name_value,points,lengths))
    # Any GPX point outside the recognized track/segment path is unsupported.
    if sum(len(t.points) for t in tracks) != point_count:
        raise InputError('Track points outside direct track segments are unsupported.')
    return Document(safe_name(name),hashlib.sha256(blob).hexdigest(),len(blob),tracks,
                    len(root.findall(TAG+'wpt')),len(root.findall(TAG+'rte')))


def inspect_pair(before, after, before_name='before.gpx', after_name='after.gpx'):
    a,b = parse_gpx(before,before_name),parse_gpx(after,after_name)
    return dict(kind='inventory',before=a.inventory(),after=b.inventory(),
                limits=dict(max_bytes=MAX_BYTES,max_points=MAX_POINTS))


def distance_m(a,b):
    lat1,lat2 = math.radians(float(a.lat)), math.radians(float(b.lat))
    dlat = math.radians(float(b.lat)-float(a.lat))
    # remainder preserves tiny longitude deltas, unlike adding 180 before %.
    dlon = math.radians(math.remainder(float(b.lon)-float(a.lon), 360.0))
    product = math.cos(lat1)*math.cos(lat2)
    h = math.sin(dlat/2)**2 + product*math.sin(dlon/2)**2
    # 1-h loses all useful precision near antipodes. This identical positive
    # half-angle expression computes the complement without cancellation.
    complement = (math.sin((lat1+lat2)/2)**2 + product*math.cos(dlon/2)**2
                  if h > 0.5 else 1-h)
    return EARTH_RADIUS_M * 2 * math.atan2(
        math.sqrt(max(0,min(1,h))), math.sqrt(max(0,min(1,complement))))


def _witness(p,index):
    return dict(index=index,lat=p.lat,lon=p.lon,elevation=p.elevation,time=p.time)


def _selected(doc,index):
    if type(index) is not int or not 1<=index<=len(doc.tracks):
        raise InputError('Choose an existing 1-based track index in each file.')
    track=doc.tracks[index-1]
    return track, dict(name=doc.name,sha256=doc.sha256,bytes=doc.size,track=track.summary())


def compare(before,after,*,before_track,after_track,confirmed=False,before_name='before.gpx',after_name='after.gpx'):
    if confirmed is not True: raise InputError('Explicit same-logical-track confirmation is required.')
    a,b = parse_gpx(before,before_name),parse_gpx(after,after_name)
    ta,da=_selected(a,before_track);tb,db=_selected(b,after_track)
    report=dict(kind='comparison',schema='segment-seam/1',status='unsupported',verdict='not_compared',
        reasons=[],scope=SCOPE.copy(),before=da,after=db,method=METHOD.copy(),summary=None,seams=[],
        witnesses_truncated=False,metadata_note='Track, segment and file metadata, other tracks, routes and waypoints are not compared. Time and elevation are preserved raw text, not validated or used in distance. Reports contain exact selected point coordinates; keep them private.')
    reasons=report['reasons']
    if not ta.points or not tb.points: reasons.append('Selected tracks must contain at least one point.')
    if 0 in ta.lengths or 0 in tb.lengths: reasons.append('Empty segments are unsupported; no boundary was silently collapsed.')
    if len(ta.points)!=len(tb.points): reasons.append('Selected point counts differ; no near matching or interpolation was attempted.')
    else:
        for i,(pa,pb) in enumerate(zip(ta.points,tb.points),1):
            if pa.signature!=pb.signature:
                reasons.append(f'Normalized XML point content differs at point {i}; no near matching was attempted.')
                break
    if reasons:return report
    before_bound={i for i in range(1,len(ta.points)) if ta.points[i-1].segment!=ta.points[i].segment}
    after_bound={i for i in range(1,len(tb.points)) if tb.points[i-1].segment!=tb.points[i].segment}
    union=sorted(before_bound | after_bound)
    if len(union)>MAX_SEAMS:
        reasons.append('More than 2,000 unique boundary witnesses; no partial success or truncated verdict is emitted.')
        return report
    distances=[distance_m(ta.points[i-1],ta.points[i]) for i in range(1,len(ta.points))]
    removed=before_bound-after_bound; added=after_bound-before_bound;retained=before_bound & after_bound
    for i in union:
        report['seams'].append(dict(left_point=i,right_point=i+1,
            change='removed' if i in removed else 'added' if i in added else 'retained',distance_m=distances[i-1],
            before=dict(left_segment=ta.points[i-1].segment,right_segment=ta.points[i].segment),
            after=dict(left_segment=tb.points[i-1].segment,right_segment=tb.points[i].segment),
            left=_witness(ta.points[i-1],i),right=_witness(ta.points[i],i+1)))
    before_distance=math.fsum(d for i,d in enumerate(distances,1) if i not in before_bound)
    after_distance=math.fsum(d for i,d in enumerate(distances,1) if i not in after_bound)
    artificial=math.fsum(distances[i-1] for i in sorted(removed))
    disconnected=math.fsum(distances[i-1] for i in sorted(added))
    report.update(status='complete',verdict='boundaries_changed' if removed or added else 'boundaries_unchanged',
        summary=dict(points=len(ta.points),removed_boundaries=len(removed),added_boundaries=len(added),retained_boundaries=len(retained),
            before_distance_m=before_distance,after_distance_m=after_distance,artificial_distance_m=artificial,
            disconnected_distance_m=disconnected,net_distance_change_m=artificial-disconnected))
    return report


def render_text(report):
    lines=['SEGMENT SEAM / セグメント境界レビュー', '', 'Status: '+report['status'], 'Verdict: '+report['verdict'],
        'Before: '+report['before']['name'], 'After: '+report['after']['name'], '', 'SCOPE / 範囲']+report['scope']
    lines += ['', 'METHOD / 距離計算',report['method']['description'],'',report['metadata_note']]
    if report['reasons']:lines+=['','NOT COMPARED / 比較対象外']+report['reasons']
    if report['summary']:
        lines+=['','SUMMARY / 集計']+[f'{k}: {v}' for k,v in report['summary'].items()]
    for s in report['seams']:
        lines += ['',f"{s['change'].upper()} boundary {s['left_point']} → {s['right_point']} | {s['distance_m']:.6f} m",
            f"Before segments {s['before']['left_segment']} → {s['before']['right_segment']}; after {s['after']['left_segment']} → {s['after']['right_segment']}",
            'Left witness: '+json.dumps(s['left'],ensure_ascii=False), 'Right witness: '+json.dumps(s['right'],ensure_ascii=False)]
    return '\n'.join(lines)+'\n'


def packet_bytes(report):
    files={'report.json':json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False).encode(),
           'report.txt':render_text(report).encode()}
    if sum(map(len,files.values()))>MAX_OUTPUT: raise InputError('Report output exceeds 12 MiB; no truncated packet is emitted.')
    manifest=dict(schema='segment-seam-manifest/1',files=[dict(path=k,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for k,v in files.items()])
    files['manifest.json']=json.dumps(manifest,indent=2).encode()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100600 << 16
            archive.writestr(info,data)
    return stream.getvalue()


def run_files(before_path,after_path,output_path,*,mode='compare',**options):
    before,after=read_bounded(before_path),read_bounded(after_path)
    if mode=='inspect':return inspect_pair(before,after,options.get('before_name','before.gpx'),options.get('after_name','after.gpx'))
    if mode!='compare':raise InputError('Unsupported analysis mode.')
    report=compare(before,after,**options)
    packet=packet_bytes(report)
    target=Path(output_path)/'packet.zip'
    target.write_bytes(packet)
    return report
