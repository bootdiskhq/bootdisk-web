/* Readable Norwegian labels shared by the curator's detail screen and its overview.
 *
 * The block below is duplicated verbatim in curate.js, and a test keeps the two identical.
 * It cannot be a shared file that curate.html loads: Catalog's local service serves the
 * curator from a closed allowlist (`STATIC` in `bootdisk_catalog/service.py`), so any file
 * curate.html loads that is not already on that list answers 404 and stops real local
 * curation before it starts. Only this page loads this file; curate.js carries its own copy.
 */
/* --- delt kuratorvokabular: identisk blokk i curate.js og curator-labels.js --- */
const CONTENT_KIND_LABELS = {
  application: "Program",
  game: "Spill",
  course: "Kurs",
  image_collection: "Bildesamling",
  font_collection: "Fontsamling",
  reference: "Oppslagsverk",
};
const DISTRIBUTION_LABELS = {
  full: "Full versjon",
  demo: "Demo",
  trial: "Prøveversjon",
  update: "Oppdatering",
  unknown: "Ukjent",
};
const QUEUE_STATE_LABELS = { pending: "Venter", deferred: "Utsatt", reviewed: "Gjennomgått" };
/* Status is readable without colour: the mark carries it on its own. */
const QUEUE_STATE_MARKS = { pending: "●", deferred: "‖", reviewed: "✓" };
const IDENTIFICATION_LABELS = { curated: "Kuratert identitet", interpreted: "Foreløpig identitet" };
const ASSESSMENT_LABELS = { accepted: "Belagt", unresolved: "Uavklart" };

/* The stored value of the three fields both screens show as a column and as a claim.
 * «unknown» is a stored value, not a label, and is spelled out in Norwegian here. */
function curatorFieldText(field, value) {
  if (field === "version") return value === "unknown" ? "Ikke oppgitt" : String(value ?? "");
  if (field === "content_kind") return CONTENT_KIND_LABELS[value] ?? String(value ?? "");
  if (field === "distribution_kind") return DISTRIBUTION_LABELS[value] ?? String(value ?? "");
  return String(value ?? "");
}
/* --- slutt delt kuratorvokabular --- */

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    CONTENT_KIND_LABELS,
    DISTRIBUTION_LABELS,
    QUEUE_STATE_LABELS,
    QUEUE_STATE_MARKS,
    IDENTIFICATION_LABELS,
    ASSESSMENT_LABELS,
    curatorFieldText,
  };
}
