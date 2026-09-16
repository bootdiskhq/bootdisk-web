# 0.1.0-rc1 production validation

Validated 2026-09-16 from the authoritative K-CD 15/2001 Ingest, Catalog and Publish outputs.

## Inputs

| Input | SHA-256 |
| --- | --- |
| `kcd15-2001-manifest.json` | `ae29b1d2976ee7c7439b2e12fe18b774d1d57e77c9a20bc3567d2e5079257281` |
| `catalog.tar.gz` | `d9086d8ca4bc869ca21153342167cd1096c8cba7042ecdaf6257c1d7e30e035d` |
| `published.tar.gz` | `50b04852dc9d2807aaec702e50c2e46806bd21763c61ec8f412f80fc318c42c3` |

## Results

- 39 Ingest entries matched 39 archive cards and 39 detail documents.
- Source ids span K1–K42; K2, K28 and K36 are absent from the source manifest.
- 77 asset projections were joined: 39 screenshots and 38 icons.
- The closed release directory contains 136 unique referenced files under `store/`.
- All 136 content-addressed files matched the SHA-256 encoded in their filename.
- K37 rebuilt as curated Winamp 2.76; the other 38 entries remained honestly pending.
- The archive overview, index JSON and K37 detail page passed an HTTP smoke test.
- The repository contract suite passed 9/9 tests after the production build.

## Artifact

`bootdisk-web-0.1.0-rc1.zip` contains the deployable `bootdisk-web/` directory.

- Uncompressed web root: 3,683,511 bytes
- ZIP SHA-256: `d2485013b943c57e5302c41d370cf13fffad09098c9a4835ddacf578cec7d0a2`

This satisfies the repository's RC gate. Promotion to `0.1.0` requires only a visual smoke test on the target host and no blocking defects.
