# Security and privacy scope

## Inputs and XML

- 4 MiB/file; 20,000 recognized GPX points; 256 tracks; 2,000 segments; 120,000 XML nodes; depth 32
- Each element has at most 32 combined attributes/namespace declarations and at most 64 active namespace bindings; namespace prefixes at most 1,024 characters and URIs at most 4,096; attribute values at most 4,096 characters; each text/tail at most 8,192; track name at most 240; coordinate text at most 64
- Strict UTF-8, official GPX 1.1 namespace/version/creator. Finite legal-range decimal lat/lon only. GPX longitude's upper bound is exclusive (+180 rejected, −180 accepted)
- DTD and entity declarations are rejected before parsing, including conservative matches in comments. Predefined/numeric XML character references remain supported. Processing instructions (other than initial XML declaration) and XInclude are rejected
- XML parser never fetches URLs, external DTDs or schemas. GPX links/schema-location attributes are inert, excluded metadata. Their presence does not authorize a fetch
- Python's [XML security documentation](https://docs.python.org/3/library/xml.html#xml-security) warns about hostile XML; the application adds byte/structure limits and isolated-process ceilings rather than claiming a general safe XML parser. Use an up-to-date supported Python build

## Execution and local server

Both CLI and UI use a disposable spawned process: 30 s wall clock, 20 s CPU, 512 MiB virtual address space, 16 MiB per output file, 32 file descriptors. The parent kills its own worker on cancellation, timeout or error. Limits are POSIX-specific; Linux is the tested target. It is process isolation with resource ceilings, not an OS/network sandbox.

The server binds only to 127.0.0.1. A 256-bit random capability path is required; Host must match the bound IP+port; foreign Origin and cross-site Fetch Metadata are rejected. No CORS grant is sent. Fixed asset allowlist prevents path traversal. Strict Content-Type/length/base64/field checks precede job creation. Only one current job is kept. ZIP downloads require a completed comparison; inventory has no download.

CSP permits same-origin assets/connections only, disables objects/forms/framing; no third-party fonts, map tiles, analytics or external code. File names and GPX strings are untrusted and must be rendered as text. The API does not interpret user paths: uploaded bytes are written under fixed names inside mode-0700 temporary directories.

## Evidence and retention

JSON/text payloads must total at most 12 MiB; no truncated complete verdict. Inputs are not included in report ZIPs, but SHA-256 hashes and exact boundary endpoint coordinates are. A hash is an identifier, not a digital signature or authenticity proof. ZIP manifests verify internal contents only.

Cancel applies to completed/error jobs as well as running jobs and discards their artifacts. New jobs replace previous terminal jobs. Normal shutdown removes temporary inputs/output. Force-kill, power loss, disk recovery, swap, browser memory/history, screenshots and the user's saved ZIPs are outside secure-erasure guarantees. The capability URL and downloads are private. Do not expose this server over a network or paste genuine GPS reports into public issues.

## Browser verification

Playwright must launch with `chromiumSandbox: true`. If a machine disallows sandboxed browser startup, report the failed stage; do not remove the sandbox or change security settings to bypass it. CI currently uses Ubuntu 22.04; migrate before the published 2027-04-17 retirement and re-verify sandbox behavior.
