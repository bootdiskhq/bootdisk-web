/* The automatic first-pass queue, kept free of the DOM so validation, counting, filtering,
 * sorting, pagination and the address bar can be tested directly. automation.js binds this
 * to the page; automation-adapter.js reads the document.
 *
 * Contract: docs/automation-queue-v1.md (schema bootdisk-automation-queue-1). This file
 * decides nothing about a program. It checks that a document has the agreed shape, recounts
 * what the document says, and answers "which entries match". Every semantic judgement, from
 * a candidate to a conflict, is the producer's and is shown as the producer wrote it.
 */
const AUTOMATION_SCHEMA = "bootdisk-automation-queue-1";
/* The order is the order a person should look at them in: what needs them first, then what
 * the machine still has to do, then what is merely proposed, then what is protected. */
const AUTOMATION_STAGES = ["needs_review", "inspecting", "proposals", "protected"];
const AUTOMATION_STATUSES = ["candidate", "retain_unknown", "inspect", "conflict", "preserve"];
const AUTOMATION_FIELDS = ["identity", "version", "content_kind", "distribution_kind", "description"];
/* A field whose value is not established. A candidate has a proposal and a preserved field
 * has human work behind it, so neither is "unknown". */
const AUTOMATION_UNKNOWN_STATUSES = ["retain_unknown", "inspect", "conflict"];
const AUTOMATION_SORTS = ["stage", "title", "source"];
const AUTOMATION_PAGE_SIZE = 25;
const AUTOMATION_QUERY_KEYS = ["kilde", "q", "stage", "felt", "feltstatus", "sort", "side", "manifest", "post"];

/* Kinds of failure the page tells apart. None of them is ever shown as a count of zero. */
class AutomationQueueError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "AutomationQueueError";
    this.kind = kind;
  }
}

