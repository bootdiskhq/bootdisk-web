/* Archive browsing consumes only the disposable index projection. Detailed Catalog
 * evidence and Publish metadata remain on the entry document, not duplicated here. */
function imageFor(asset) {
  return asset?.derivatives?.find(item => item.kind === "thumbnail") ?? asset?.original;
}

function normalized(value) {
  return String(value ?? "").toLocaleLowerCase("no");
}

function archiveStatusParameter(value) {
  return ["identified", "interpreted", "pending", "source_documented"].includes(value) ? value : "all";
}

/* One status rule for filter, list and detail page (app.js statusLabel): a documented
 * source name on a pending entry is "Oppgitt på CD-en", a provisional identity is
 * "Foreløpig identifisering", otherwise the curation status. */
function archiveStatus(entry) {
  if (entry.curation_status === "pending" && entry.source_catalog_status === "documented") return "source_documented";
  if (entry.identification_status === "interpreted") return "interpreted";
  return entry.curation_status;
}

// The mark repeats the status in shape, so status is never told by colour alone.
const ARCHIVE_STATUS = {
  identified: ["✔", "Identifisert"],
  interpreted: ["◐", "Foreløpig identifisering"],
  source_documented: ["▣", "Oppgitt på CD-en"],
  pending: ["○", "Venter på identifisering"],
};
const ARCHIVE_CONTENT_KINDS = { application: "Program", game: "Spill", course: "Kurs / veiledning", image_collection: "Bildesamling", font_collection: "Skriftpakke", reference: "Oppslagsverk", article: "Artikkel" };
const ARCHIVE_DISTRIBUTION_KINDS = { full: "fullversjon", demo: "demo", trial: "prøveversjon", update: "oppdatering" };
// Program, Spill and Kurs / veiledning are always offered, so «Spill» is an explicit choice
// even on an index where no entry is a game yet; other types appear when the data has them.
const ARCHIVE_CENTRAL_KINDS = ["application", "game", "course"];
const ARCHIVE_UNKNOWN = "unknown";
const ARCHIVE_SORTS = ["source", "name", "type", "year-desc", "year-asc"];

/* The CD's own menu group may group an entry for browsing when Catalog has no content
 * kind. Only these exact source values count (docs/archive-sort-filter.md); «Demoer»,
 * «Barn», «Bonus», «Aktuelt» and every other group say nothing about the type on their
 * own. Mirrored by scripts/archive_index.py, which reports the distribution. */
const ARCHIVE_MENU_GROUP_KINDS = {
  "Spill": "game", "Spil": "game", "games": "game",
  "Videokurs": "course",
  "KProgram": "application", "programs": "application", "Software": "application",
  "Artikler": "article",
};

/* One archive type per entry, used alike by filter, sort and row:
 * 1. a known Catalog content_kind (basis "catalog");
 * 2. otherwise the mapped menu groups, if they all agree (basis "menu");
 * 3. otherwise unknown: no group, only unmapped groups, or groups that disagree.
 * Titles, file names and descriptions are never read here. An older index without
 * `menu_groups` simply falls through to unknown. */
function archiveKind(entry) {
  const known = entry.content_kind;
  if (typeof known === "string" && Object.hasOwn(ARCHIVE_CONTENT_KINDS, known) && known !== "article") return { kind: known, basis: "catalog" };
  const groups = Array.isArray(entry.menu_groups) ? entry.menu_groups : [];
  const kinds = new Set();
  for (const group of groups) {
    const kind = typeof group === "string" && Object.hasOwn(ARCHIVE_MENU_GROUP_KINDS, group.trim()) ? ARCHIVE_MENU_GROUP_KINDS[group.trim()] : null;
    if (kind) kinds.add(kind);
  }
  if (kinds.size === 1) return { kind: [...kinds][0], basis: "menu" };
  return { kind: ARCHIVE_UNKNOWN, basis: kinds.size > 1 ? "conflict" : "none" };
}

function archiveKindLabel(kind) {
  return ARCHIVE_CONTENT_KINDS[kind] ?? "Ikke oppgitt";
}

/* The year and issue of the CD itself, from its label («K-CD 10/2001»), never the
 * program version or the date it was published here. */
