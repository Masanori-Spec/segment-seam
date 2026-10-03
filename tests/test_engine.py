import hashlib
import io
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile
from segment_seam import engine as e

FIX=Path(__file__).resolve().parent.parent/'fixtures'

def point(lat='0',lon='0',extra=''):
    return f'<trkpt lat="{lat}" lon="{lon}">{extra}</trkpt>'
def gpx(segments, *,prefix='',suffix='',track_name='test'):
    body=''.join('<trkseg>'+''.join(s)+'</trkseg>' for s in segments)
    return (f'<gpx xmlns="{e.NS}" version="1.1" creator="tests">{prefix}<trk><name>{track_name}</name>{body}</trk>{suffix}</gpx>').encode()
def compare(a,b,**options):
    return e.compare(a,b,before_track=1,after_track=1,confirmed=True,**options)

class EngineTests(unittest.TestCase):
    def setUp(self):self.before=(FIX/'before.gpx').read_bytes();self.after=(FIX/'after.gpx').read_bytes()
    def test_demo(self):
        r=compare(self.before,self.after);s=r['summary']
        self.assertEqual(r['status'],'complete');self.assertEqual(r['verdict'],'boundaries_changed')
        self.assertEqual((s['removed_boundaries'],s['added_boundaries'],s['retained_boundaries']),(1,1,1))
        self.assertEqual([(v['left_point'],v['right_point'],v['change']) for v in r['seams']],[(2,3,'removed'),(4,5,'retained'),(6,7,'added')])
        self.assertAlmostEqual(s['artificial_distance_m'],e.EARTH_RADIUS_M*math.radians(.019),places=6)
        self.assertAlmostEqual(s['after_distance_m']-s['before_distance_m'],s['net_distance_change_m'],places=9)
    def test_inverse(self):
        forward=compare(self.before,self.after);back=compare(self.after,self.before)
        self.assertAlmostEqual(forward['summary']['net_distance_change_m'],-back['summary']['net_distance_change_m'])
        self.assertEqual(back['seams'][0]['change'],'added')
    def test_unchanged(self):
        r=compare(self.before,self.before)
        self.assertEqual(r['verdict'],'boundaries_unchanged');self.assertEqual(r['summary']['retained_boundaries'],2)
    def test_single_point(self):
        a=gpx([[point()]])
        r=compare(a,a);self.assertEqual(r['summary']['before_distance_m'],0);self.assertEqual(r['seams'],[])
    def test_zero_distance_removed_seam(self):
        a=gpx([[point()],[point()]]);b=gpx([[point(),point()]])
        r=compare(a,b);self.assertEqual(r['summary']['removed_boundaries'],1);self.assertEqual(r['summary']['artificial_distance_m'],0)
    def test_point_mismatch_unsupported(self):
        r=compare(self.before,(FIX/'changed-point.gpx').read_bytes())
        self.assertEqual(r['status'],'unsupported');self.assertIsNone(r['summary']);self.assertEqual(r['seams'],[])
    def test_point_count_mismatch(self):
        r=compare(gpx([[point()]]),gpx([[point(),point()]]))
        self.assertEqual(r['status'],'unsupported');self.assertIn('counts differ',r['reasons'][0])
    def test_empty_segments_unsupported(self):
        for segments in ([[],[point()]],[[point()],[]],[[],[],[point()]]):
            with self.subTest(segments=segments):
                r=compare(gpx(segments),gpx([[point()]]));self.assertEqual(r['status'],'unsupported')
    def test_empty_tracks_unsupported(self):
        r=compare(gpx([]),gpx([]));self.assertEqual(r['status'],'unsupported')
    def test_confirmation_and_index_types(self):
        for value in (False,1,'true',None):
            with self.assertRaises(e.InputError):e.compare(self.before,self.after,before_track=1,after_track=1,confirmed=value)
        for value in (True,0,-1,2,'1',1.0):
            with self.assertRaises(e.InputError):e.compare(self.before,self.after,before_track=value,after_track=1,confirmed=True)
    def test_explicit_multiple_track_pairing(self):
        first='<trk><name>unrelated</name><trkseg>'+point('1','1')+'</trkseg></trk>'
        a=gpx([[point(),point('0','1')]],suffix=first)
        b=gpx([[point(),point('0','1')]],prefix=first)
        r=e.compare(a,b,before_track=1,after_track=2,confirmed=True)
        self.assertEqual(r['status'],'complete');self.assertEqual(r['after']['track']['index'],2)
        self.assertEqual(compare(a,b)['status'],'unsupported')
    def test_decimal_spelling_change_not_assumed_equal(self):
        self.assertEqual(compare(gpx([[point()]]),gpx([[point('0.0')]]))['status'],'unsupported')
    def test_point_time_elevation_changes_unsupported(self):
        for field in ('<time>bad</time>','<ele>1e5</ele>','<extensions><x xmlns="urn:t">1</x></extensions>'):
            with self.subTest(field=field):
                self.assertEqual(compare(gpx([[point()]]),gpx([[point(extra=field)]]))['status'],'unsupported')
    def test_raw_values_not_interpreted(self):
        a=gpx([[point(extra='<time>not a timestamp</time><ele>NaN</ele>')],[point('1','1')]])
        r=compare(a,a);w=r['seams'][0]['left']
        self.assertEqual(w['time'],{'state':'raw','text':'not a timestamp'});self.assertEqual(w['elevation']['text'],'NaN')
    def test_absent_values(self):
        a=gpx([[point()],[point('1','1')]])
        self.assertEqual(compare(a,a)['seams'][0]['left']['time'],dict(state='absent',text=None))
    def test_xml_prefix_and_attribute_order_formatting(self):
        a=gpx([[point(extra='<ele>0</ele>')]]);b=a.replace(b'<trkpt lat="0" lon="0">',b'<trkpt lon="0" lat="0">\n ')
        self.assertEqual(compare(a,b)['status'],'complete')
    def test_names_sanitized_metadata_excluded(self):
        r=compare(self.before,self.before.replace(b'Synthetic recorder',b'Different recorder'),before_name='../../<x>\n.gpx')
        self.assertEqual(r['status'],'complete');self.assertEqual(r['before']['name'],'_x__.gpx')
    def test_file_hash_and_inventory(self):
        r=e.inspect_pair(self.before,self.after)
        self.assertEqual(r['before']['sha256'],hashlib.sha256(self.before).hexdigest());self.assertEqual(r['before']['tracks'][0]['points'],8)
    def test_strict_root(self):
        good=gpx([[point()]])
        for bad in (good.replace(b'1.1',b'1.0'),good.replace(e.NS.encode(),b'urn:other'),good.replace(b' creator="tests"',b''),good.replace(b'<trk>',b'<other>').replace(b'</trk>',b'</other>')):
            with self.assertRaises(e.InputError):e.parse_gpx(bad)
    def test_coordinate_validation(self):
        for lat,lon in [('NaN','0'),('1e0','0'),('Infinity','0'),('90.1','0'),('-90.1','0'),('0','180'),('0','-180.1'),(' 0','0'),('','0')]:
            with self.subTest(lat=lat,lon=lon),self.assertRaises(e.InputError):e.parse_gpx(gpx([[point(lat,lon)]]))
        e.parse_gpx(gpx([[point('-90','-180'),point('90','179.99')]]))
    def test_dtd_entities_rejected(self):
        for declaration in ('<!DOCTYPE gpx>','<!DOCTYPE gpx [<!ENTITY e "x">]>','<!DOCTYPE gpx SYSTEM "file:///etc/passwd">'):
            with self.assertRaises(e.InputError):e.parse_gpx(declaration.encode()+self.before)
    def test_predefined_entities_safe(self):
        r=e.parse_gpx(gpx([[point()]],track_name='A &amp; B &#x3C; C'))
        self.assertEqual(r.tracks[0].name,'A & B < C')
    def test_unknown_entity_error(self):
        with self.assertRaises(e.InputError):e.parse_gpx(gpx([[point()]],track_name='&unknown;'))
    def test_encoding_malformed_xml_pi_include(self):
        bads=[b'\xff',b'<',b'<?xml version="1.0" encoding="utf-16"?>'+gpx([[point()]]),b'<?xml-stylesheet href="https://example.test/a"?>'+gpx([[point()]]),gpx([[point()]],prefix='<x:include xmlns:x="http://www.w3.org/2001/XInclude" href="file:///etc/passwd"/>')]
        for bad in bads:
            with self.subTest(bad=bad[:80]),self.assertRaises(e.InputError):e.parse_gpx(bad)
    def test_nested_point_rejected(self):
        with self.assertRaises(e.InputError):e.parse_gpx(gpx([[point(extra=point())]]))
    def test_wrong_point_location_rejected(self):
        with self.assertRaises(e.InputError):e.parse_gpx(gpx([[point()]],prefix='<metadata>'+point()+'</metadata>'))
    def test_duplicate_and_complex_raw_fields_rejected(self):
        for extra in ('<time>a</time><time>b</time>','<ele><x/></ele>'):
            with self.assertRaises(e.InputError):e.parse_gpx(gpx([[point(extra=extra)]]))
    def test_byte_limit(self):
        with patch.object(e,'MAX_BYTES',64),self.assertRaises(e.InputError):e.parse_gpx(self.before)
    def test_point_limit(self):
        with patch.object(e,'MAX_POINTS',7),self.assertRaises(e.InputError):e.parse_gpx(self.before)
    def test_node_depth_segment_limits(self):
        for setting,value in [('MAX_NODES',3),('MAX_DEPTH',2),('MAX_SEGMENTS',2),('MAX_TRACKS',0)]:
            with self.subTest(setting=setting),patch.object(e,setting,value),self.assertRaises(e.InputError):e.parse_gpx(self.before)
    def test_text_attribute_limits(self):
        with self.assertRaises(e.InputError):e.parse_gpx(gpx([[point(extra='<name>'+'a'*8193+'</name>')]]))
        with self.assertRaises(e.InputError):e.parse_gpx(gpx([[point()]]).replace(b'creator="tests"',b'creator="'+b'a'*4097+b'"'))
    def test_seam_limit_no_partial_success(self):
        with patch.object(e,'MAX_SEAMS',2):r=compare(self.before,self.after)
        self.assertEqual(r['status'],'unsupported');self.assertEqual(r['seams'],[]);self.assertFalse(r['witnesses_truncated'])
    def test_packet_hashes_and_determinism(self):
        report=compare(self.before,self.after);packet=e.packet_bytes(report)
        self.assertEqual(packet,e.packet_bytes(report))
        with zipfile.ZipFile(io.BytesIO(packet)) as z:
            self.assertEqual(set(z.namelist()),{'report.json','report.txt','manifest.json'})
            manifest=json.loads(z.read('manifest.json'))
            for f in manifest['files']:
                blob=z.read(f['path']);self.assertEqual(f['bytes'],len(blob));self.assertEqual(f['sha256'],hashlib.sha256(blob).hexdigest())
    def test_packet_size_limit(self):
        with patch.object(e,'MAX_OUTPUT',10),self.assertRaises(e.InputError):e.packet_bytes(compare(self.before,self.after))
    def test_unsupported_packet_has_no_distances(self):
        report=compare(self.before,(FIX/'changed-point.gpx').read_bytes())
        with zipfile.ZipFile(io.BytesIO(e.packet_bytes(report))) as z:
            data=json.loads(z.read('report.json'));self.assertIsNone(data['summary']);self.assertEqual(data['seams'],[])

if __name__=='__main__':unittest.main()
