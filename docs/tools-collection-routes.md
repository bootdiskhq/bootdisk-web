# Supplemental entries on a legacy medium

Only historical K-number entries retain bare public links when `legacy_links` is
true. Supplemental entries such as I1 use the normal medium namespace, for example
`kcd-15-2001--I1`. Source IDs and manifest bindings remain unchanged. Both collection
construction and validation enforce the same rule; only one medium may retain
legacy links.

`build-preview.py --previous-manifest OLD` forwards the explicitly selected
append-only predecessor to Catalog. Catalog validates continuity and preserves the
original decision binding in the generated document. This is a static preview,
not a migration of the local curator or approval of new source entries.