function archiveIssue(entry) {
  return typeof parseIssue === "function" ? parseIssue(entry.medium) : null;
}

function archiveYearParameter(value) {
  if (value === ARCHIVE_UNKNOWN) return value;
  return /^[0-9]{4}$/.test(String(value ?? "")) ? String(value) : null;
}

function archiveTypeParameter(value) {
  if (value === ARCHIVE_UNKNOWN) return value;
  return typeof value === "string" && Object.hasOwn(ARCHIVE_CONTENT_KINDS, value) ? value : null;
}

function archiveSortParameter(value) {
  return ARCHIVE_SORTS.includes(value) ? value : "source";
}

/* Filter choices come from the data: every type and CD year that occurs, plus
 * «Ikke oppgitt» when some entry has none. */
function archiveTypeOptions(entries) {
  const present = new Set(entries.map(entry => archiveKind(entry).kind));
  const others = Object.keys(ARCHIVE_CONTENT_KINDS).filter(kind => !ARCHIVE_CENTRAL_KINDS.includes(kind) && present.has(kind))
    .sort((left, right) => archiveCollator.compare(archiveKindLabel(left), archiveKindLabel(right)));
  const options = [...ARCHIVE_CENTRAL_KINDS, ...others].map(kind => ({ value: kind, label: archiveKindLabel(kind) }));
  if (present.has(ARCHIVE_UNKNOWN)) options.push({ value: ARCHIVE_UNKNOWN, label: "Ikke oppgitt" });
  return options;
}

function archiveYearOptions(entries) {
  const years = new Set();
  let unknown = false;
  for (const entry of entries) {
    const year = archiveIssue(entry)?.year;
    if (year) years.add(year); else unknown = true;
  }
  const options = [...years].sort((left, right) => right - left).map(year => ({ value: String(year), label: String(year) }));
  if (unknown) options.push({ value: ARCHIVE_UNKNOWN, label: "Ikke oppgitt" });
  return options;
}

function filterEntries(entries, query, status, medium = "all", type = "all", year = "all") {
  const needle = normalized(query.trim());
  return entries.filter(entry => {
    const effectiveStatus = archiveStatus(entry);
    const matchesStatus = status === "all" || effectiveStatus === status;
    const haystack = [entry.entry, entry.editorial_title, entry.software_name, entry.version, entry.medium, entry.source_entry].map(normalized).join(" ");
    if (!(matchesStatus && (medium === "all" || entry.medium_id === medium) && haystack.includes(needle))) return false;
    if (type !== "all" && archiveKind(entry).kind !== type) return false;
    if (year !== "all") {
      const entryYear = archiveIssue(entry)?.year;
      if (year === ARCHIVE_UNKNOWN ? Boolean(entryYear) : String(entryYear) !== year) return false;
    }
    return true;
  });
}

const archiveCollator = new Intl.Collator("nb", { sensitivity: "base" });

function archiveName(entry) {
  return entry.software_name ?? entry.editorial_title ?? entry.entry;
}

function sourcePosition(entry) {
  return entry.source_order ?? Number(String(entry.entry).replace(/^.*?(\d+)$/, "$1"));
}

// Last resort for a total, stable order: source position, then the unique entry id.
function sourceTieBreak(left, right) {
  return (sourcePosition(left) - sourcePosition(right)) || (left.entry < right.entry ? -1 : left.entry > right.entry ? 1 : 0);
}

/* Sorting only orders; it never adds or removes an entry (filterEntries decides that).
 * Unknown type or year goes last in both directions. */
function sortEntries(entries, sort) {
  const comparators = {
    name: (left, right) => archiveCollator.compare(archiveName(left), archiveName(right)),
    type: (left, right) => {
      const a = archiveKind(left).kind, b = archiveKind(right).kind;
      if ((a === ARCHIVE_UNKNOWN) !== (b === ARCHIVE_UNKNOWN)) return a === ARCHIVE_UNKNOWN ? 1 : -1;
      return archiveCollator.compare(archiveKindLabel(a), archiveKindLabel(b)) || archiveCollator.compare(archiveName(left), archiveName(right));
    },
    "year-desc": (left, right) => compareIssues(archiveIssue(left), archiveIssue(right), -1) || archiveCollator.compare(left.medium ?? "", right.medium ?? ""),
    "year-asc": (left, right) => compareIssues(archiveIssue(left), archiveIssue(right), 1) || archiveCollator.compare(left.medium ?? "", right.medium ?? ""),
  };
  const compare = comparators[sort] ?? (() => 0);
  return [...entries].sort((left, right) => compare(left, right) || sourceTieBreak(left, right));
}

