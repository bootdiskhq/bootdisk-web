# 1.2.0-rc1 — two-disc public archive

This release publishes both K-CD 15/2001 and K-CD 1/2000. It keeps historical
`index.html?entry=K37` links, adds CD filtering with shareable URLs, and shows
original CD wording. Missing versions say “Ikke oppgitt”. Source-only records and
menu conflicts are explained in the public page without implying approval.

The release candidate contains 60 source entries (39 + 21), 57 original descriptions
(39 + 18), and 136 existing published image objects. All 21 new Director entries
remain pending identification. Three have no unambiguously selected description;
five have conflicting/missing launch references. No images have yet been selected
for the Director disc, and no complete executable packages or download links are
claimed. These are documented source limitations, not failed web builds.

## Reproducible preparation

1. Export accepted graph records from the local ReviewWorkspace into a new Catalog
   directory. Do not project drafts or publish the workspace itself.
2. Run `bootdisk_catalog.presentation` separately for each Catalog/manifest pair.
3. Run `scripts/build-frontend-data.py` with each projection and its corresponding
   Publish manifest. Set `--medium` explicitly. A manifest containing `assets: []`
   is valid when no image assets have been selected for that disc.
4. Build the collection with `scripts/build-collection.py CONFIG --output NEW_DATA`.
   Give K-CD 15/2001 the stable slug `kcd-15-2001` and `legacy_links: true`; give
   K-CD 1/2000 the slug `kcd-1-2000`. Do not reuse slugs for a different disc.
5. Run `scripts/build-release-artifact.py PUBLISH_ROOT --frontend-data NEW_DATA
   --output RELEASES --expected-entries 60`. The Publish root must contain all
   referenced content-addressed image objects. No Director assets are required yet.
6. Serve the resulting release directory on a separate loopback port and run
   `scripts/verify-deployment.py URL --expected-entries 60`. Check old/new detail
   links, CD filter, search, reload, missing-description and source-conflict states.

Only the closed public allowlist and referenced public data/assets enter the ZIP.
Curator pages, synthetic overview data, drafts, review history, source media and
services stay local. The ZIP is deterministic and its report records the input
projection digest, exact source manifest identities, pending count and ZIP digest.

## Upload and rollback

Back up the current public directory. Upload the **contents** of the extracted
release folder to the web root, including all 61 JSON documents in `data`, static
files, sitemap, robots and `store`. Keep the data and static files from the same
release; preferably switch a fully uploaded directory atomically. Do not upload
the surrounding local-results folder or either source-media directory.

After switching, run the deployment verifier against `https://bootdisk.no/` with
60 expected entries. Check the K37 link and one K-CD 1/2000 link in a browser.
If verification fails, restore the previous directory in full (39 entries). The
old release ZIP remains a rollback artifact. Clean up stale public curator files
if an earlier manual upload included any; this release does not ship them.

## Remaining development

Publishing source observations is independent of semantic approval. The next
curation work still needs tested field proposals from file inspection, explicit
machine-actor history/idempotency/undo, and an actual multi-medium service behind
the overview prototype. Do not mark those roadmap items complete with this release.
