# Automation queue v1 — read-only integration contract

Status: development contract for Catalog first-pass-1 and Claude's Web queue.
Schema: `bootdisk-automation-queue-1`. This is not the curator write protocol.

The document contains `schema`, `rules_version`, `mode: read_only`, `input` (manifest
SHA-256 and source candidate SHA-256), `entries`, and `summary`. No timestamps,
mount paths or random IDs enter this reproducible result. A new manifest or rule
version produces a new snapshot. Source IDs are scoped by manifest, never title.

Each entry contains:

- `key: {manifest, entry}`: exact source identity. Preserve both strings.
- `title`: source title, displayed as text.
- `stage`: `proposals`, `inspecting`, `needs_review`, or `protected`.
- `requires_human`: boolean. Only `needs_review` may have true.
- `fields`: ordered array with `field`, `status`, `proposed`, `rule`, `reason`,
  `evidence`. Fields are identity, version, content_kind, distribution_kind,
  description. Status is candidate, retain_unknown, inspect, conflict or preserve.
- `evidence`: array of `{label, value, source_ref}`. `value` is readable source
  text or an array of source strings; source_ref contains manifest, entry, pointer.
  Show the label and original readable value first, provenance on demand.
- `tasks`: array with `code`, `field`, `reason`, `evidence`. These are machine
  inspection tasks, not user questions. Do not turn them into required checkboxes.

Candidate means a suggestion, NOT an accepted value or completed inspection.
`proposed: null` never means delete or approve unknown. `retain_unknown` records
that no value is established; separate tasks may still request machine inspection.
Description candidates preserve the selected original text, including whitespace.
No inferred language is attached. Source conflict is not automatically a human
exception: first-pass-1 puts it in `inspecting`, requires_human false. The inspector
must attempt resolution before a future producer can emit `needs_review`.

`summary` is computed from entries: entries, field_status_counts (all five statuses,
including zeros), stage_counts (all four stages), machine_tasks, human_exceptions,
automatic_decisions (zero), human_decisions (zero). Web recomputes filter-result
counts but must not invent accepted counts from candidate counts.

## Delivered producer scope

First-pass-1 accepts only a pristine Director candidate intake and its exact
manifest. It refuses altered candidate data, decisions, unknown schemas, and
symlinks in the intake snapshot. It cannot open a ReviewWorkspace or write a
Catalog claim. It emits only proposals/inspecting, not needs_review/protected.
The latter two are reserved for future audited producers and appear only in
clearly labelled synthetic Web fixtures. Do not claim that they are integrated.

This first delivery does not inspect binaries, parse versions from names, equate
Freeware with full edition, or treat shared setup bytes as program identity.
Actual human workload cannot be measured until machine inspection is implemented.

## Web adapter boundary

Implement a small explicit read-only adapter with `loadQueue(): Promise<document>`.
Prototype source: an explicitly selected synthetic fixture in local development.
Do not invent an HTTP backend endpoint. Future local service wiring is Catalog's
responsibility. Validate schema, stage/status enums, keys, readable reasons and
arrays before rendering. Missing or malformed data must produce error, never a
silent synthetic fallback. Preserve unknown evidence values as safe text.

There are no save/approve/undo methods in this contract. Do not redirect a Director
candidate into the old curator: v1 curator requires existing identifications and
its keys are not the same. An entry opens a read-only evidence panel instead.
Show keyboard-accessible expand/collapse and an explicit close/return action.
Public release must not contain this queue, its adapter, or synthetic fixtures.