function automationFail(kind, message) {
  throw new AutomationQueueError(kind, message);
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireString(value, where, { nonEmpty = true } = {}) {
  if (typeof value !== "string" || (nonEmpty && value.trim() === "")) {
    automationFail("invalid_schema", `${where} må være ${nonEmpty ? "en tekst som ikke er tom" : "tekst"}.`);
  }
  return value;
}

function requireArray(value, where) {
  if (!Array.isArray(value)) automationFail("invalid_schema", `${where} må være en liste.`);
  return value;
}

function requireObject(value, where) {
  if (!isPlainObject(value)) automationFail("invalid_schema", `${where} må være et objekt.`);
  return value;
}

function requireEnum(value, allowed, where) {
  if (typeof value !== "string") automationFail("invalid_schema", `${where} må være tekst.`);
  if (!allowed.includes(value)) {
    automationFail("unknown_value", `${where} har den ukjente verdien «${value}». Kjente verdier: ${allowed.join(", ")}.`);
  }
  return value;
}

/* An evidence value is readable source text or a list of source strings. Anything else is
 * kept, as text, and marked so the page can say it is an unexpected shape. */
function validateEvidence(list, where) {
  return requireArray(list, where).map((item, index) => {
    const at = `${where}[${index}]`;
    requireObject(item, at);
    requireString(item.label, `${at}.label`);
    if (!("value" in item)) automationFail("invalid_schema", `${at}.value mangler.`);
    const ref = requireObject(item.source_ref, `${at}.source_ref`);
    requireString(ref.manifest, `${at}.source_ref.manifest`);
    requireString(ref.entry, `${at}.source_ref.entry`);
    requireString(ref.pointer, `${at}.source_ref.pointer`, { nonEmpty: false });
    const value = item.value;
    let shape = "other";
    if (typeof value === "string") shape = "text";
    else if (Array.isArray(value) && value.every(part => typeof part === "string")) shape = "list";
    return {
      label: item.label,
      value,
      shape,
      source_ref: { manifest: ref.manifest, entry: ref.entry, pointer: ref.pointer },
    };
  });
}

function validateField(field, where) {
  requireObject(field, where);
  const name = requireEnum(field.field, AUTOMATION_FIELDS, `${where}.field`);
  const status = requireEnum(field.status, AUTOMATION_STATUSES, `${where}.status`);
  if (!("proposed" in field)) automationFail("invalid_schema", `${where}.proposed mangler (null betyr ikke fastslått).`);
  return {
    field: name,
    status,
    proposed: field.proposed,
    rule: requireString(field.rule, `${where}.rule`),
    reason: requireString(field.reason, `${where}.reason`),
    evidence: validateEvidence(field.evidence, `${where}.evidence`),
  };
}

function validateTask(task, where, fieldNames) {
  requireObject(task, where);
  const field = requireEnum(task.field, AUTOMATION_FIELDS, `${where}.field`);
  if (!fieldNames.includes(field)) {
    automationFail("invalid_schema", `${where}.field viser til «${field}», som posten ikke har.`);
  }
  return {
    code: requireString(task.code, `${where}.code`),
    field,
    reason: requireString(task.reason, `${where}.reason`),
    evidence: validateEvidence(task.evidence, `${where}.evidence`),
  };
}

function validateEntry(entry, where, manifest) {
  requireObject(entry, where);
  const key = requireObject(entry.key, `${where}.key`);
  requireString(key.manifest, `${where}.key.manifest`);
  requireString(key.entry, `${where}.key.entry`);
  /* One snapshot is one manifest: a K-ID only means something together with its manifest. */
  if (key.manifest !== manifest) {
    automationFail("invalid_schema", `${where}.key.manifest er ikke manifestet i input.manifest.`);
  }
  const stage = requireEnum(entry.stage, AUTOMATION_STAGES, `${where}.stage`);
  if (typeof entry.requires_human !== "boolean") {
    automationFail("invalid_schema", `${where}.requires_human må være true eller false.`);
  }
  /* The contract ties the two together; a disagreement is refused rather than guessed at,
   * because either reading would put the entry in the wrong place for a person. */
  if (entry.requires_human !== (stage === "needs_review")) {
    automationFail("invalid_schema",
      `${where}: requires_human er ${entry.requires_human}, men stage er «${stage}». Bare needs_review kan kreve et menneske, og den må gjøre det.`);
  }
  const fields = requireArray(entry.fields, `${where}.fields`).map((field, index) => validateField(field, `${where}.fields[${index}]`));
  const names = fields.map(field => field.field);
  if (new Set(names).size !== names.length) automationFail("invalid_schema", `${where}.fields har samme felt to ganger.`);
  const tasks = requireArray(entry.tasks, `${where}.tasks`).map((task, index) => validateTask(task, `${where}.tasks[${index}]`, names));
  return {
    key: { manifest: key.manifest, entry: key.entry },
    title: requireString(entry.title, `${where}.title`),
    stage,
    requires_human: entry.requires_human,
    fields,
    tasks,
  };
}

/* The summary exactly as the contract defines it, computed from the entries. */
function automationSummary(entries) {
  const field_status_counts = Object.fromEntries(AUTOMATION_STATUSES.map(status => [status, 0]));
  const stage_counts = Object.fromEntries(AUTOMATION_STAGES.map(stage => [stage, 0]));
  let machine_tasks = 0;
  let human_exceptions = 0;
  for (const entry of entries) {
    stage_counts[entry.stage] += 1;
    for (const field of entry.fields) field_status_counts[field.status] += 1;
    machine_tasks += entry.tasks.length;
    if (entry.requires_human) human_exceptions += 1;
  }
  return {
    entries: entries.length,
    field_status_counts,
    stage_counts,
    machine_tasks,
    human_exceptions,
    automatic_decisions: 0,
    human_decisions: 0,
  };
}

function sameCounts(expected, actual, where) {
  requireObject(actual, where);
  for (const [name, value] of Object.entries(expected)) {
    if (actual[name] !== value) {
      automationFail("invalid_schema", `${where}.${name} er ${JSON.stringify(actual[name])}, men postene gir ${value}.`);
    }
  }
}

/* Checks one document against the contract and returns a normalised copy. The input is never
 * changed. A document that does not add up is refused as a whole, so a page never shows a
 * partial queue as if it were the full one. */
function automationValidate(document) {
  const doc = requireObject(document, "Dokumentet");
  if (doc.schema !== AUTOMATION_SCHEMA) {
    automationFail("invalid_schema", `Ukjent schema ${JSON.stringify(doc.schema)}; forventet «${AUTOMATION_SCHEMA}».`);
  }
  if (doc.mode !== "read_only") automationFail("invalid_schema", `mode må være «read_only», ikke ${JSON.stringify(doc.mode)}.`);
  const rulesVersion = requireString(doc.rules_version, "rules_version");
  const input = requireObject(doc.input, "input");
  const manifest = requireString(input.manifest, "input.manifest");
  const candidates = requireString(input.candidates_sha256, "input.candidates_sha256");
  const entries = requireArray(doc.entries, "entries").map((entry, index) => validateEntry(entry, `entries[${index}]`, manifest));
  const seen = new Set();
  for (const entry of entries) {
    if (seen.has(entry.key.entry)) automationFail("invalid_schema", `Kildeposten ${entry.key.entry} står to ganger i samme manifest.`);
    seen.add(entry.key.entry);
  }
  const expected = automationSummary(entries);
  const summary = requireObject(doc.summary, "summary");
  sameCounts(expected.field_status_counts, summary.field_status_counts, "summary.field_status_counts");
  sameCounts(expected.stage_counts, summary.stage_counts, "summary.stage_counts");
  const { field_status_counts, stage_counts, ...totals } = expected;
  sameCounts(totals, summary, "summary");
  return {
    schema: doc.schema,
    rules_version: rulesVersion,
    mode: doc.mode,
    input: { manifest, candidates_sha256: candidates },
    entries,
    summary: expected,
  };
}

/* Several snapshots, one per manifest, read as one queue. The same K-ID on two CDs is two
 * entries; the same manifest twice would be two answers for one CD and is refused. */
function automationCombine(documents) {
  const snapshots = [];
  const entries = [];
  const manifests = new Map();
  documents.forEach((document, index) => {
    if (manifests.has(document.input.manifest)) {
      automationFail("invalid_schema", `Manifestet ${document.input.manifest} er lastet to ganger.`);
    }
    const ordinal = index + 1;
    manifests.set(document.input.manifest, ordinal);
    snapshots.push({ ordinal, rules_version: document.rules_version, input: document.input, entries: document.entries.length });
    for (const entry of document.entries) {
      entries.push({
        ...entry,
        id: automationKeyId(entry.key),
        manifest_ordinal: ordinal,
        rules_version: document.rules_version,
        candidates_sha256: document.input.candidates_sha256,
        search_text: `${entry.title}\n${entry.key.entry}\n${entry.key.manifest}`.toLocaleLowerCase("nb-NO"),
      });
    }
  });
  return { snapshots, entries, summary: automationSummary(entries), byId: new Map(entries.map(entry => [entry.id, entry])) };
}

function automationKeyId(key) {
  return `${key.manifest}\u0000${key.entry}`;
}

function automationFind(model, key) {
  if (!key) return null;
  return model.byId.get(automationKeyId(key)) ?? null;
}

/* Fields whose value is not established, per field, in the given entries. */
function automationUnknownByField(entries) {
  const counts = Object.fromEntries(AUTOMATION_FIELDS.map(field => [field, 0]));
  for (const entry of entries) {
    for (const field of entry.fields) {
      if (AUTOMATION_UNKNOWN_STATUSES.includes(field.status)) counts[field.field] += 1;
    }
  }
  return counts;
}

const entryCollator = typeof Intl !== "undefined" ? new Intl.Collator("nb-NO", { numeric: true, sensitivity: "base" }) : null;
function compareText(left, right) {
  return entryCollator ? entryCollator.compare(left, right) : (left < right ? -1 : left > right ? 1 : 0);
}

/* Every sort ends on the full identity, so two runs over the same data always give the same
 * order and a page number always means the same rows. */
function automationComparator(sort) {
  const byStage = (a, b) => AUTOMATION_STAGES.indexOf(a.stage) - AUTOMATION_STAGES.indexOf(b.stage);
  const byTitle = (a, b) => compareText(a.title, b.title);
  const bySource = (a, b) => (a.manifest_ordinal - b.manifest_ordinal) || compareText(a.key.entry, b.key.entry);
  const exact = (a, b) => (a.key.manifest < b.key.manifest ? -1 : a.key.manifest > b.key.manifest ? 1 : 0)
    || (a.key.entry < b.key.entry ? -1 : a.key.entry > b.key.entry ? 1 : 0);
  const chains = {
    stage: [byStage, byTitle, bySource, exact],
    title: [byTitle, bySource, exact],
    source: [bySource, byTitle, exact],
  };
  const chain = chains[sort] ?? chains.stage;
  return (a, b) => {
    for (const compare of chain) {
      const result = compare(a, b);
      if (result) return result;
    }
    return 0;
  };
}

/* Only allowed values survive; anything else falls back to "all" and the page shows the
 * effective filter, so a hand-edited address cannot produce a filter nobody can see. */
function automationNormalizeFilters(filters) {
  const pick = (value, allowed, fallback) => (allowed.includes(value) ? value : fallback);
  const page = Number.parseInt(filters.page, 10);
  return {
    query: typeof filters.query === "string" ? filters.query : "",
    stage: pick(filters.stage, AUTOMATION_STAGES, "all"),
    field: pick(filters.field, AUTOMATION_FIELDS, "all"),
    status: pick(filters.status, AUTOMATION_STATUSES, "all"),
    sort: pick(filters.sort, AUTOMATION_SORTS, "stage"),
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

function automationMatches(entry, filters) {
  if (filters.stage !== "all" && entry.stage !== filters.stage) return false;
  if (filters.status !== "all" || filters.field !== "all") {
    const ok = entry.fields.some(field => (filters.field === "all" || field.field === filters.field)
      && (filters.status === "all" || field.status === filters.status));
    if (!ok) return false;
  }
  const words = filters.query.toLocaleLowerCase("nb-NO").split(/\s+/).filter(Boolean);
  return words.every(word => entry.search_text.includes(word));
}

/* One page of the matching entries. Filtering always runs over the whole queue; only the
 * rows of the current page are handed to the page to build. */
function automationQuery(model, rawFilters, pageSize = AUTOMATION_PAGE_SIZE) {
  const filters = automationNormalizeFilters(rawFilters);
  const matching = model.entries.filter(entry => automationMatches(entry, filters));
  matching.sort(automationComparator(filters.sort));
  const pageCount = Math.max(1, Math.ceil(matching.length / pageSize));
  const page = Math.min(filters.page, pageCount);
  const start = (page - 1) * pageSize;
  return {
    filters: { ...filters, page },
    items: matching.slice(start, start + pageSize),
    matched: matching.length,
    total: model.entries.length,
    page,
    pageCount,
    stageCounts: Object.fromEntries(AUTOMATION_STAGES.map(stage => [stage, matching.filter(entry => entry.stage === stage).length])),
    humanMatched: matching.filter(entry => entry.requires_human).length,
    tasksMatched: matching.reduce((sum, entry) => sum + entry.tasks.length, 0),
  };
}

/* The page on which an entry sits under the given filters, or null when it does not match. */
function automationPageOf(model, rawFilters, key, pageSize = AUTOMATION_PAGE_SIZE) {
  const filters = automationNormalizeFilters(rawFilters);
  const matching = model.entries.filter(entry => automationMatches(entry, filters));
  matching.sort(automationComparator(filters.sort));
  const index = matching.findIndex(entry => entry.key.manifest === key.manifest && entry.key.entry === key.entry);
  return index < 0 ? null : Math.floor(index / pageSize) + 1;
}

function automationStateFromQuery(params) {
  const read = name => params.get(name) ?? "";
  const manifest = read("manifest");
  const entry = read("post");
  return {
    source: read("kilde"),
    ...automationNormalizeFilters({
      query: read("q"),
      stage: read("stage"),
      field: read("felt"),
      status: read("feltstatus"),
      sort: read("sort"),
      page: read("side"),
    }),
    open: manifest && entry ? { manifest, entry } : null,
  };
}

function automationStateToQuery(state) {
  const params = new URLSearchParams();
  if (state.source) params.set("kilde", state.source);
  if (state.query) params.set("q", state.query);
  if (state.stage && state.stage !== "all") params.set("stage", state.stage);
  if (state.field && state.field !== "all") params.set("felt", state.field);
  if (state.status && state.status !== "all") params.set("feltstatus", state.status);
  if (state.sort && state.sort !== "stage") params.set("sort", state.sort);
  if (state.page && state.page !== 1) params.set("side", String(state.page));
  if (state.open) {
    params.set("manifest", state.open.manifest);
    params.set("post", state.open.entry);
  }
  return params;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    AUTOMATION_SCHEMA,
    AUTOMATION_STAGES,
    AUTOMATION_STATUSES,
    AUTOMATION_FIELDS,
    AUTOMATION_UNKNOWN_STATUSES,
    AUTOMATION_SORTS,
    AUTOMATION_PAGE_SIZE,
    AUTOMATION_QUERY_KEYS,
    AutomationQueueError,
    automationValidate,
    automationSummary,
    automationCombine,
    automationKeyId,
    automationFind,
    automationUnknownByField,
    automationComparator,
    automationNormalizeFilters,
    automationMatches,
    automationQuery,
    automationPageOf,
    automationStateFromQuery,
    automationStateToQuery,
  };
}
