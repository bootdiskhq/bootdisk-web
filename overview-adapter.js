/* Prototype read layer for the curator overview.
 *
 * This is NOT part of the agreed `bootdisk-curator-v1` contract. It is the smallest read
 * interface the overview needs, implemented locally against sample data so the screen can
 * be judged before Catalog has one. `docs/curator-overview-prototype.md` writes it up as a
 * proposal to Birk/Codex. Nothing here writes: the object has no mutating method at all,
 * which is what keeps searching and filtering from touching curation data.
 */
const OVERVIEW_CONTRACT = "bootdisk-curator-overview-proposal-1";
const OVERVIEW_CLAIM_FIELDS = ["identity", "version", "content_kind", "distribution_kind", "description"];
/* The columns the table shows beyond name, source entry and status. */
const OVERVIEW_VALUE_FIELDS = ["version", "content_kind", "distribution_kind"];
const OVERVIEW_STATUS_FILTERS = ["all", "pending", "deferred", "reviewed"];
const OVERVIEW_FIELD_FILTERS = ["all", "any_open", "resolved", "needs_review", ...OVERVIEW_CLAIM_FIELDS];
const OVERVIEW_SORTS = ["name", "source"];
const OVERVIEW_PAGE_SIZE = 50;

function overviewOpenFields(claims) {
  return OVERVIEW_CLAIM_FIELDS.filter(field => claims?.[field]?.assessment === "unresolved");
}

function overviewEntryNumber(entryId) {
  const digits = String(entryId ?? "").replace(/^K/i, "");
  return Number.isFinite(Number(digits)) ? Number(digits) : Number.MAX_SAFE_INTEGER;
}

function overviewSameValue(left, right) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

/* One row of the overview, derived from the review state of one entry. `getQueue` reads
 * open fields from the accepted claims when there are any, and this mirrors that exactly so
 * the two views of the same entry cannot disagree. */
function overviewSummary(record) {
  const accepted = record.accepted ?? null;
  const claims = accepted?.claims ?? record.draft?.claims ?? null;
  const openFields = overviewOpenFields(claims);
  const reviewRequired = (record.issues ?? [])
    .filter(issue => issue.code === "classification_review_required" && issue.field)
    .map(issue => issue.field);

  const values = {};
  for (const field of OVERVIEW_VALUE_FIELDS) {
    const acceptedValue = accepted ? (accepted.claims?.[field]?.value ?? null) : null;
    const draftValue = record.draft?.claims?.[field]?.value ?? null;
    values[field] = {
      accepted: acceptedValue,
      draft: draftValue,
      /* A draft that differs is never presented as the catalogue's approved value. */
      differs: accepted ? !overviewSameValue(acceptedValue, draftValue) : Boolean(record.draft),
    };
  }

  const title = record.title ?? record.source?.title ?? "";
  const entry = record.key.entry;
  const label = record.manifest_label ?? record.key.manifest;
  return {
    key: { manifest: record.key.manifest, entry },
    manifest_label: label,
    title,
    queue_state: record.queue_state,
    identification_status: accepted?.identification_status ?? null,
    open_fields: openFields,
    review_required_fields: reviewRequired,
    has_accepted: Boolean(accepted),
    /* Reviewed is a pass over the entry; resolved is an entry with nothing left open. */
    fully_resolved: Boolean(accepted) && openFields.length === 0 && reviewRequired.length === 0,
    values,
    /* Precomputed so a keystroke over several thousand rows stays a substring scan. */
    search: `${title}\n${entry}\n${label}\n${record.key.manifest}`.toLocaleLowerCase("nb-NO"),
    sort_name: title.toLocaleLowerCase("nb-NO"),
    sort_entry: overviewEntryNumber(entry),
  };
}

function overviewSummaryFromEntry(entry, manifestLabel) {
  return overviewSummary({
    key: entry.key,
    manifest_label: manifestLabel,
    title: entry.source?.title,
    queue_state: entry.queue_state,
    accepted: entry.accepted,
    draft: entry.draft,
    issues: entry.issues,
  });
}

/* Replaces a generated row with the review state the detail screen has already stored for
 * that entry. The source issues stay as they were: they describe the source, not the
 * decision. */
function overviewApplyRecord(row, record) {
  return overviewSummary({
    key: row.key,
    manifest_label: row.manifest_label,
    title: row.title,
    queue_state: record.queue_state,
    accepted: record.accepted,
    draft: record.draft,
    issues: row.review_required_fields.map(field => ({ code: "classification_review_required", field, message: "" })),
  });
}

function overviewMatchesStatus(row, status) {
  return status === "all" || row.queue_state === status;
}

function overviewMatchesField(row, field) {
  if (field === "all") return true;
  if (field === "any_open") return row.open_fields.length > 0 || row.review_required_fields.length > 0;
  if (field === "resolved") return row.fully_resolved;
  if (field === "needs_review") return row.review_required_fields.length > 0;
  return row.open_fields.includes(field) || row.review_required_fields.includes(field);
}

