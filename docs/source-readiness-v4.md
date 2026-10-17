# Accept source readiness v4

Catalog v4 binds Norwegian DTX title variants to preserved source bytes and validates
multiline Tools descriptions. The frontend data validator now accepts that rule,
while retaining v1-v3 for existing releases and rejecting unknown rule names.
All other status, source binding and title equality checks remain in force.

This is a build-contract compatibility change; no public UI or live deployment is
changed. The change is required before attach-source-documents and collection builds
can consume the newer Catalog projection.

Validation: 328 tests, 218 passed and 110 optional/browser tests skipped in the
non-browser run. The complete generated preview is also verified separately by the
HTTP deployment verifier. Existing public baseline entry bytes must remain unchanged.
