/* Collections are editorial presentation over the generated archive index. The
 * registry (collections.json) names each collection and binds it to exact
 * `publication` values found on media; it is not a Catalog identity. Everything
 * here is DOM-free so the same rules can be tested outside a browser. */
const COLLECTION_REGISTRY_SCHEMA = "bootdisk-web-collections-1";
const COLLECTION_INDEX_SCHEMA = "bootdisk-web-collection-1";
const COLLECTION_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
// Source links may point at a preserved entry, the archive, or an external https page.
const COLLECTION_SOURCE_HREF = /^(?:index\.html\?entry=(?:[a-z0-9]+(?:-[a-z0-9]+)*--)?[A-Za-z][A-Za-z0-9]{0,63}|archive\.html(?:\?medium=[a-z0-9]+(?:-[a-z0-9]+)*)?|https:\/\/[^\s"'<>\\]+)$/;

function nonBlank(value) {
  return typeof value === "string" && value.trim() !== "";
}

function registryProblem(registry) {
  if (!registry || typeof registry !== "object" || Array.isArray(registry)) return "Registeret er ikke et objekt.";
  if (registry.schema !== COLLECTION_REGISTRY_SCHEMA) return "Registeret har ukjent skjema.";
  if (!Array.isArray(registry.collections) || registry.collections.length === 0) return "Registeret har ingen samlinger.";
  const ids = new Set();
  const claimed = new Set();
  for (const collection of registry.collections) {
    if (!collection || typeof collection !== "object") return "En samling er ikke et objekt.";
    if (typeof collection.id !== "string" || !COLLECTION_SLUG.test(collection.id)) return "En samling har ugyldig nøkkel.";
    if (ids.has(collection.id)) return `Samlingsnøkkelen ${collection.id} er brukt flere ganger.`;
    ids.add(collection.id);
    for (const field of ["title", "summary", "lede"]) {
      if (!nonBlank(collection[field])) return `Samlingen ${collection.id} mangler ${field}.`;
    }
    if (!Array.isArray(collection.publication_values) || collection.publication_values.length === 0) return `Samlingen ${collection.id} er ikke koblet til noen publikasjonsverdi.`;
    for (const value of collection.publication_values) {
      if (!nonBlank(value)) return `Samlingen ${collection.id} har en tom publikasjonsverdi.`;
      if (claimed.has(value)) return `Publikasjonsverdien «${value}» er koblet til flere samlinger.`;
      claimed.add(value);
    }
    if (!Array.isArray(collection.history) || !collection.history.every(nonBlank)) return `Samlingen ${collection.id} har ugyldig historietekst.`;
    if ("history_title" in collection && !nonBlank(collection.history_title)) return `Samlingen ${collection.id} har tom historieoverskrift.`;
    if (!Array.isArray(collection.sources)) return `Samlingen ${collection.id} mangler kildeliste.`;
    for (const source of collection.sources) {
      if (!source || !nonBlank(source.label) || typeof source.href !== "string" || !COLLECTION_SOURCE_HREF.test(source.href)) return `Samlingen ${collection.id} har en ugyldig kildelenke.`;
    }
  }
  return null;
}

function indexProblem(index) {
  if (!index || typeof index !== "object" || Array.isArray(index)) return "Indeksen er ikke et objekt.";
  if (!Array.isArray(index.entries)) return "Indeksen mangler kildeposter.";
  if (!index.entries.every(entry => entry && typeof entry.entry === "string")) return "Indeksen har en ugyldig kildepost.";
  if (index.schema === COLLECTION_INDEX_SCHEMA) {
    if (!Array.isArray(index.media)) return "Indeksen mangler medier.";
    const ids = new Set();
    for (const medium of index.media) {
      if (!medium || typeof medium.id !== "string" || !COLLECTION_SLUG.test(medium.id)) return "Indeksen har et medium med ugyldig ID.";
      if (ids.has(medium.id)) return `Mediet ${medium.id} finnes flere ganger.`;
      if (!nonBlank(medium.publication) || !nonBlank(medium.medium)) return `Mediet ${medium.id} mangler publikasjon eller navn.`;
      ids.add(medium.id);
    }
    if (!index.entries.every(entry => ids.has(entry.medium_id))) return "En kildepost peker til et ukjent medium.";
    return null;
  }
  // Frontend-datakontrakt 1.0: one medium, described by the index root.
  if (!nonBlank(index.publication) || !nonBlank(index.medium)) return "Indeksen mangler publikasjon eller medium.";
  return null;
}

/* The media a collection can be built from. A single-medium projection has no media
 * array; its root is that medium, and the whole archive is its content. */
function indexMedia(index) {
  if (index.schema === COLLECTION_INDEX_SCHEMA) {
    return index.media.map(medium => ({
      id: medium.id,
      publication: medium.publication,
      label: medium.medium,
      count: index.entries.filter(entry => entry.medium_id === medium.id).length,
      href: `archive.html?medium=${encodeURIComponent(medium.id)}`,
    }));
  }
  return [{ id: null, publication: index.publication, label: index.medium, count: index.entries.length, href: "archive.html" }];
}

/* A label ending in "13/2000" is issue 13 of 2000. The issue number is not a month. */
function parseIssue(label) {
  const match = /(\d{1,3})\s*\/\s*(\d{4})\s*$/.exec(String(label ?? ""));
  return match ? { issue: Number(match[1]), year: Number(match[2]) } : null;
}

function compareMedia(left, right) {
  const a = parseIssue(left.label);
  const b = parseIssue(right.label);
  if (a && b) return b.year - a.year || b.issue - a.issue || left.label.localeCompare(right.label, "no", { numeric: true });
  if (a || b) return a ? -1 : 1;
  return left.label.localeCompare(right.label, "no", { numeric: true });
}

function collectionForPublication(registry, publication) {
  return registry.collections.find(collection => collection.publication_values.includes(publication)) ?? null;
}

function collectionById(registry, id) {
  if (typeof id !== "string" || !COLLECTION_SLUG.test(id)) return null;
  return registry.collections.find(collection => collection.id === id) ?? null;
}

function collectionHref(collection) {
  return `collection.html?collection=${encodeURIComponent(collection.id)}`;
}

/* Every medium in the index must belong to a collection. The build refuses an unbound
 * medium (scripts/collection_registry.py); the browser repeats the check because a
 * stale registry next to a newer index would otherwise drop discs from the counts and
 * look like a smaller, or empty, archive. */
function bindingProblem(registry, index) {
  const unbound = indexMedia(index).filter(medium => !collectionForPublication(registry, medium.publication));
  if (unbound.length === 0) return null;
  const names = unbound.map(medium => medium.id ?? medium.label).join(", ");
  return `${countLabel(unbound.length, "medium", "medier")} i indeksen er ikke koblet til noen samling: ${names}.`;
}

function assertBound(registry, index) {
  const problem = bindingProblem(registry, index);
  if (problem) throw new Error(problem);
}

/* Media are counted by stable medium id, never by entry names: the same program can
 * appear on several discs, and every source entry counts once on its own disc. */
function collectionView(registry, index, collection) {
  assertBound(registry, index);
  const media = indexMedia(index)
    .filter(medium => collectionForPublication(registry, medium.publication) === collection)
    .sort(compareMedia);
  const years = [];
  for (const medium of media) {
    const year = parseIssue(medium.label)?.year ?? null;
    const group = years.find(item => item.year === year);
    if (group) group.media.push(medium);
    else years.push({ year, media: [medium] });
  }
  return { collection, media, years, entryCount: media.reduce((sum, medium) => sum + medium.count, 0) };
}

function publishedCollections(registry, index) {
  assertBound(registry, index);
  return registry.collections.map(collection => collectionView(registry, index, collection)).filter(view => view.media.length > 0);
}

function countLabel(count, singular, plural) {
  return `${count.toLocaleString("no")} ${count === 1 ? singular : plural}`;
}

async function loadJson(url, fetcher = fetch) {
  const response = await fetcher(url);
  if (!response.ok) throw new Error(`Kunne ikke hente ${url}: HTTP ${response.status}`);
  try {
    return await response.json();
  } catch (error) {
    throw new Error(`${url} er ikke gyldig JSON`);
  }
}

async function loadRegistry(fetcher = fetch) {
  const registry = await loadJson("collections.json", fetcher);
  const problem = registryProblem(registry);
  if (problem) throw new Error(problem);
  return registry;
}

async function loadIndex(fetcher = fetch) {
  const index = await loadJson("data/index.json", fetcher);
  const problem = indexProblem(index);
  if (problem) throw new Error(problem);
  return index;
}
