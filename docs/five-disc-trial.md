# Five-disc scaling trial — 1.2.0-rc3

The archive grows from 60 entries on two discs to 178 on seven discs. The 118
new entries remain pending identification; source descriptions and images are
published without manufacturing identity/version/distribution approvals.

| New medium | Entries | Original descriptions | CD images | Original icons |
|---|---:|---:|---:|---:|
| K-CD 4/2000 | 16 | 16 | 16 | 13 |
| K-CD 9/2000 | 20 | 18 | 20 | 17 |
| K-CD 13/2000 | 16 | 16 | 16 | 13 |
| K-CD 8/2001 | 32 | 32 | 32 | 32 |
| K-CD 1/2001 | 34 | 33 | 32 | 33 |

There are 172 original descriptions and 576 unique public image objects across
the complete seven-disc release. Counts describe the qualified menu projection,
not a claim that every executable on each CD has been identified.

## Problems found and corrected

- 4/2000, 9/2000 and 13/2000: cropped original icons were excluded by a 32×32
  constraint. The qualified selector now accepts unique 16–32px title-row images,
  excluding 38px menu decoration and retaining ambiguity checks.
- 8/2001 and 1/2001: Shot.bmp was absent from discovery. JPG remains preferred;
  BMP is used when JPG is absent. This recovered 49 screenshots.
- 8/2001: case aliases such as ModemBoost/Modemboost collided during extraction
  on macOS. A verified copy of the same source is reused while both manifest
  spellings remain recorded.
- 1/2001: the original descriptions reside in No.rtf, not DTX Global. Ingest
  preserves exact RTF bytes and a bounded plain-text view; Catalog verifies the
  provenance before presenting it. All 33 texts matched independent textutil
  conversion exactly, including whitespace.
- 13/2000: macOS lists three semicolon-containing HTML filenames that cannot be
  opened through its mounted view. A separate bsdtar ISO extraction completed
  and was ingested instead. No files were skipped to make inventory pass.

## Remaining source/qualification limits

- Each Director disc has three game entries without a qualified original-icon
  binding. Their CD image is used as a thumbnail, retaining screenshot identity.
- 1/2001 Intercent: no description/image/icon at its declared asset location.
  Acrobat Reader has an icon and original description but no observed screenshot.
- 9/2000 E-police and Chanseygolf have no uniquely selected original description.
- Launch evidence: 4/2000 Billeder til Geometra conflicts; Albert Åberg has an
  unresolved warning-continue branch. 9/2000 NeoTrace has conflicting targets and
  a missing launch reference. 13/2000 Terragen & Firmament has conflicting targets.
  These observations remain unresolved; images do not approve launch identity.

## What this demonstrates about scaling

The extraction/import/projection stages processed all 118 entries without manual
per-entry edits or approvals. Four common format/filesystem assumptions required
code fixes, and one disc required an acquisition workaround. This is evidence
that the batch pipeline works across these seven discs, not that arbitrary media
or thousands of entries can already be processed unattended.

Next automation work: a resumable batch runner with per-disc stage status,
source-format detection, coverage comparison against the prior run, and an
exception queue. The ISO mount workaround should become a documented acquisition
option with input-image identity, not a silent skip in file inventory. Semantic
identification remains separate work; the user should review exceptions rather
than approve every imported field.

## Release checks

The collection config binds one exact manifest to each medium, retains old K37
links, and gives the new discs namespaced routes. Image minimums are asserted per
CD. `description_requirements.minimum_count` now also blocks accidental loss of
original source text. Missing text cannot be masked by a normalized rewrite.

Local validation: Ingest 154 found / 136 passed / 18 unavailable-media skips;
Catalog 87 found / 86 passed / 1 unavailable-media skip; Web 126 found / 96 passed
/ 30 unavailable Playwright skips. Skips are not passes. Separate actual browser
checks exercise all five filters, loaded overview images, search, namespaced K37,
and RTF source text. All selected new images/icons were inspected in contact
sheets. HTTP verification checks every entry and public object.

Related implementation: bootdisk-ingest PR14 and PR15; bootdisk-catalog PR40.
The local curator workspace on port 8772 is not part of the public package.
