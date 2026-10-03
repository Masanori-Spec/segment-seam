"""Independent adversarial review: no production Haversine in the oracle."""
import hashlib
import io
import json
import math
import multiprocessing as mp
from pathlib import Path
import random
import resource
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from segment_seam import engine as e
from segment_seam.runner import Job, JobManager


def point(lat='0', lon='0', body=''):
    return f'<trkpt lat="{lat}" lon="{lon}">{body}</trkpt>'


def document(points, cuts=(), *, extra='', name='review'):
    segments=[]
    last=0
    for cut in sorted(cuts):
        segments.append(''.join(points[last:cut]));last=cut
    segments.append(''.join(points[last:]))
    content=''.join('<trkseg>'+segment+'</trkseg>' for segment in segments)
    return (f'<gpx xmlns="{e.NS}" version="1.1" creator="adversarial tests">'
            f'{extra}<trk><name>{name}</name>{content}</trk></gpx>').encode()


def compare(a,b,**kwargs):
    return e.compare(a,b,before_track=1,after_track=1,confirmed=True,**kwargs)


def vector_distance(lat1,lon1,lat2,lon2):
    """Independent unit-vector cross/dot atan2 oracle for the declared sphere."""
    p1,l1,p2,l2=map(math.radians,map(float,(lat1,lon1,lat2,lon2)))
    a=(math.cos(p1)*math.cos(l1),math.cos(p1)*math.sin(l1),math.sin(p1))
    b=(math.cos(p2)*math.cos(l2),math.cos(p2)*math.sin(l2),math.sin(p2))
    cross=tuple(a[(i+1)%3]*b[(i+2)%3]-a[(i+2)%3]*b[(i+1)%3] for i in range(3))
    return 6_371_008.8*math.atan2(math.hypot(*cross),math.fsum(x*y for x,y in zip(a,b)))


def numeric_distance(coords):
    pts=[e.Point(str(lat),str(lon),{}, {},(),1) for lat,lon in (coords[:2],coords[2:])]
    return e.distance_m(*pts)


class IndependentSphereReview(unittest.TestCase):
    def test_analytic_equator_quarter_and_tiny_edges(self):
        for delta in (90,1,.001,1e-9,1e-14):
            with self.subTest(delta=delta):
                actual=numeric_distance((0,0,0,delta))
                expected=6_371_008.8*math.radians(delta)
                self.assertTrue(math.isclose(actual,expected,rel_tol=2e-15,abs_tol=1e-15),(actual,expected))

    def test_antimeridian_poles_antipodes_near_antipodes(self):
        pairs=[(0,179.999999,0,-179.999999),(90,0,90,170),(-90,17,90,-103),
               (0,0,0,-180),(0,0,0,179.999999),(37,11,-37,-168.999999),
               (89.999999,19,-89.999999,-161),(20,20,-20.000001,-160)]
        for coords in pairs:
            with self.subTest(coords=coords):
                self.assertAlmostEqual(numeric_distance(coords),vector_distance(*coords),delta=1e-7)

    def test_seeded_global_and_near_antipodal_property(self):
        rng=random.Random(50317)
        cases=[]
        for _ in range(600):
            cases.append((rng.uniform(-90,90),rng.uniform(-180,180),rng.uniform(-90,90),rng.uniform(-180,180)))
        for _ in range(300):
            lat,lon=rng.uniform(-89,89),rng.uniform(-180,180)
            epsilon=10**rng.uniform(-10,-2)
            other_lon=(lon+180+epsilon+180)%360-180
            cases.append((lat,lon,-lat+rng.uniform(-epsilon,epsilon),other_lon))
        max_error=0
        for coords in cases:
            actual=numeric_distance(coords);expected=vector_distance(*coords)
            self.assertTrue(math.isfinite(actual));self.assertGreaterEqual(actual,0)
            self.assertLessEqual(actual,math.pi*6_371_008.8+1e-8)
            max_error=max(max_error,abs(actual-expected))
            self.assertAlmostEqual(actual,expected,delta=1e-7,msg=str(coords))
            reverse=coords[2:]+coords[:2]
            self.assertAlmostEqual(actual,numeric_distance(reverse),delta=1e-8)
        self.assertLess(max_error,1e-7)