// Year, then issue number as a number (2 before 10), in the same direction.
function compareIssues(a, b, direction) {
  if (!a || !b) return a ? -1 : b ? 1 : 0;
  return direction * (a.year - b.year || a.issue - b.issue);
}

function contentLabel(entry) {
  const { kind, basis } = archiveKind(entry);
  const label = kind === ARCHIVE_UNKNOWN ? null : basis === "menu" ? `${archiveKindLabel(kind)} (CD-meny)` : archiveKindLabel(kind);
  const edition = ARCHIVE_DISTRIBUTION_KINDS[entry.distribution_kind];
  if (label && edition) return `${label}, ${edition}`;
  if (label) return label;
  if (edition) return edition.charAt(0).toLocaleUpperCase("no") + edition.slice(1);
  return null;
}

// «(CD-meny)» stays on one line so a narrow row never breaks it at the hyphen.
function kindContent(label) {
  const marker = " (CD-meny)";
  if (!label || !label.includes(marker)) return label;
  const [kind, rest] = label.split(marker);
  const basis = document.createElement("span");
  basis.className = "archive-kind-basis";
  basis.textContent = "(CD-meny)";
  const fragment = document.createDocumentFragment();
  fragment.append(`${kind} `, basis, rest);
  return fragment;
}

function cell(className, label, content) {
  const element = document.createElement("td");
  element.className = className;
  if (label) element.dataset.label = label;
  if (content === null || content === undefined) {
    const unknown = document.createElement("span");
    unknown.className = "archive-unknown";
    unknown.textContent = "Ikke oppgitt";
    element.append(unknown);
  } else {
    element.append(content);
  }
  return element;
}

/* One compact row per source entry: a human title (never the source id), CD and year,
 * content type and status. All values are set as text; source titles are untrusted. */
function card(entry) {
  const row = document.createElement("tr");
  const link = document.createElement("a");
  link.className = "archive-card";
  link.href = `index.html?entry=${encodeURIComponent(entry.entry)}`;
  const image = imageFor(entry.icon);
  const name = entry.software_name ?? entry.editorial_title ?? entry.entry;
  const secondary = entry.software_name && entry.editorial_title !== entry.software_name ? entry.editorial_title : null;
  const icon = document.createElement("span");
  icon.className = "archive-card-icon";
  if (image?.public_path) {
    const img = document.createElement("img");
    img.src = image.public_path;
    img.alt = "";
    img.width = 32;
    img.height = 32;
    img.loading = "lazy";
    icon.append(img);
  } else {
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "?";
  }

  const copy = document.createElement("span");
  copy.className = "archive-card-copy";
  link.textContent = name;
  copy.append(link);
  if (entry.version && entry.version !== "unknown") {
    const version = document.createElement("span");
    version.className = "archive-version";
    version.textContent = `versjon ${entry.version}`;
    copy.append(version);
  }
  if (secondary) {
    const sourceTitle = document.createElement("span");
    sourceTitle.className = "archive-source-title";
    sourceTitle.textContent = `På CD-en: ${secondary}`;
    copy.append(sourceTitle);
  }
  const title = document.createElement("span");
  title.className = "archive-title-cell";
  title.append(icon, copy);

  const year = archiveIssue(entry)?.year;
  const effectiveStatus = archiveStatus(entry);
  const [mark, label] = ARCHIVE_STATUS[effectiveStatus] ?? ["?", "Ukjent"];
  const status = document.createElement("span");
  status.className = "archive-status";
  status.dataset.status = effectiveStatus;
  const symbol = document.createElement("span");
  symbol.className = "archive-status-mark";
  symbol.setAttribute("aria-hidden", "true");
  symbol.textContent = mark;
  status.append(symbol, label);

  const typeCell = cell("archive-cell-kind", "Innhold", kindContent(contentLabel(entry)));
  if (Array.isArray(entry.menu_groups) && entry.menu_groups.includes("Skole")) {
    const source = document.createElement("small");
    source.className = "archive-source-title";
    source.textContent = "På CD-en: Skole";
    typeCell.append(source);
  }
  row.append(
    cell("archive-cell-title", null, title),
    cell("archive-cell-medium", "CD", entry.medium ?? null),
    cell("archive-cell-year", "År", year ? String(year) : null),
    typeCell,
    cell("archive-cell-status", null, status));
  return row;
}

