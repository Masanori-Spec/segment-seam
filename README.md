# Segment Seam

A local before/after GPX conversion review: show which segment boundaries disappeared, which new connecting edges they introduced, and how much horizontal distance those edges contribute.

GPX editors already split and join traces. This tool answers a narrower review question: **“The point sequence stayed the same. What did this conversion change about connectivity?”** It does not edit GPX or decide whether a route is safe.

## 日本語

GPX変換前後の「セグメント境界」を、手元のPCだけで比較するツールです。消えた境界・追加された境界・維持された境界を、隣接する点番号と座標で確認できます。境界の消失によって新たにつながる線分について、水平距離の寄与を計算します。

- 変換前と変換後から、同じ論理トラックを明示的に選択します
- 点の順序や内容が変わっていた場合は、近似照合せず「比較対象外」と表示します
- 地図・外部API・テレメトリーは使いません。位置データはローカル処理のみです
- レポートには正確な座標が含まれます。共有前に内容を確認してください
- 完全なGPX一致・実際の移動距離・経路の安全性を保証するものではありません

## Run locally

Requirements: **Python 3.12+ on Linux**. The application uses only the Python standard library; no pip install, account, map token or runtime download. POSIX process resource limits are required. macOS and Windows are not verified targets.

From the extracted project folder:

```sh
python -m segment_seam serve
```

Open the printed private `http://127.0.0.1:.../<random-token>/` address if a browser does not open automatically. Keep that URL private. Press Ctrl+C in the terminal to stop the worker and clean its temporary input files. Do not put this server behind a proxy or expose its port.

### Workbench workflow

1. Choose before and after GPX files, or load the synthetic demo
2. Inspect the files to see track indices, names, point counts and segment counts
3. Select the intended before/after tracks and explicitly confirm that they represent the same logical track. Names are contextual labels, not identity proofs
4. Compare. Review removed boundaries/new connections, added boundaries/disconnections and retained boundaries
5. Inspect exact adjacent point witnesses and download the JSON/text ZIP evidence report

Files and selections changing invalidate the current report. Cancel stops the disposable worker and removes its local artifacts. Starting another job replaces the previous artifacts. A downloaded ZIP remains wherever you saved it.

The UI switches between English and Japanese without discarding the current comparison. No map is shown; the boundary diagram represents point adjacency, not geography.

## CLI

List tracks first:

```sh
python -m segment_seam inspect fixtures/before.gpx fixtures/after.gpx
```

Explicitly compare track 1 against track 1:

```sh
python -m segment_seam compare fixtures/before.gpx fixtures/after.gpx \
  --before-track 1 --after-track 1 --confirm-same-track \
  --output review.zip
```

Both CLI commands use the same bounded subprocess as the workbench. The output path must be new; existing files are never overwritten. Exit codes: `0` = scoped boundaries unchanged, `1` = boundaries changed, `2` = unsupported input/comparison or processing error. A valid but unsupported comparison can still produce a reasons-only packet. An input/parser/worker error produces no packet.

The synthetic demo deliberately has:

- One removed boundary at points **2 → 3**, adding approximately **2,112.707 m** of connecting-edge distance
- One added boundary at **6 → 7**, removing approximately **111.195 m** of connecting-edge distance
- One retained boundary at **4 → 5**, still disconnected
- A net horizontal segment-distance change of approximately **+2,001.511 m**

These are synthetic equatorial coordinates, not a recorded route or a travel claim. The added edge is “artificial” only in the structural sense that the after-file now connects formerly disconnected adjacent points. It does not establish whether movement actually occurred.

## Supported scope

