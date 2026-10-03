# Verification record

Development date: 2026-10-03. This record distinguishes executed checks from staged checks.

## Locally executed

- Python parser/engine/packet tests: scoped topology, mismatch refusal, exact witnesses, malformed XML, entity/DTD/include rejection, range/encoding/structure/resource limits, deterministic packet manifests
- Real spawned-process tests: inspect/compare, cancellation before/after completion, replacement, worker crash and wall-time ceiling
- Real loopback HTTP tests: capability path, Host/Origin/Fetch-Metadata checks, upload validation, inspect/no-packet, compare/download/cancel
- CLI subprocess tests: inspect, changed/unchanged/unsupported exit statuses and exclusive output creation
- Final local aggregate: 85 Python tests passed, 22 Node model/controller tests passed; Python compileall and JS syntax checks passed
- 31 independent-review tests include 900 seeded global/near-antipodal pairs versus a vector-atan2 oracle (absolute disagreement ≤ 1e−7 m in this corpus), plus 160 generated segmentation pairs for boundary algebra and exact witnesses
- Independent regressions cover leaf/mixed XML text, inherited xml:space, namespace rebinding/default/Unicode/alias changes, namespace scope limits/sharing, malformed structural paths, partial-input cleanup, and actual spawned Linux hard/soft resource-limit values
- A real bounded worker also completed a 20,000-point comparison at the supported point limit
- npm ci with a writable temporary cache succeeded; no browser installation/startup was attempted locally

The synthetic [benchmark.json](benchmark.json) records the actual local Python/platform and measured durations/peak traced Python allocations. It is an in-process engine benchmark, excludes child-start overhead, and is not total RSS. It covers 100/1,000/10,000/20,000 points; it is not a promise for adversarial or arbitrary files.

## Exact-commit CI result

Executable code commit: [aa33673895dcddbe97ae43be9c46b799c9acea97](https://github.com/Masanori-Spec/segment-seam/commit/aa33673895dcddbe97ae43be9c46b799c9acea97). All three jobs passed in [run 37127171844](https://github.com/Masanori-Spec/segment-seam/actions/runs/37127171844). This record identifies the verified code revision; a later documentation-only commit can have a different hash.

- Python 3.12 and Python 3.13 core jobs: each passed all 85 Python tests, 22 Node tests, compile/syntax checks and synthetic benchmark generation
- Sandboxed Chromium mock suite: all 12 scenarios passed
- Real-browser/real-Python-worker suite: fixture upload, inspection, explicit track pairing, point witnesses, report download, Japanese/mobile layout, cancellation/removal of the old server artifact, unsupported point mismatch, restart and demo all passed
- Local browser execution was blocked by the development environment and was not attempted or bypassed. CI ran with `chromiumSandbox: true`; the sandbox was never disabled

## Browser coverage and evidence

The mock suite covers explicit pairing and affirmation, language changes, filtered witnesses, responsive layouts, hostile strings rendered as text, distinct empty/whitespace/absent raw fields, inspection errors/incomplete responses, worker errors, cancellation before the start response, double-click prevention, input/selection/swap/restart invalidation, file limits and inaccessible stale downloads. Visibility and fail-closed assertions remain enabled.

Keyboard-focused skip links were captured at desktop/mobile sizes. Unfocused clipping and scroll regressions passed. All nine captured PNGs were visually inspected, including desktop/mobile, English/Japanese, raw hostile-text wrapping, unsupported/no-metrics and focused-link states: no unintended unfocused skip-link overlay or horizontal overflow was observed. This is focused visual QA, not a full accessibility audit.

`browser-evidence` artifact ID: 11275732838. Downloaded artifact ZIP SHA-256: `41d02d51e3891e17e04eeacdb44cba2a0098797c60b9533143205cb49b52f140`.

Screenshots include desktop initial/evidence/Japanese, mobile Japanese evidence, desktop/mobile focused skip link, real desktop/mobile evidence, and the unsupported result. The artifact also contains `real-evidence.zip`. Its report JSON/text byte lengths and SHA-256 values were checked against its internal manifest. Report ZIP SHA-256: `d48285b63de14da69d7b9c8a91d9d83106bc6d9eb30f0f3a09d363211849ca13`.

The real synthetic report contains eight points, one removed/one added/one retained boundary, approximately 2,112.706524 m newly connected distance and 111.195080 m newly disconnected distance. These are the declared spherical estimates for the synthetic fixture, not physical travel measurements.

## CI-discovered correction

The first CI run reached sandboxed Chromium but failed after loading the demo: the controller invoked the stored native fetch method with the controller as its receiver. A receiver-enforcing Node regression reproduced an error instead of a completed inspection before the fix. The default fetch callback now invokes `globalThis.fetch` through a wrapper, preserving the browser global receiver for starts, polls and cancellation. The regression passes, as do all subsequent mock and real browser scenarios. Inventory validation and visible-result assertions were not relaxed. Inspection failure diagnostics now include status/error/request information and a screenshot.

## CI maintenance

`.github/workflows/ci.yml` uploads browser evidence even on failure. Ubuntu 22.04 is a temporary known-working sandbox runner, not a security bypass. GitHub announces retirement on 2027-04-17: https://github.com/actions/runner-images/issues/14254. Migrate to a supported image before retirement and verify actual sandboxed execution. Never silently set `chromiumSandbox: false`.

## Remaining limits

Linux target only; no claim of Windows/macOS support. No live personal GPS files, customer validation, hardware navigation testing or full GPX schema conformance suite. Report distances are numerical estimates on a declared sphere, not physical recording truth. This is not a penetration test or formal proof.
