# RTF reading view: local test data only

Everything under this directory is **test data for the RTF reading view** and must never
be part of a public release. `scripts/build-release.py` copies only its own allowlist and
`tests/test_rtf_reading.py` checks that no file from here reaches a packaged release.

- `real/` holds three development examples from preserved CD data, delivered with
  Stian's work order on 2026-09-25 (not a complete data or release package):
  - `k37.json` — WinAmp 2.76, K-CD 15/2001: short menu description, longer RTF text.
  - `kcd-1-2001--k1.json` — Asterix, K-CD 1/2001: the menu description *is* the RTF text.
  - `kcd-8-2001--k5.json` — Freesaver MP3, K-CD 8/2001: `text: null`
    (unsupported RTF font charset), original still published.
  - `store/documents/sha256/…` — the original RTF bytes for those three entries,
    unchanged (SHA-256 equals the file name).
  The entry JSON is byte-identical to the delivery; the fixture site builder drops the
  `assets` list in its served copy only, because the image bytes were not delivered.
- `tests/rtf_reading_fixtures.py` adds the synthetic cases (titles start with
  `TESTDATA`), builds the RTF bytes for them and writes a servable site. Preview with:

      python tests/rtf_reading_fixtures.py NEW_DIRECTORY
      python -m http.server 8814 --directory NEW_DIRECTORY
