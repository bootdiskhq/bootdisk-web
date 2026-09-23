/* Archive browsing consumes only the disposable index projection. Detailed Catalog
 * evidence and Publish metadata remain on the entry document, not duplicated here. */
function imageFor(asset) {
  return asset?.derivatives?.find(item => item.kind === "thumbnail") ?? asset?.original;
}

function normalized(value) {
  return String(value ?? "").toLocaleLowerCase("no");
}

function filterEntries(entries, query, status, medium = "all") {
  const needle = normalized(query.trim());
  return entries.filter(entry => {
    const effectiveStatus = entry.identification_status === "interpreted" ? "interpreted" : entry.curation_status;
    const matchesStatus = status === "all" || effectiveStatus === status;
    const haystack = [entry.entry, entry.editorial_title, entry.software_name, entry.version, entry.medium, entry.source_entry].map(normalized).join(" ");
    return matchesStatus && (medium === "all" || entry.medium_id === medium) && haystack.includes(needle);
  });
}

function sortEntries(entries, sort) {
  return [...entries].sort((left, right) => {
    if (sort === "name") {
      const leftName = left.software_name ?? left.editorial_title ?? left.entry;
      const rightName = right.software_name ?? right.editorial_title ?? right.entry;
      return leftName.localeCompare(rightName, "no", { sensitivity: "base" });
    }
    return (left.source_order ?? Number(left.entry.slice(1))) - (right.source_order ?? Number(right.entry.slice(1)));
  });
}

function card(entry) {
  const link = document.createElement("a");
  link.className = "archive-card";
  link.href = `index.html?entry=${encodeURIComponent(entry.entry)}`;
  const image = imageFor(entry.icon);
  const name = entry.software_name ?? entry.editorial_title ?? entry.entry;
  const secondary = entry.software_name && entry.editorial_title !== entry.software_name ? entry.editorial_title : null;
  const icon = document.createElement("div");
  icon.className = "archive-card-icon";
  if (image?.public_path) {
    const img = document.createElement("img");
    img.src = image.public_path;
    img.alt = "";
    img.width = 32;
    img.height = 32;
    icon.append(img);
  } else {
    const placeholder = document.createElement("span");
    placeholder.textContent = "?";
    icon.append(placeholder);
  }

  const copy = document.createElement("div");
  copy.className = "archive-card-copy";
  const strong = document.createElement("strong");
  strong.textContent = name;
  copy.append(strong);
  if (entry.version && entry.version !== "unknown") {
    const version = document.createElement("span");
    version.textContent = `versjon ${entry.version}`;
    copy.append(version);
  }
  if (entry.identification_status === "interpreted") {
    const note = document.createElement("small");
    note.textContent = "Foreløpig identifisering";
    copy.append(note);
  }
  if (secondary) {
    const sourceTitle = document.createElement("small");
    sourceTitle.textContent = secondary;
    copy.append(sourceTitle);
  }

  const sourceId = document.createElement("span");
  sourceId.className = "archive-entry";
  sourceId.textContent = entry.source_entry ?? entry.entry;
  if (entry.medium) {
    const medium = document.createElement("small");
    medium.textContent = entry.medium;
    copy.append(medium);
  }
  if (entry.curation_status === "pending") {
    const status = document.createElement("small");
    status.textContent = "Venter på identifisering";
    copy.append(status);
  }
  link.append(icon, copy, sourceId);
  return link;
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

async function render() {
  const registryRequest = typeof loadRegistry === "function" ? loadRegistry().catch(error => { console.warn(error); return null; }) : Promise.resolve(null);
  const response = await fetch("data/index.json");
  if (!response.ok) throw new Error(`Cannot load archive index: ${response.status}`);
  const data = await response.json();
  const registry = await registryRequest;
  const grid = document.querySelector("#archive-grid");
  const count = document.querySelector("#archive-count");
  const empty = document.querySelector("#archive-empty");
  const search = document.querySelector("#archive-search");
  const status = document.querySelector("#archive-status");
  const medium = document.querySelector("#archive-medium");
  for (const item of data.media ?? []) {
    const option = document.createElement("option");
    option.value = item.id; option.textContent = item.medium; medium.append(option);
  }
  const sort = document.querySelector("#archive-sort");
  const reset = document.querySelector("#archive-reset");
  const parameters = new URLSearchParams(window.location.search);
  const requestedMedium = parameters.get("medium");
  medium.value = (data.media ?? []).some(item => item.id === requestedMedium) ? requestedMedium : "all";
  if (requestedMedium !== null && medium.value === "all") {
    const notice = document.querySelector("#archive-notice");
    notice.textContent = "Fant ikke CD-en i lenken. Viser alle kildeposter i stedet.";
    notice.hidden = false;
  }
  search.value = parameters.get("q") ?? "";
  status.value = ["identified", "interpreted", "pending"].includes(parameters.get("status")) ? parameters.get("status") : "all";
  sort.value = parameters.get("sort") === "name" ? "name" : "source";

  function update() {
    const entries = sortEntries(filterEntries(data.entries, search.value, status.value, medium.value), sort.value);
    grid.replaceChildren(...entries.map(card));
    empty.hidden = entries.length !== 0;
    count.textContent = `${entries.length} av ${data.entries.length} poster`;
    const next = new URLSearchParams();
    if (search.value.trim()) next.set("q", search.value.trim());
    if (medium.value !== "all") next.set("medium", medium.value);
    if (status.value !== "all") next.set("status", status.value);
    if (sort.value !== "source") next.set("sort", sort.value);
    renderArchiveContext(archiveContext(data, registry, medium.value));
    const query = next.toString();
    window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  }
  search.addEventListener("input", update);
  status.addEventListener("change", update);
  medium.addEventListener("change", update);
  sort.addEventListener("change", update);
  reset.addEventListener("click", () => {
    search.value = "";
    status.value = "all";
    medium.value = "all";
    sort.value = "source";
    update();
    search.focus();
  });
  update();
}

render().catch(error => {
  console.error(error);
  const notice = document.querySelector("#archive-notice");
  notice.textContent = "Kunne ikke laste arkivoversikten. Det betyr ikke at arkivet er tomt. Last siden på nytt.";
  notice.hidden = false;
  document.querySelector("#archive-grid").textContent = "Kunne ikke laste arkivoversikten. Bygg frontend-data først.";
});
