# 1.2.0-rc2 — restore the new disc's original images

Supersedes rc1, which was prematurely labelled publication-ready despite missing
all Director assets. HTTP/contract tests showed that shipped files worked but did
not establish source-image coverage. This release corrects both the missing images
and that acceptance gap.

K-CD 1/2000 now has 21 original detail images and 18 original menu icons. Three
remaining cards use their CD image as a thumbnail; the asset keeps kind screenshot
and is never represented as an original icon. Original source wording, pending
identity statuses, five launch-reference conflicts and three missing selected
text descriptions remain. Images are a separate source observation, not evidence
that the launch target or software identity is approved.

Ingest extracts resource bytes/provenance; Catalog imports occurrences; Publish
verifies preserved container slices and renders indexed rasters to PNG; Web joins
only assets with a matching occurrence hash and source entry. No image generation,
web image replacement, executable launch or manual copy into frontend data occurs.

The collection configuration for `kcd-1-2000` must contain:

```json
"image_requirements": {
  "all_entries": ["screenshot"],
  "minimum_counts": {"icon": 18}
}
```

The release builder now refuses a collection medium with no images unless the
configuration records an explicit nonempty `images_unavailable_reason`. Such an
exception never overrides the required kinds/counts above. This is source coverage,
separate from tests of HTTP availability and asset hashes.

Build the supplemental image bundle using Ingest, import it to a new Catalog, and
publish it with `bootdisk_publish.embedded`. Rebuild only the new disc's frontend
projection, then combine with the previous approved old-disc projection. Assemble
the two content-addressed stores, rejecting unequal bytes under the same key.
Run the collection and release-artifact builders with 60 expected entries. Upload
and rollback instructions from rc1 still apply, but use the rc2 ZIP.

Acceptance: verify all 21 overview images load, original Word icon/detail image,
one game thumbnail fallback, existing K37 image, image-coverage rejection tests,
and all 60 documents/206 referenced store objects over HTTP. Compare the full
21-image and 18-icon contact sheets against titles/source frames. Excel Viewer
uses a Word-style icon in the source menu; retain it instead of inventing a repair.
