# Practical difference and primary sources

Checked 2026-10-03. This is a bounded product hypothesis, not a patentability or comprehensive novelty claim.

## Existing workflows

[GPSBabel 1.10 track filter](https://www.gpsbabel.org/htmldoc-1.10.0/filter_track.html) documents operations including pack, merge, split, segment-to-track and track-to-segment conversion. Some operations reorder or remove points, so not every GPSBabel conversion falls inside this project's strict unchanged-point scope. The originally considered 1.9 URL redirects attention to newer documentation and labels itself obsolete.

[gpx.studio's crop and split help](https://gpx.studio/help/toolbar/scissors) explains splitting a trace into files, tracks or segments. Its [application](https://gpx.studio/app) also distinguishes connecting traces from merging contents while retaining disconnections. These capabilities already provide interactive editing; this project is not positioned as a new GPX editor.

The [GPX 1.1 schema documentation](https://www.topografix.com/GPX/1/1/) describes tracks made of segments and points, WGS84 coordinates, and metric measurements. A segment is an explicit structure, so a line drawn across a removed boundary is evidence about serialization/connectivity rather than proof of observed movement.

## Narrow useful difference

A person reviewing an export or conversion wants a repeatable answer to: which segment breaks were retained, removed or added, and what distance did each changed adjacency contribute? Segment Seam records the selected file hashes and track indices, refuses changed point sequences, and emits per-boundary point witnesses plus a compact reproducible report packet. It intentionally has no map and makes no network requests with GPS data.

This is complementary to editing tools. The practical differentiation is review evidence and conservative refusal, not novel splitting/merging algorithms. No claim is made that existing products lack every comparable capability.

## Bounded gate

Proceed because an eight-point fixture demonstrates a specific conversion defect that a whole-track total alone obscures: a large removed-boundary contribution and a smaller newly disconnected edge partially offset each other. Reviewers can inspect both contributions rather than seeing only a net delta. Stop/refuse when point counts, order or content differ; fuzzy identity would make those explanations unreliable.

Unvalidated business hypothesis: maintainers of conversion/import pipelines may value such regression packets. No customer interviews, willingness-to-pay evidence or legal/patent assessment has been collected.
