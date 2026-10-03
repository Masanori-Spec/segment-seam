# Verification record

Development date: 2026-10-03. This record distinguishes executed checks from staged checks.

## Locally executed

- Python parser/engine/packet tests: scoped topology, mismatch refusal, exact witnesses, malformed XML, entity/DTD/include rejection, range/encoding/structure/resource limits, deterministic packet manifests
- Real spawned-process tests: inspect/compare, cancellation before/after completion, replacement, worker crash and wall-time ceiling
- Real loopback HTTP tests: capability path, Host/Origin/Fetch-Metadata checks, upload validation, inspect/no-packet, compare/download/cancel
- CLI subprocess tests: inspect, changed/unchanged/unsupported exit statuses and exclusive output creation
- Final local aggregate: 85 Python tests passed, 21 Node model/controller tests passed; Python compileall and JS syntax checks passed
- 31 independent-review tests include 900 seeded global/near-antipodal pairs versus a vector-atan2 oracle (absolute disagreement ≤ 1e−7 m in this corpus), plus 160 generated segmentation pairs for boundary algebra and exact witnesses
- Independent regressions cover leaf/mixed XML text, inherited xml:space, namespace rebinding/default/Unicode/alias changes, namespace scope limits/sharing, malformed structural paths, partial-input cleanup, and actual spawned Linux hard/soft resource-limit values
- A real bounded worker also completed a 20,000-point comparison at the supported point limit
- npm ci with a writable temporary cache succeeded; no browser installation/startup was attempted locally

The synthetic [benchmark.json](benchmark.json) records the actual local Python/platform and measured durations/peak traced Python allocations. It is an in-process engine benchmark, excludes child-start overhead, and is not total RSS. It covers 100/1,000/10,000/20,000 points; it is not a promise for adversarial or arbitrary files.

## Browser stage

Local Chromium is blocked by the execution environment. No security bypass or unsandboxed browser run is used. Playwright mock race checks and real local-worker workflows are prepared for CI with `chromiumSandbox: true`, screenshot artifacts and responsive desktop/mobile coverage. The mock suite contains 12 scenarios; the real suite exercises fixture uploads, actual Python workers, report ZIP contents, Japanese/mobile layouts, unsupported outcomes and server-side stale-artifact deletion. Focused/unfocused skip-link screenshots and scroll regressions are included. **Browser success and screenshots are pending exact-commit CI execution and inspection.** A source archive alone is not evidence of UI success.

## CI plan

`.github/workflows/ci.yml` runs Python 3.12/3.13 core checks, Node model/syntax checks, a synthetic benchmark, sandboxed mock UI tests and real-backend browser tests. It uploads browser evidence even on failure.

Ubuntu 22.04 is a temporary known-working sandbox runner, not a security bypass. GitHub announces retirement on 2027-04-17: https://github.com/actions/runner-images/issues/14254. Migrate to a supported image before retirement and verify actual sandboxed execution. Never silently set `chromiumSandbox: false`.

## Remaining limits

Linux target only; no claim of Windows/macOS support. No live personal GPS files, customer validation, hardware navigation testing or full GPX schema conformance suite. Report distances are numerical estimates on a declared sphere, not physical recording truth. This is not a penetration test or formal proof.