function overviewTerms(query) {
  return String(query ?? "").toLocaleLowerCase("nb-NO").split(/\s+/).filter(Boolean);
}

function overviewMatchesQuery(row, terms) {
  return terms.every(term => row.search.includes(term));
}

/* A total order. The collator decides how names read to a Norwegian curator, and the
 * manifest and entry tiebreakers decide everything else, so two rows are never equal and a
 * page boundary can neither drop nor repeat a row. */
function overviewComparator(sort) {
  const collator = new Intl.Collator("nb-NO", { numeric: true, sensitivity: "base" });
  return (left, right) => {
    if (sort === "name") {
      const byName = collator.compare(left.sort_name, right.sort_name);
      if (byName !== 0) return byName;
    }
    if (left.key.manifest !== right.key.manifest) return left.key.manifest < right.key.manifest ? -1 : 1;
    if (left.sort_entry !== right.sort_entry) return left.sort_entry - right.sort_entry;
    if (left.key.entry === right.key.entry) return 0;
    return left.key.entry < right.key.entry ? -1 : 1;
  };
}

function createOverviewAdapter(options) {
  const settle = options.settle ?? (value => Promise.resolve(value));
  const curatorFor = options.curatorFor ?? null;
  const manifestLabels = options.manifestLabels ?? new Map();
  const rows = options.rows.slice();
  const index = new Map(rows.map((row, position) => [`${row.key.manifest}/${row.key.entry}`, position]));

  /* Unknown values fall back rather than failing, and the effective request comes back in
   * the answer, so the caller never has to keep its own copy of the allowed values. */
  function effective(request = {}) {
    return {
      query: request.query ?? "",
      status: OVERVIEW_STATUS_FILTERS.includes(request.status) ? request.status : "all",
      field: OVERVIEW_FIELD_FILTERS.includes(request.field) ? request.field : "all",
      sort: OVERVIEW_SORTS.includes(request.sort) ? request.sort : "name",
      page_size: Math.max(1, request.page_size ?? OVERVIEW_PAGE_SIZE),
    };
  }

  /* Whether one row belongs in a given request. The overview uses it to explain a row that
   * has just fallen outside the active filter. */
  function matches(row, request = {}) {
    const { query, status, field } = effective(request);
    return overviewMatchesStatus(row, status)
      && overviewMatchesField(row, field)
      && overviewMatchesQuery(row, overviewTerms(query));
  }

  function listEntries(request = {}) {
    const { query, status, field, sort, page_size: pageSize } = effective(request);
    const terms = overviewTerms(query);

    const matched = rows.filter(row =>
      overviewMatchesStatus(row, status) && overviewMatchesField(row, field) && overviewMatchesQuery(row, terms));
    matched.sort(overviewComparator(sort));

    const pageCount = Math.max(1, Math.ceil(matched.length / pageSize));
    const page = Math.min(Math.max(1, request.page ?? 1), pageCount);
    const start = (page - 1) * pageSize;
    return settle({
      schema: OVERVIEW_CONTRACT,
      query,
      status,
      field,
      sort,
      total: rows.length,
      matched: matched.length,
      page,
      page_size: pageSize,
      page_count: pageCount,
      items: matched.slice(start, start + pageSize),
    });
  }

  /* One entry, read through the ordinary v1 adapter for its manifest, so a row that has
   * just been decided is refreshed from what the adapter actually answers rather than from
   * a guess made here. */
  function refreshEntry(key) {
    if (!curatorFor) return Promise.resolve(null);
    /* An unknown manifest must reject like any other read failure, not throw out of here. */
    return Promise.resolve().then(() => curatorFor(key.manifest)).then(curator => curator.getEntry({ key })).then(entry => {
      const summary = overviewSummaryFromEntry(entry, manifestLabels.get(key.manifest) ?? key.manifest);
      const position = index.get(`${key.manifest}/${key.entry}`);
      if (position !== undefined) rows[position] = summary;
      return summary;
    });
  }

  return {
    contract: OVERVIEW_CONTRACT,
    /* Always true here. The screen says so, and no reader may take these rows for an
     * integrated catalogue read. */
    prototype: true,
    total: rows.length,
    pageSize: OVERVIEW_PAGE_SIZE,
    listEntries,
    refreshEntry,
    matches,
    comparator: overviewComparator,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    createOverviewAdapter,
    overviewSummary,
    overviewSummaryFromEntry,
    overviewApplyRecord,
    overviewComparator,
    overviewMatchesField,
    overviewEntryNumber,
    OVERVIEW_CONTRACT,
    OVERVIEW_CLAIM_FIELDS,
    OVERVIEW_VALUE_FIELDS,
    OVERVIEW_STATUS_FILTERS,
    OVERVIEW_FIELD_FILTERS,
    OVERVIEW_SORTS,
    OVERVIEW_PAGE_SIZE,
  };
}