function archiveTable(rows) {
  const table = document.createElement("table");
  table.className = "archive-table";
  const caption = document.createElement("caption");
  caption.textContent = "Kildeposter med tittel, CD, år, innhold og status";
  const columns = document.createElement("colgroup");
  for (const name of ["title", "medium", "year", "kind", "status"]) {
    const column = document.createElement("col");
    column.className = `archive-col-${name}`;
    columns.append(column);
  }
  const head = document.createElement("thead");
  const headings = document.createElement("tr");
  for (const text of ["Tittel", "CD", "År", "Innhold", "Status"]) {
    const heading = document.createElement("th");
    heading.scope = "col";
    heading.textContent = text;
    headings.append(heading);
  }
  head.append(headings);
  const body = document.createElement("tbody");
  body.append(...rows);
  table.append(caption, columns, head, body);
  return table;
}

/* A medium filter shows one CD as a place of its own: its name, its collection and a
 * way back to both the collection and the whole archive. */
function archiveContext(data, registry, mediumId) {
  const medium = (data.media ?? []).find(item => item.id === mediumId);
  if (!medium) return { title: "Programvarearkivet", eyebrow: `${data.publication} · ${data.medium}`, trail: [{ label: "Bootdisk", href: "./" }, { label: "Alle kildeposter" }], links: [] };
  const collection = registry ? collectionForPublication(registry, medium.publication) : null;
  const trail = [{ label: "Bootdisk", href: "./" }];
  if (collection) trail.push({ label: collection.title, href: collectionHref(collection) });
  else trail.push({ label: "Alle kildeposter", href: "archive.html" });
  trail.push({ label: medium.medium });
  const links = collection ? [{ label: `← Tilbake til ${collection.title}`, href: collectionHref(collection) }] : [];
  links.push({ label: "Alle kildeposter", href: "archive.html" });
  return { title: medium.medium, eyebrow: collection ? collection.title.toLocaleUpperCase("no") : medium.publication, trail, links, medium, collection };
}

function renderArchiveContext(context) {
  document.querySelector("#archive-title").textContent = context.title;
  document.querySelector("#archive-source").textContent = context.eyebrow;
  document.querySelector("#archive-lede").textContent = context.medium
    ? "Innholdet på CD-en, slik det er bevart. Originalomtalene vises uendret, og uavklart programidentitet er merket."
    : "Bla i kildepostene slik de er bevart. Bekreftede opplysninger og originale CD-omtaler vises side om side.";
  document.querySelector("#archive-breadcrumbs").replaceChildren(...context.trail.map(item => {
    const element = document.createElement("li");
    if (item.href) {
      const link = document.createElement("a");
      link.href = item.href;
      link.textContent = item.label;
      element.append(link);
    } else {
      element.textContent = item.label;
      element.setAttribute("aria-current", "page");
    }
    return element;
  }));
  const links = document.querySelector("#medium-links");
  links.replaceChildren(...context.links.map(item => Object.assign(document.createElement("a"), { href: item.href, textContent: item.label })));
  links.hidden = context.links.length === 0;
  document.title = context.medium ? `${context.title}${context.collection ? ` — ${context.collection.title}` : ""} — Bootdisk` : "Arkiv — Bootdisk";
}

function fillOptions(select, options) {
  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    select.append(option);
  }
}

