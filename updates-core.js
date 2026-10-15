/* "Sist lagt til og oppdatert": what was published on Bootdisk, and when. The feed
 * (data/public-updates.json, contract bootdisk-public-updates-v2) supplies dates and
 * change codes; names, CD, icon and link come from the current archive index. An event
 * for an entry that is no longer in the index is kept in the history but never shown,
 * so the page cannot link to a missing entry. Rendering helpers take a document so the
 * rules can be tested outside a browser. Every name here starts with "update". */
const UPDATES_SCHEMA = "bootdisk-public-updates-v2";
const UPDATES_FEED_URL = "data/public-updates.json";
const UPDATES_PAGE_SIZE = 25;
const UPDATES_LANDING_COUNT = 8;
const UPDATE_ENTRY_ID = /^(?:[a-z0-9]+(?:-[a-z0-9]+)*--)?[A-Za-z][A-Za-z0-9]{0,63}$/;
const UPDATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const UPDATE_TYPES = ["added", "updated"];
const UPDATE_CODES = [
  "identified", "identification_confirmed", "interpreted", "identification_withdrawn",
  "name_added", "name_changed", "name_removed",
  "version_added", "version_changed", "version_removed",
  "content_kind_added", "content_kind_changed", "content_kind_removed",
  "distribution_kind_added", "distribution_kind_changed", "distribution_kind_removed",
  "menu_title_changed",
  "description_added", "description_changed", "description_removed",
  "icon_added", "icon_changed", "icon_removed",
  "screenshot_added", "screenshot_changed", "screenshot_removed",
  "source_document_added", "source_document_changed", "source_document_removed",
  "source_issues_added", "source_issues_changed", "source_issues_removed",
];
const UPDATE_PHRASES = {
  identification_confirmed: "Identifiseringen er bekreftet",
  interpreted: "Foreløpig identifisert",
  identification_withdrawn: "Identifiseringen er trukket tilbake",
  name_added: "Programnavn lagt til",
  name_changed: "Programnavn endret",
  name_removed: "Programnavnet er fjernet",
  version_added: "Versjon avklart",
  version_changed: "Versjon endret",
  version_removed: "Versjonen er ikke lenger oppgitt",
  content_kind_added: "Innholdstype avklart",
  content_kind_changed: "Innholdstype endret",
  content_kind_removed: "Innholdstypen er ikke lenger oppgitt",
  distribution_kind_added: "Utgave avklart",
  distribution_kind_changed: "Utgave endret",
  distribution_kind_removed: "Utgaven er ikke lenger oppgitt",
  menu_title_changed: "Menytittel endret",
  description_added: "Omtale lagt til",
  description_changed: "Omtale endret",
  description_removed: "Omtalen er fjernet",
  icon_added: "Ikon lagt til",
  icon_changed: "Ikon byttet",
  icon_removed: "Ikon fjernet",
  screenshot_added: "Skjermbilde lagt til",
  screenshot_changed: "Skjermbilde byttet",
  screenshot_removed: "Skjermbilde fjernet",
  source_document_added: "Vedlagt originaltekst lagt til",
  source_document_changed: "Vedlagt originaltekst endret",
  source_document_removed: "Vedlagt originaltekst fjernet",
  source_issues_added: "Kildeavvik merket",
  source_issues_changed: "Merknaden om kildeavvik er endret",
  source_issues_removed: "Kildeavvik ikke lenger merket",
};
// Same labels as the detail page (app.js).
const UPDATE_CONTENT_KINDS = { application: "program", game: "spill", course: "kurs / veiledning", image_collection: "bildesamling", font_collection: "skriftpakke", reference: "oppslagsverk" };
const UPDATE_DISTRIBUTION_KINDS = { full: "fullversjon", demo: "demo", trial: "prøveversjon", update: "oppdatering" };
const UPDATE_DATE_FORMAT = new Intl.DateTimeFormat("nb-NO", { timeZone: "Europe/Oslo", day: "numeric", month: "long", year: "numeric" });

