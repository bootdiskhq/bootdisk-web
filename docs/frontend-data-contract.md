# Frontend-datakontrakt 1.0

Identifisert programvare kan ha `descriptions`, en liste med kuraterte
`description_id`, `language` og ikke-tom `text`. Feltet er valgfritt for eldre og
uidentifiserte poster. Nettvisningen foretrekker `nb-NO` og beholder sin generiske
tekst når ingen kuratert beskrivelse finnes.

Bootdisk Web leser bare genererte presentasjonsdata. Catalog eier programvareidentitet og evidens, mens Publish eier publiserte filer. Kontrakten nedenfor fryses for 1.0-serien slik at presentasjonslaget kan slettes og bygges på nytt uten håndredigering.

## `data/index.json`

Rotobjektet skal inneholde:

- `publication`: ikke-tom tekst fra byggeparameteren.
- `medium`: ikke-tom tekst fra byggeparameteren.
- `entries`: kildeposter i stigende numerisk K-rekkefølge.

Hver indekspost skal minst ha en unik `entry` på formen `K<nummer>` og `curation_status` lik `identified` eller `pending`. `editorial_title`, `software_name`, `version` og `icon` kan være `null`; nettleseren skal aldri finne på manglende identitet.

## `data/k<nummer>.json`

Det skal finnes nøyaktig ett detaljdokument per indekspost. Dokumentets `entry`, `publication` og `medium` skal samsvare med indeksen. `software` og `assets` er alltid lister, også når de er tomme.

En ressurs skal:

- tilhøre samme `entry` som detaljdokumentet;
- ha typen `icon` eller `screenshot`;
- peke til en relativ `store/`-sti uten `..`;
- oppgi en SHA-256 for originalen og hvert derivat.

Utvidelser kan legge til felter. Eksisterende felt endres eller fjernes først i en ny hovedversjon av kontrakten.

## Validering

Kjør kontraktporten direkte med:

```sh
python scripts/frontend_contract.py build/data --expected-entries 39
```

`build-release.py` kjører samme port automatisk før den kopierer data eller filer til en deploymappe. Dermed kan en ugyldig eller halvferdig projeksjon ikke pakkes som release.

## 1.1 optional interpretation metadata

Software projections may provide `content_kind`, `distribution_kind`, `package_id`
and `status`. Index summaries may additionally provide `identification_status`,
`content_kind` and `distribution_kind`. An interpreted identity is displayed as
provisional and has a separate browsing filter. This does not change the existing
`curation_status` enum. Missing optional fields retain the 1.0 fallback behavior.
The version value `unknown` is displayed as unknown in details and omitted from
page titles and overview version labels.

## Collection extension — 1.2.0-rc1

A single-medium projection still follows Frontend-datakontrakt 1.0. Director source
IDs such as `Spil1` and `K1D1` are now supported, preserving case and manifest order.
Pure K-number projections keep their historical numeric ordering.

`build-collection.py config.json --output NEW_DIRECTORY` combines individually
validated projections. Configuration uses `media: [{id, data, legacy_links?}]`;
`data` paths are relative to the configuration. The builder refuses an existing
output, duplicate media/manifests, cross-source observations and route collisions.

A collection index has schema `bootdisk-web-collection-1`, a `media` array with
stable slug, publication, medium label and exact manifest digest, and entries in
configured medium/source order. The root publication/medium describe the collection.
Each summary and detail includes `medium_id`, `source_manifest`, `source_entry`,
`source_order`, `publication` and `medium`. Public `entry` becomes
`<medium-slug>--<source-entry>`, while Catalog identity and `source_context.key`
retain the original manifest/entry pair. Filenames are lowercase public IDs.

Only one explicitly configured historical medium may use `legacy_links: true`.
It retains `K37` URLs and requires K-number IDs. The slug is an editorial route
name, not a media identity; keep it stable between releases. Different revisions of
one source manifest must replace that medium's projection deliberately.

`source_context` is supplied by Catalog. Original description, menu groups and
issues are observations with manifest/entry/JSON-pointer provenance. Original
text is preferred over a curated paraphrase and rendered as plain text with line
breaks. A missing selected description is stated explicitly. Pending entries
remain pending; source titles never become software identities. Neither versions
from generic installers nor source menu groups become semantic facts here.

Director discs now publish selected CD images and original icons (see image
coverage below and [the five-disc trial](five-disc-trial.md)). Empty assets remain
valid for an individual entry and do not imply that no image exists on the disc.
The Director intake preserves launch references, not complete executable packages.
No program downloads or hosted curator are included in the public release.

## Image coverage — 1.2.0-rc2

The index's `icon` is an overview preview: prefer an icon asset, otherwise use a
screenshot asset without changing its kind. A collection medium may declare
`image_requirements.all_entries` (required kinds on every entry) and
`image_requirements.minimum_counts` (minimum covered entries per kind). Release
builds enforce these requirements and reject image-empty media unless a nonempty
`images_unavailable_reason` is explicitly configured. Exceptions never waive
positive requirements. Tests and HTTP checks do not substitute for this gate.

## Original-description coverage

Collection media may specify `description_requirements: {"minimum_count": 33}`.
The release checks nonblank `source_context.description.value` for that medium
and fails before replacing output when coverage falls below the requirement.
The artifact report includes `description_coverage` alongside image coverage.

## Collection registry — public front page

The front page and collection pages combine the collection index with a small
Web-owned registry, `collections.json`. The registry is presentation configuration,
not a Catalog identity, and no field is added to the generated data.

```json
{
  "schema": "bootdisk-web-collections-1",
  "collections": [{
    "id": "komputer-for-alle",
    "title": "Komputer for alle",
    "publication_values": ["KOMPUTER FOR ALLE"],
    "summary": "Front page text",
    "lede": "Collection page introduction",
    "history_title": "Optional heading",
    "history": ["Paragraph", "Paragraph"],
    "sources": [{"label": "Source", "href": "index.html?entry=K26"}]
  }]
}
```

- `id` is a stable lowercase slug and the `collection` URL parameter.
- `publication_values` binds the collection to exact `media[].publication` values in
  the index (for a 1.0 single-medium index: the root `publication`). This is the only
  grouping rule: nothing is inferred from file names, medium slugs or the collection
  index root, which describes the whole archive.
- `sources[].href` is an entry link, an archive link or an `https://` URL.
- Collections are presented in registry order; one without media is not shown.

`scripts/collection_registry.py` (run by `build-release.py`) refuses to package when
a medium's publication is bound to no collection or to more than one, when an id is
repeated or unsafe, when a source link is not allowed, or when a cited entry is not
in the index. The error names the medium and the value to configure. The browser
applies the same rules in `collection-core.js` and shows an explicit error state
instead of sample data or zero counts.

Counts are derived from the index alone: media are counted by `media[].id`, and
entries by `medium_id`. An entry count is source entries, not unique programs.
Media sort newest first by the trailing `<issue>/<year>` of the medium label, compared
numerically; the issue number is not a month. Labels without that pattern follow in
natural order. Adding a disc or a second publication is a data and registry change;
the pages do not change. The 1.0 single-medium index remains supported as one medium
whose content is the whole archive.
