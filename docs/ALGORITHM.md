# Algorithm and evidence semantics

1. Check byte/UTF-8 limits, reject DTD/entity declarations, processing instructions and XML includes, then incrementally parse with depth/node/field limits. Only direct GPX 1.1 track/segment paths count as track data. No external resource is fetched.
2. Require explicit 1-based indices and an explicit same-logical-track confirmation. Names are labels; identical names do not establish identity.
3. Flatten each selected track while retaining a 1-based source segment number on every point. Empty tracks/segments yield unsupported outcomes because a point-adjacency model cannot faithfully represent their empty boundary multiplicity.
4. Compare the selected point sequences by normalized XML trees. Expanded namespace names and sorted attributes make ordinary GPX-only prefix/attribute ordering irrelevant. Nonempty extension/foreign values and unknown point attributes preserve all in-scope prefix-to-URI bindings; changed context causes conservative refusal without guessing QName types. Harmless prefix changes can therefore be unsupported for such content. Inherited xml:space is honored. Indentation-only inter-element text is omitted unless preservation is requested; leaf text and non-whitespace mixed content are exact. Comments and processing instructions are not compared (processing instructions are rejected). Point child order and every point attribute/extension field remain significant. A changed coordinate spelling can therefore cause conservative refusal.
5. For every adjacency between flattened points i and i+1, determine whether the segment number changes before and after. The union of boundaries yields three classes: removed (before only), added (after only), retained (both). The report shows both source segment-index pairs and exact endpoint coordinate/ele/time witnesses.
6. Measure each adjacency's horizontal spherical distance using Haversine and a declared fixed radius, with directly evaluated complementary half-angle for antipodal stability. Sum within-segment edges with `math.fsum`. Added connectivity is the sum at removed boundaries. Disconnected distance is the sum at added boundaries. Net change is their difference. The independently summed after-minus-before total agrees within floating-point tolerance.
7. Emit all witnesses within bounds or no numeric conclusion. Never cap the list while emitting a complete verdict. The packet holds JSON, human-readable bilingual-titled text and their byte-length/SHA-256 manifest. Fixed ZIP timestamps make identical report packets byte-reproducible.

## Distance is a declared model

The radius 6,371,008.8 m is a chosen mean-Earth spherical model, not a claim of surveyed precision. GPX's WGS84 coordinate convention does not turn the calculation into a WGS84 ellipsoid solution. Elevation and timestamps remain raw text; their types are not validated and no elapsed-time/speed/ascent calculation is attempted. No interpolation is introduced.

A removed zero-distance boundary still counts as a topology change. A retained boundary's distance is shown as an endpoint gap, never added to before/after segment totals. Reversing comparison swaps added/removed sets and changes the sign of the net distance delta.

## What is not proven

No review of excluded file/track/segment metadata, routes, waypoints or unselected tracks, except inherited xml:space and namespace bindings needed for point identity. A point-content comparison is not full XSD validation. Sequence identity plus user-selected pairing does not prove that two files represent the same real-world recording. Artificial edges describe newly connected serialization only; no movement, route suitability or safety inference follows.