function updatesProblem(feed) {
  if (!feed || typeof feed !== "object" || Array.isArray(feed)) return "Endringsoversikten er ikke et objekt.";
  if (feed.schema !== UPDATES_SCHEMA) return "Endringsoversikten har ukjent skjema.";
  if (!Array.isArray(feed.releases) || !Array.isArray(feed.events)) return "Endringsoversikten mangler utgaver eller hendelser.";
  const releases = new Map();
  for (const release of feed.releases) {
    if (!release || typeof release.release_id !== "string" || !UPDATE_TIME.test(release.published_at ?? "")) return "En utgave i endringsoversikten er ugyldig.";
    releases.set(release.release_id, release.published_at);
  }
  const seen = new Set();
  for (const event of feed.events) {
    if (!event || typeof event !== "object") return "En hendelse er ikke et objekt.";
    if (!UPDATE_ENTRY_ID.test(event.entry ?? "")) return "En hendelse har ugyldig kildepost.";
    if (!UPDATE_TYPES.includes(event.type)) return "En hendelse har ukjent type.";
    if (releases.get(event.release_id) !== event.published_at) return "En hendelse har feil utgave eller tidspunkt.";
    if (!Array.isArray(event.changes) || !event.changes.every(code => UPDATE_CODES.includes(code))) return "En hendelse har ukjent endringskode.";
    if ((event.type === "updated") !== (event.changes.length > 0)) return "En hendelse har feil endringskoder for typen.";
    const key = `${event.release_id}\u0000${event.entry}`;
    if (seen.has(key)) return "En kildepost har to hendelser i samme utgave.";
    seen.add(key);
  }
  return null;
}

/* Newest publication first; on equal time, the permanent entry id in code-point order.
 * Never locale-dependent, so the order is the same in every build and browser. */
function compareUpdateRows(left, right) {
  if (left.event.published_at !== right.event.published_at) return left.event.published_at < right.event.published_at ? 1 : -1;
  return left.event.entry < right.event.entry ? -1 : left.event.entry > right.event.entry ? 1 : 0;
}

/* One row per source entry: its latest event. Two entries for the same program on two
 * CDs stay two rows; nothing is merged by name or file hash. */
function latestUpdates(feed, index) {
  const summaries = new Map(index.entries.map(summary => [summary.entry, summary]));
  const latest = new Map();
  for (const event of feed.events) {
    const summary = summaries.get(event.entry);
    if (!summary) continue;
    if (event.medium_id && summary.medium_id && event.medium_id !== summary.medium_id) continue;
    if (event.source_entry && summary.source_entry && event.source_entry !== summary.source_entry) continue;
    const current = latest.get(event.entry);
    if (!current || current.event.published_at < event.published_at) latest.set(event.entry, { event, summary });
  }
  return [...latest.values()].sort(compareUpdateRows);
}

function updateKnown(value) {
  return typeof value === "string" && value.trim() !== "" && value !== "unknown" ? value : null;
}

/* The human name: never an entry id, hash or route key. */
function updateName(summary) {
  return updateKnown(summary.software_name) ?? updateKnown(summary.editorial_title) ?? "Kildepost uten navn i CD-menyen";
}

function updateVersion(summary) {
  return updateKnown(summary.software_name) ? updateKnown(summary.version) : null;
}

function updateValue(code, summary) {
  if (code === "version_added" || code === "version_changed") return updateVersion(summary);
  if (code === "content_kind_added" || code === "content_kind_changed") return UPDATE_CONTENT_KINDS[summary.content_kind] ?? null;
  if (code === "distribution_kind_added" || code === "distribution_kind_changed") return UPDATE_DISTRIBUTION_KINDS[summary.distribution_kind] ?? null;
  return null;
}

/* A short, concrete explanation from the controlled codes. "Avklart" is only used when
 * something became known; a field that became unknown is said to be no longer given. */
function updateExplanation(event, summary) {
  if (event.type === "added") return "Ny kildepost i arkivet.";
  const codes = new Set(event.changes);
  const phrases = [];
  if (codes.has("identified")) {
    if (codes.has("version_added")) phrases.push("Programnavn og versjon avklart");
    else if (updateVersion(summary)) phrases.push("Program identifisert");
    else phrases.push("Program identifisert, versjonen er fortsatt ukjent");
    codes.delete("identified");
    codes.delete("name_added");
    codes.delete("version_added");
  }
  for (const code of UPDATE_CODES) {
    if (!codes.has(code)) continue;
    const value = updateValue(code, summary);
    phrases.push(value ? `${UPDATE_PHRASES[code]}: ${value}` : UPDATE_PHRASES[code]);
  }
  return phrases.map(phrase => `${phrase}.`).join(" ");
}

function updateBadge(event) {
  return event.type === "added" ? "Ny kildepost" : "Oppdatert";
}

function formatUpdateDate(iso) {
  return UPDATE_DATE_FORMAT.format(new Date(iso));
}