class BoundaryPropertyReview(unittest.TestCase):
    def test_generated_boundary_algebra_and_exact_witnesses(self):
        rng=random.Random(291017)
        for case in range(160):
            count=rng.randrange(1,70)
            coords=[(f'{rng.uniform(-80,80):.9f}',f'{rng.uniform(-179,179):.9f}') for _ in range(count)]
            raw=[point(lat,lon,f'<ele> raw elevation {i} </ele><time>not-a-date-{i}</time>')
                 for i,(lat,lon) in enumerate(coords)]
            before={i for i in range(1,count) if rng.random()<.25}
            after={i for i in range(1,count) if rng.random()<.25}
            a=document(raw,before);b=document(raw,after)
            result=compare(a,b);summary=result['summary']
            self.assertEqual(result['status'],'complete')
            expected={i:'removed' if i in before-after else 'added' if i in after-before else 'retained' for i in before|after}
            self.assertEqual({s['left_point']:s['change'] for s in result['seams']},expected)
            self.assertEqual(summary['removed_boundaries'],len(before-after))
            self.assertEqual(summary['added_boundaries'],len(after-before))
            self.assertEqual(summary['retained_boundaries'],len(before&after))
            distances=[vector_distance(*coords[i-1],*coords[i]) for i in range(1,count)]
            self.assertAlmostEqual(summary['before_distance_m'],math.fsum(d for i,d in enumerate(distances,1) if i not in before),delta=2e-6)
            self.assertAlmostEqual(summary['after_distance_m'],math.fsum(d for i,d in enumerate(distances,1) if i not in after),delta=2e-6)
            self.assertAlmostEqual(summary['artificial_distance_m'],math.fsum(distances[i-1] for i in before-after),delta=1e-6)
            self.assertAlmostEqual(summary['disconnected_distance_m'],math.fsum(distances[i-1] for i in after-before),delta=1e-6)
            self.assertAlmostEqual(summary['after_distance_m']-summary['before_distance_m'],summary['net_distance_change_m'],delta=2e-6)
            for seam in result['seams']:
                i=seam['left_point']
                self.assertEqual(seam['right_point'],i+1)
                for side,index in [('left',i),('right',i+1)]:
                    self.assertEqual(seam[side]['index'],index)
                    self.assertEqual((seam[side]['lat'],seam[side]['lon']),coords[index-1])
                    self.assertEqual(seam[side]['elevation']['text'],f' raw elevation {index-1} ')
                    self.assertEqual(seam[side]['time']['text'],f'not-a-date-{index-1}')
                self.assertEqual(seam['before'],dict(left_segment=1+sum(j<i for j in before),right_segment=1+sum(j<=i for j in before)))
                self.assertEqual(seam['after'],dict(left_segment=1+sum(j<i for j in after),right_segment=1+sum(j<=i for j in after)))
                self.assertAlmostEqual(seam['distance_m'],distances[i-1],delta=1e-7)

    def test_exact_normalized_xml_accepts_prefix_attr_order_entities_and_indent(self):
        a=document([point('0.00','-0','<ele> 001.0 </ele><name>A &amp; B</name>')])
        b=a.replace(b'<trkpt lat="0.00" lon="-0">',b'<g:trkpt xmlns:g="'+e.NS.encode()+b'" lon="-0" lat="0.00">\n ')
        b=b.replace(b'</trkpt>',b'\n</g:trkpt>').replace(b' a="1" b="2"',b' b="2" a="1"').replace(b'A &amp; B',b'A &#38; B')
        self.assertEqual(compare(a,b)['status'],'complete')

    def test_leaf_and_mixed_text_whitespace_is_not_discarded(self):
        for left,right in [('<ele> 1 </ele>','<ele>1</ele>'),('<time> x </time>','<time>x</time>'),
                           ('<ele> </ele>','<ele/>'),
                           ('<extensions><n xmlns="urn:test"> a </n></extensions>','<extensions><n xmlns="urn:test">a</n></extensions>'),
                           ('<extensions><n xmlns="urn:test">x</n> end </extensions>','<extensions><n xmlns="urn:test">x</n>end</extensions>')]:
            with self.subTest(left=left):
                result=compare(document([point(body=left)]),document([point(body=right)]))
                self.assertEqual(result['status'],'unsupported');self.assertIsNone(result['summary']);self.assertEqual(result['seams'],[])

    def test_xml_space_preserve_within_point_is_honored(self):
        a=document([point(body='<extensions xml:space="preserve"><x xmlns="urn:test"/></extensions>')])
        b=a.replace(b'<extensions xml:space="preserve">',b'<extensions xml:space="preserve"> ')
        self.assertEqual(compare(a,b)['status'],'unsupported')

    def test_inherited_xml_space_preserve_is_honored(self):
        a=document([point(body='<ele>1</ele>')]).replace(b'creator="adversarial tests"',b'creator="adversarial tests" xml:space="preserve"')
        b=a.replace(b'<ele>',b' <ele>')
        self.assertEqual(compare(a,b)['status'],'unsupported')
        # A point-local default resets inherited preserve semantics.
        a=a.replace(b'<trkpt ',b'<trkpt xml:space="default" ')
        b=a.replace(b'<ele>',b' <ele>')
        self.assertEqual(compare(a,b)['status'],'complete')

    def test_point_order_duplicate_count_and_spelling_fail_closed(self):
        original=[point('1','2'),point('3','4'),point('1','2')]
        for changed in [list(reversed(original[:2]))+original[2:],original[:-1],original+[original[-1]],
                        [point('1.0','2')]+original[1:],[point('1','2','<ele/>')]+original[1:]]:
            result=compare(document(original,{1}),document(changed))
            self.assertEqual(result['status'],'unsupported');self.assertIsNone(result['summary']);self.assertEqual(result['seams'],[])

    def test_ignored_metadata_must_not_be_advertised_as_equal(self):
        a=document([point()],extra='<metadata><desc>old</desc></metadata>')
        b=document([point()],extra='<metadata><desc>new</desc></metadata><wpt lat="8" lon="8"/><rte/>',name='changed')
        result=compare(a,b)
        self.assertEqual(result['verdict'],'boundaries_unchanged')
        self.assertIn('not compared',result['metadata_note'])
        self.assertNotEqual(result['before']['sha256'],result['after']['sha256'])