async function render() {
  const registryRequest = typeof loadRegistry === "function" ? loadRegistry().catch(error => { console.warn(error); return null; }) : Promise.resolve(null);
  const response = await fetch("data/index.json", { cache: "no-cache" });
  if (!response.ok) throw new Error(`Cannot load archive index: ${response.status}`);
  const data = await response.json();
  const registry = await registryRequest;
  const grid = document.querySelector("#archive-grid");
  const count = document.querySelector("#archive-count");
  const empty = document.querySelector("#archive-empty");
  const search = document.querySelector("#archive-search");
  const status = document.querySelector("#archive-status");
  const medium = document.querySelector("#archive-medium");
  const type = document.querySelector("#archive-type");
  const year = document.querySelector("#archive-year");
  const sort = document.querySelector("#archive-sort");
  const reset = document.querySelector("#archive-reset");
  const emptyReset = document.querySelector("#archive-empty-reset");
  fillOptions(medium, (data.media ?? []).map(item => ({ value: item.id, label: item.medium })));
  const typeOptions = archiveTypeOptions(data.entries);
  fillOptions(year, archiveYearOptions(data.entries));

  /* Every parameter is read on its own: one that is unknown falls back to «all» and
   * says so, without clearing the others. */
  const parameters = new URLSearchParams(window.location.search);
  const problems = [];
  const requestedMedium = parameters.get("medium");
  medium.value = (data.media ?? []).some(item => item.id === requestedMedium) ? requestedMedium : "all";
  if (requestedMedium !== null && medium.value === "all") problems.push("Fant ikke CD-en i lenken. Viser alle CD-er i stedet.");
  const requestedType = parameters.get("type");
  const typeValue = archiveTypeParameter(requestedType);
  // A valid type the data does not have yet still selects; the result is then empty.
  if (typeValue && !typeOptions.some(item => item.value === typeValue)) typeOptions.push({ value: typeValue, label: archiveKindLabel(typeValue) });
  fillOptions(type, typeOptions);
  type.value = typeValue ?? "all";
  if (requestedType !== null && !typeValue) problems.push("Ukjent innholdstype i lenken. Viser alle typer.");
  const requestedYear = parameters.get("year");
  const yearValue = archiveYearParameter(requestedYear);
  year.value = yearValue && [...year.options].some(option => option.value === yearValue) ? yearValue : "all";
  if (requestedYear !== null && year.value === "all") problems.push("Fant ikke CD-året i lenken. Viser alle år.");
  search.value = parameters.get("q") ?? "";
  status.value = archiveStatusParameter(parameters.get("status"));
  sort.value = archiveSortParameter(parameters.get("sort"));
  const notice = document.querySelector("#archive-notice");
  if (problems.length) {
    notice.textContent = problems.join(" ");
    notice.hidden = false;
  }

  function update() {
    const entries = sortEntries(filterEntries(data.entries, search.value, status.value, medium.value, type.value, year.value), sort.value);
    grid.replaceChildren(...(entries.length ? [archiveTable(entries.map(card))] : []));
    empty.hidden = entries.length !== 0;
    count.textContent = `${entries.length} av ${data.entries.length} poster`;
    const next = new URLSearchParams();
    if (search.value.trim()) next.set("q", search.value.trim());
    if (medium.value !== "all") next.set("medium", medium.value);
    if (status.value !== "all") next.set("status", status.value);
    if (type.value !== "all") next.set("type", type.value);
    if (year.value !== "all") next.set("year", year.value);
    if (sort.value !== "source") next.set("sort", sort.value);
    renderArchiveContext(archiveContext(data, registry, medium.value));
    const query = next.toString();
    window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  }
  for (const control of [status, medium, type, year, sort]) control.addEventListener("change", update);
  search.addEventListener("input", update);
  function clear() {
    search.value = "";
    status.value = "all";
    medium.value = "all";
    type.value = "all";
    year.value = "all";
    sort.value = "source";
    notice.hidden = true;
    update();
    search.focus();
  }
  reset.addEventListener("click", clear);
  emptyReset?.addEventListener("click", clear);
  update();
}

render().catch(error => {
  console.error(error);
  const notice = document.querySelector("#archive-notice");
  notice.textContent = "Kunne ikke laste arkivoversikten. Det betyr ikke at arkivet er tomt. Last siden på nytt.";
  notice.hidden = false;
  document.querySelector("#archive-grid").textContent = "Kunne ikke laste arkivoversikten. Bygg frontend-data først.";
});