function updateNormalized(value) {
  return String(value ?? "").toLocaleLowerCase("no");
}

/* Search and type filter apply to the whole dataset, not to the rows already shown. */
function filterUpdates(rows, type, query) {
  const needle = updateNormalized(String(query ?? "").trim());
  return rows.filter(row => {
    if (type !== "all" && row.event.type !== type) return false;
    if (!needle) return true;
    const summary = row.summary;
    return [summary.software_name, summary.editorial_title, summary.medium, updateVersion(summary)].map(updateNormalized).join(" ").includes(needle);
  });
}

function updateParameters(search) {
  const parameters = new URLSearchParams(search);
  const type = UPDATE_TYPES.includes(parameters.get("type")) ? parameters.get("type") : "all";
  return { type, query: parameters.get("q") ?? "" };
}

function updateSearch(type, query) {
  const next = new URLSearchParams();
  if (type !== "all") next.set("type", type);
  if (query.trim()) next.set("q", query.trim());
  const text = next.toString();
  return text ? `?${text}` : "";
}

/* A missing feed (HTTP 404) is an archive without published history, not an error. */
async function loadUpdates(fetcher = fetch) {
  const response = await fetcher(UPDATES_FEED_URL, { cache: "no-cache" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Kunne ikke hente ${UPDATES_FEED_URL}: HTTP ${response.status}`);
  let feed;
  try {
    feed = await response.json();
  } catch (error) {
    throw new Error(`${UPDATES_FEED_URL} er ikke gyldig JSON`);
  }
  const problem = updatesProblem(feed);
  if (problem) throw new Error(problem);
  return feed;
}

async function loadUpdateIndex(fetcher = fetch) {
  const response = await fetcher("data/index.json", { cache: "no-cache" });
  if (!response.ok) throw new Error(`Kunne ikke hente data/index.json: HTTP ${response.status}`);
  const index = await response.json();
  if (!index || !Array.isArray(index.entries) || !index.entries.every(entry => entry && typeof entry.entry === "string")) throw new Error("Indeksen er ugyldig.");
  return index;
}

function updateImage(summary) {
  const icon = summary.icon;
  const image = icon?.derivatives?.find(item => item.kind === "thumbnail") ?? icon?.original;
  return typeof image?.public_path === "string" && /^store\//.test(image.public_path) && !image.public_path.split("/").includes("..") ? image.public_path : null;
}

/* One list item. Source values are set as text, never parsed as HTML. */
function updateItem(row, doc = document) {
  const { event, summary } = row;
  const name = updateName(summary);
  const item = doc.createElement("li");
  item.className = "update-item";
  const link = doc.createElement("a");
  link.className = "update-link";
  link.href = `index.html?entry=${encodeURIComponent(event.entry)}`;

  const icon = doc.createElement("span");
  icon.className = "update-icon";
  const image = updateImage(summary);
  if (image) {
    const img = doc.createElement("img");
    img.src = image;
    img.alt = "";
    img.width = 32;
    img.height = 32;
    img.loading = "lazy";
    icon.append(img);
  } else {
    // A quiet text stand-in when the entry has no image.
    icon.classList.add("is-text");
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = Array.from(name.trim())[0]?.toLocaleUpperCase("no") ?? "·";
  }

  const copy = doc.createElement("span");
  copy.className = "update-copy";
  const title = doc.createElement("span");
  title.className = "update-title";
  const strong = doc.createElement("strong");
  strong.textContent = name;
  title.append(strong);
  const version = updateVersion(summary);
  if (version) {
    const versionText = doc.createElement("span");
    versionText.className = "update-version";
    versionText.textContent = `versjon ${version}`;
    title.append(" ", versionText);
  }

  const meta = doc.createElement("span");
  meta.className = "update-meta";
  const badge = doc.createElement("span");
  badge.className = "update-badge";
  badge.dataset.type = event.type;
  badge.textContent = updateBadge(event);
  const time = doc.createElement("time");
  time.dateTime = event.published_at;
  time.textContent = formatUpdateDate(event.published_at);
  meta.append(badge);
  if (summary.medium) {
    const medium = doc.createElement("span");
    medium.className = "update-medium";
    medium.textContent = summary.medium;
    meta.append(medium);
  }
  meta.append(time);

  const explanation = doc.createElement("span");
  explanation.className = "update-explanation";
  explanation.textContent = updateExplanation(event, summary);
  copy.append(title, meta, explanation);
  link.append(icon, copy);
  item.append(link);
  return item;
}