class NamespaceIdentityReview(unittest.TestCase):
    def scoped(self,body,bindings='xmlns:p="urn:a"'):
        return document([point(body=body)]).replace(b'creator="adversarial tests"',('creator="adversarial tests" '+bindings).encode())

    def test_qname_attribute_text_and_unknown_point_attribute_fail_closed(self):
        for body in ['<extensions><x:n xmlns:x="urn:ext" kind="p:T"/></extensions>',
                     '<extensions><x:n xmlns:x="urn:ext">p:T</x:n></extensions>']:
            a=self.scoped(body);b=a.replace(b'urn:a',b'urn:b')
            result=compare(a,b)
            self.assertEqual(result['status'],'unsupported');self.assertIsNone(result['summary'])
        a=self.scoped('').replace(b'lat="0"',b'kind="p:T" lat="0"')
        self.assertEqual(compare(a,a.replace(b'urn:a',b'urn:b'))['status'],'unsupported')

    def test_unicode_combining_prefix_and_unused_binding_change_are_conservative(self):
        prefix='p\u0301'
        a=self.scoped('<extensions><x:n xmlns:x="urn:ext" kind="'+prefix+':T"/></extensions>',bindings='xmlns:'+prefix+'="urn:a"')
        self.assertEqual(compare(a,a.replace(b'urn:a',b'urn:b'))['status'],'unsupported')
        a=self.scoped('<extensions><x:n xmlns:x="urn:ext">ordinary text</x:n></extensions>')
        self.assertEqual(compare(a,a.replace(b'urn:a',b'urn:b'))['status'],'unsupported')

    def test_default_namespace_changes_on_unprefixed_qname_values_fail_closed(self):
        a=(f'<g:gpx xmlns:g="{e.NS}" xmlns="urn:a" xmlns:x="urn:ext" version="1.1" creator="test">'
           '<g:trk><g:trkseg><g:trkpt lat="0" lon="0"><g:extensions><x:n kind="Type"/>'
           '</g:extensions></g:trkpt></g:trkseg></g:trk></g:gpx>').encode()
        self.assertEqual(compare(a,a.replace(b'urn:a',b'urn:b'))['status'],'unsupported')

    def test_shadowed_bindings_use_local_scope_and_sibling_scope_restores(self):
        a=self.scoped('<extensions><x:n xmlns:x="urn:ext" xmlns:p="urn:fixed">p:T</x:n></extensions>')
        self.assertEqual(compare(a,a.replace(b'urn:a',b'urn:b'))['status'],'complete')
        a=self.scoped('<extensions><x:n xmlns:x="urn:ext" xmlns:p="urn:fixed">p:T</x:n><x:n xmlns:x="urn:ext">p:T</x:n></extensions>')
        self.assertEqual(compare(a,a.replace(b'urn:a',b'urn:b'))['status'],'unsupported')

    def test_extension_attribute_order_entity_spelling_and_declaration_order_normalize(self):
        a=self.scoped('<extensions><x:n xmlns:x="urn:ext" a="1" b="2">A &amp; B</x:n></extensions>')
        b=a.replace(b'a="1" b="2"',b'b="2" a="1"').replace(b'&amp;',b'&#38;')
        self.assertEqual(compare(a,b)['status'],'complete')
        b=a.replace(b'xmlns:p="urn:a"',b'xmlns:q="urn:a"')
        self.assertEqual(compare(a,b)['status'],'unsupported')

    def test_gpx_only_namespace_prefix_changes_still_normalize(self):
        a=document([point(body='<ele>1</ele><time>2026-01-01T00:00:00Z</time>')])
        b=a.replace(b'xmlns="',b'xmlns:g="')
        for tag in ('gpx','trk','trkseg','trkpt','ele','time','name'):
            b=b.replace(('<'+tag).encode(),('<g:'+tag).encode()).replace(('</'+tag+'>').encode(),('</g:'+tag+'>').encode())
        self.assertEqual(compare(a,b)['status'],'complete')

    def test_namespace_declarations_active_bindings_and_lengths_are_bounded(self):
        declarations=lambda start,n: ' '.join(f'xmlns:p{i}="urn:p{i}"' for i in range(start,start+n))
        a=document([point()]).replace(b'<trk>',('<trk '+declarations(0,33)+'>').encode())
        with self.assertRaises(e.InputError):e.parse_gpx(a)
        a=document([point()]).replace(b'<trk>',('<trk '+declarations(0,32)+'>').encode()).replace(b'<trkseg>',('<trkseg '+declarations(32,32)+'>').encode())
        with self.assertRaises(e.InputError):e.parse_gpx(a)
        for bindings in ['xmlns:p="'+('a'*4097)+'"', 'xmlns:'+('p'*1025)+'="urn:a"']:
            with self.assertRaises(e.InputError):e.parse_gpx(self.scoped('',bindings))

    def test_namespace_context_tuple_shared_across_point_fanout(self):
        a=document([point(body='<extensions><x:n>Type</x:n></extensions>') for _ in range(1000)])
        a=a.replace(b'creator="adversarial tests"',b'creator="adversarial tests" xmlns:x="urn:ext" xmlns:p="urn:a"')
        doc=e.parse_gpx(a)
        contexts=[]
        def collect(signature):
            if signature[0]=='{urn:ext}n':contexts.append(signature[-1])
            for child,_tail in signature[3]:collect(child)
        for item in doc.tracks[0].points:collect(item.signature)
        self.assertEqual(len(contexts),1000)
        self.assertEqual(len({id(value) for value in contexts}),1)