- UTF-8 GPX **1.1** with the official namespace, version and creator attribute
- One explicitly selected track from each file; file track order may differ
- Exactly the same number of points, same order, and same normalized XML point content
- Nonempty selected tracks and nonempty segments
- GPX-only namespace prefix names, attribute order and indentation between child elements are normalized. Leaf text, attribute values, child order and non-whitespace mixed content are preserved. Inherited xml:space is honored. Nonempty extension/foreign values and unknown point attributes additionally retain all namespace bindings; even harmless prefix-context changes may be refused. Numeric reformatting, timestamp rewriting or extension-content changes are unsupported, even when they may be semantically equivalent
- Latitude and longitude use finite GPX decimal syntax and legal ranges; elevation/time are preserved **raw XML-decoded text**, not asserted-valid decimal/dateTime values and not used in calculations
- Other tracks, file/track/segment metadata, waypoints and routes are excluded from the comparison, except inherited xml:space and namespace context needed for point identity. Input hashes identify the full bytes, but do not mean those excluded fields were reviewed
- No full GPX XSD validation, point reconciliation, resampling, reorder detection, distance-based matching or repair

“Complete” means this restricted boundary analysis completed. “Boundaries unchanged” means no boundary changed in the selected unchanged point sequence. Neither is a general GPX pass. Empty segments or a point-content mismatch yield an explicit unsupported outcome with no numeric summary or inferred connections.

### Distance method

Horizontal **Haversine great-circle** distance on a sphere of radius **6,371,008.8 m**. A directly computed complementary half-angle keeps near-antipodal results stable. This is not a WGS84 ellipsoidal inverse solution, 3D distance, cumulative ascent, elapsed time, speed, or measured travel distance. GPX coordinates use WGS84; the deliberately simpler spherical model is declared in every report. See [algorithm](docs/ALGORITHM.md) and [independent test coverage](docs/VERIFICATION.md).

### Limits and privacy

Each input: 4 MiB, 20,000 track points, 256 tracks, 2,000 segments, 120,000 XML nodes, depth 32, 64 active namespace bindings and 32 combined attributes/namespace declarations per element. Reports: at most 2,000 unique boundary witnesses and 12 MiB of uncompressed JSON/text. Each job: 30 seconds wall time, 20 seconds CPU and 512 MiB address space. Exceeding a limit is an error or unsupported result, never a truncated success.

DTD/entity declarations, processing instructions and XInclude are rejected. Predefined/numeric XML character references are decoded by the parser. Ordinary GPX links and schema hints are inert data; no URL is fetched and no remote schema is loaded. See [security scope](docs/SECURITY.md).

Input files are temporarily stored in a private local directory. The server has no telemetry or request logging, uses a capability path plus host/origin checks, and serves only fixed assets and current-job output. Closing/cancelling cleans temporary files during normal operation; force-kill, OS crash, swap, backups and browser history are outside secure-erasure guarantees. Reports contain exact GPS coordinates and can be sensitive.

## Verify

```sh
python -m unittest discover -s tests -v
python -m compileall -q segment_seam tests scripts
npm ci --ignore-scripts
npm test
npm run check:syntax
npx playwright install --with-deps chromium
npm run test:browser
npm run test:browser:real
python scripts/benchmark.py --out benchmark-ci.json
python scripts/package_source.py --out ../segment-seam-output
```

Node 22 and pinned Playwright are development-only dependencies. Browser tests launch Chromium with its sandbox enabled and capture desktop/mobile screenshots. They are not claimed to pass until the exact revision's CI evidence is inspected. [Verification status](docs/VERIFICATION.md) distinguishes passed checks from pending browser checks.

CI currently uses Ubuntu 22.04 to preserve sandboxed browser execution. That runner is scheduled for retirement on **2027-04-17**; migrate and re-verify the sandbox on a supported runner before then. [GitHub notice](https://github.com/actions/runner-images/issues/14254)

## Project notes

- [Why this bounded workflow is useful; existing products](docs/PRIOR_ART.md)
- [Algorithm and evidence semantics](docs/ALGORITHM.md)
- [Security and operating limits](docs/SECURITY.md)
- [Synthetic demo walkthrough](docs/DEMO_WALKTHROUGH.md)
- [Local API contract](docs/API.md)
- [Verification and benchmark](docs/VERIFICATION.md)
- [Dependencies and attribution](docs/THIRD_PARTY.md)

No project license has been selected. Public source visibility alone does not grant a license to reuse it.
