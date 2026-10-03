# Five-minute review walkthrough / デモ手順

## The question

A recorder exported three GPX segments. A converter kept all eight points but changed two boundaries. A simple point count says “8 → 8”; a distance total shows a net increase. Neither identifies the new connection by itself.

The included coordinates are wholly synthetic. They do not describe a person's trip.

## Steps

1. Run `python -m segment_seam serve`
2. Choose **Try a synthetic example** / **架空のサンプルを試す**
3. After inspection, select track 1 in both files and confirm the same logical track
4. Run the segment review
5. Open the removed witness at point 2 → 3. Before segment pair is 1 → 2; after is 1 → 1. The latitude remains 0 and the longitude jumps from 0.001 to 0.020. That newly connected edge contributes about 2,112.707 m in the declared sphere model
6. Inspect point 6 → 7: it changed from within segment 3 to between segments 2 and 3, removing about 111.195 m of connectivity
7. Inspect point 4 → 5: still a boundary, so its endpoint gap is excluded from both connected-distance totals
8. Download the ZIP. `report.json` is the machine-readable result; `report.txt` is the readable counterpart; `manifest.json` contains their SHA-256 and byte lengths

## Test a conservative refusal

Replace the after file with `fixtures/changed-point.gpx`. The third longitude is different. Reinspect, select and confirm the pair. The result is unsupported, with no boundary metrics. It cannot pretend that point 3 retained its identity merely because the coordinate is nearby.

## What to discuss in a portfolio review

- Product boundary: a conversion evidence reviewer, complementary to existing GPX editors
- Trust decision: user-selected pairing plus exact point-content equality, no fuzzy matching
- Numerical work: explicit sphere model, complementary Haversine near antipodes, independent vector-geometry oracle tests
- Failure handling: scoped refusal, bounded parsing/processes, cancellable jobs and stale-report invalidation
- Privacy: no map/provider requests, local report generation, exact-coordinate sensitivity disclosed
- Evidence: reproducible packets, hashes, adversarial tests, CI and inspected responsive screenshots

No customer value, market demand or patentability conclusion has been validated.