class ParserAdversarialReview(unittest.TestCase):
    def test_encoded_dtd_xxe_and_include_cannot_load_resources(self):
        base=document([point()])
        bodies=[b'<!DOCTYPE gpx SYSTEM "file:///tmp/segment-seam-no-read">'+base,
                b'<!DOCTYPE gpx [<!ENTITY xx SYSTEM "http://127.0.0.1:9/">]>'+base,
                b'<!DOCTYPE gpx [<!ENTITY a "x"><!ENTITY b "&a;&a;">]>'+base,
                base.replace(b'<trk>',b'<trk><extensions><xi:include xmlns:xi="http://www.w3.org/2001/XInclude" href="file:///tmp/no-read"/></extensions>'),
                base.decode().encode('utf-16'),base.decode().encode('utf-32')]
        with patch('socket.create_connection',side_effect=AssertionError('network attempted')):
            for body in bodies:
                with self.subTest(body=body[:80]),self.assertRaises(e.InputError):e.parse_gpx(body)

    def test_processing_instruction_after_declaration_and_encoding_mismatch(self):
        base=document([point()])
        for body in [b'<?xml version="1.0"?><?danger x?>'+base,
                     b'<?xml version="1.0" encoding="ISO-8859-1"?>'+base,
                     b'<?xml version="1.0" encoding="UTF-16"?>'+base,
                     base+b'<?extra x?>']:
            with self.assertRaises(e.InputError):e.parse_gpx(body)
        self.assertEqual(len(e.parse_gpx(b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>'+base).tracks),1)

    def test_recognized_trackpoint_nested_or_misplaced_rejected(self):
        for extra in ['<extensions>'+point()+'</extensions>',
                      '<metadata><extensions>'+point()+'</extensions></metadata>',
                      '<extensions><trk><trkseg>'+point()+'</trkseg></trk></extensions>']:
            with self.subTest(extra=extra),self.assertRaises(e.InputError):e.parse_gpx(document([point()],extra=extra))
        for body in ['<extensions>'+point()+'</extensions>','<ele>'+point()+'</ele>']:
            with self.assertRaises(e.InputError):e.parse_gpx(document([point(body=body)]))

    def test_empty_structural_tags_outside_direct_paths_rejected(self):
        for extra in ['<extensions><trk/></extensions>', '<metadata><trkseg/></metadata>',
                      '<extensions><trk><trkseg/></trk></extensions>']:
            with self.subTest(extra=extra),self.assertRaises(e.InputError):
                e.parse_gpx(document([point()],extra=extra))

    def test_namespace_range_structure_duplicates_and_nonfinite_are_rejected(self):
        base=document([point()])
        variants=[base.replace(e.NS.encode(),b'http://www.topografix.com/GPX/1/0'),base.replace(b'version="1.1"',b'version="1.0"'),
                  base.replace(b'<trkseg>',b'<trkseg xmlns="urn:wrong">'),base.replace(b'<trkpt lat="0" lon="0">',b'<trkpt lat="0" lat="1" lon="0">')]
        variants += [document([point(lat,lon)]) for lat,lon in [('nan','0'),('Infinity','0'),('0','180'),('1e1','0'),('0','0x10'),('0','0\x00')]]
        for variant in variants:
            with self.subTest(variant=variant[-120:]),self.assertRaises(e.InputError):e.parse_gpx(variant)

    def test_actual_byte_depth_node_point_and_output_limits(self):
        with self.assertRaises(e.InputError):e.parse_gpx(b' '*(e.MAX_BYTES+1))
        deep='<extensions>'+'<x>'*31+'</x>'*31+'</extensions>'
        with self.assertRaises(e.InputError):e.parse_gpx(document([point(body=deep)]))
        with self.assertRaises(e.InputError):e.parse_gpx(document([point()]*(e.MAX_POINTS+1)))
        nodes='<extensions>'+'<x/>'*e.MAX_NODES+'</extensions>'
        with self.assertRaises(e.InputError):e.parse_gpx(document([point()],extra=nodes))
        report=compare(document([point(),point('1','1')],{1}),document([point(),point('1','1')]))
        report['metadata_note']='x'*e.MAX_OUTPUT
        with self.assertRaises(e.InputError):e.packet_bytes(report)

    def test_seam_union_limit_never_returns_partial_metrics(self):
        points=[point() for _ in range(4000)]
        result=compare(document(points,range(1,2000)),document(points,range(2000,3999)))
        self.assertEqual(result['status'],'unsupported');self.assertIsNone(result['summary'])
        self.assertEqual(result['seams'],[]);self.assertIs(result['witnesses_truncated'],False)

    def test_raw_blank_absent_and_nonsemantic_fields_distinct(self):
        a=document([point(body='<ele> \n </ele><time/>'),point('1','1')],{1})
        result=compare(a,a);left=result['seams'][0]['left'];right=result['seams'][0]['right']
        self.assertEqual(left['elevation'],dict(state='raw',text=' \n '))
        self.assertEqual(left['time'],dict(state='raw',text=''))
        self.assertEqual(right['elevation'],dict(state='absent',text=None))

    def test_packet_integrity_and_safe_member_names(self):
        source=document([point('0','0'),point('0','.01')],{1})
        report=compare(source,source,before_name='../../danger\n.gpx')
        archive=zipfile.ZipFile(io.BytesIO(e.packet_bytes(report)))
        self.assertEqual(archive.namelist(),['report.json','report.txt','manifest.json'])
        manifest=json.loads(archive.read('manifest.json'))
        for member in manifest['files']:
            payload=archive.read(member['path'])
            self.assertEqual(hashlib.sha256(payload).hexdigest(),member['sha256'])
            self.assertEqual(len(payload),member['bytes'])
        self.assertEqual(json.loads(archive.read('report.json'))['before']['name'],'danger_.gpx')


def capture_worker_limits(events):
    from segment_seam import runner
    def capture(*args,**kwargs):
        return {name:resource.getrlimit(getattr(resource,name)) for name in
                ('RLIMIT_AS','RLIMIT_CPU','RLIMIT_FSIZE','RLIMIT_NOFILE')}
    runner.run_files=capture
    runner._worker(None,None,None,{},events)


class RuntimeCancellationReview(unittest.TestCase):
    def wait_terminal(self,job):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            status=job.snapshot()['status']
            if status!='running':return status
            time.sleep(.02)
        self.fail('worker did not finish within test deadline')

    def test_actual_spawned_worker_resource_limits(self):
        context=mp.get_context('spawn');events=context.Queue()
        process=context.Process(target=capture_worker_limits,args=(events,))
        process.start()
        try:
            self.assertEqual(events.get(timeout=5)[0],'progress')
            kind,limits=events.get(timeout=5)
            self.assertEqual(kind,'done')
            self.assertEqual(limits['RLIMIT_AS'],(512*1024*1024,)*2)
            self.assertEqual(limits['RLIMIT_CPU'],(20,20))
            self.assertEqual(limits['RLIMIT_FSIZE'],(16*1024*1024,)*2)
            self.assertEqual(limits['RLIMIT_NOFILE'],(32,32))
            process.join(timeout=5);self.assertEqual(process.exitcode,0)
        finally:
            if process.is_alive():process.kill();process.join(timeout=3)
            events.close();events.join_thread()

    def test_partial_input_write_failure_removes_temporary_input(self):
        original=Path.write_bytes
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)/'job';work.mkdir()
            def write(path,blob):
                if path.name=='after.gpx':raise OSError('simulated storage exhaustion')
                return original(path,blob)
            with patch('segment_seam.runner.tempfile.mkdtemp',return_value=str(work)),patch.object(Path,'write_bytes',write):
                with self.assertRaises(OSError):Job(document([point()]),document([point()]),mode='inspect')
            self.assertFalse(work.exists())

    def test_done_cancel_deletes_sources_packet_and_result(self):
        blob=document([point('0','0'),point('0','.1')],{1})
        job=Job(blob,blob,mode='compare',before_track=1,after_track=1,confirmed=True)
        try:
            self.assertEqual(self.wait_terminal(job),'done',job.snapshot())
            self.assertTrue((job.work/'packet.zip').is_file())
            self.assertEqual(job.work.stat().st_mode&0o777,0o700)
            result=job.cancel()
            self.assertEqual(result['status'],'cancelled');self.assertNotIn('result',result)
            self.assertFalse(job.work.exists());self.assertFalse(job.process.is_alive())
        finally:job.close()

    def test_replacement_removes_old_job_and_close_removes_current(self):
        blob=document([point()]);manager=JobManager()
        try:
            a=manager.start(blob,blob,mode='inspect');self.assertEqual(self.wait_terminal(a),'done')
            b=manager.start(blob,blob,mode='inspect')
            self.assertFalse(a.work.exists());self.assertIsNone(manager.get(a.id));self.assertIs(manager.get(b.id),b)
            manager.close();self.assertFalse(b.work.exists());self.assertFalse(b.process.is_alive())
        finally:manager.close()


if __name__=='__main__':unittest.main()
