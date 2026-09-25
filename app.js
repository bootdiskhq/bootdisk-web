function renderSourceDocuments(entry, description) {
  const container = document.querySelector("#source-documents");
  if (!container) return;
  container.replaceChildren();
  const normalize = value => (value ?? "").replace(/\s+/g, " ").trim();
  for (const doc of entry.source_documents ?? []) {
    const original = doc.original ?? {};
    if (!/^[a-f0-9]{64}$/.test(original.sha256 ?? "") || original.public_path !== `store/documents/sha256/${original.sha256.slice(0, 2)}/${original.sha256}.rtf`) continue;
    const block = document.createElement("details");
    const summary = document.createElement("summary");
    const same = normalize(doc.text) === normalize(description);
    summary.textContent = same ? "Original omtale som RTF" : "Les originaltekst fra CD-en (RTF)";
    block.append(summary);
    if (doc.text && !same) {
      const text = document.createElement("div");
      text.className = "rtf-source-text"; text.textContent = doc.text; block.append(text);
    } else if (!doc.text) {
      const note = document.createElement("p"); note.textContent = "Teksten kunne ikke vises. Originalfilen er tilgjengelig nedenfor."; block.append(note);
    }
    const source = document.createElement("p"); source.className = "provenance";
    source.textContent = `Kilde: ${doc.path}`; block.append(source);
    const link = document.createElement("a"); link.href = original.public_path;
    link.download = (doc.path ?? "omtale.rtf").split("/").pop();
    link.textContent = `Last ned originalfil (RTF, ${Math.ceil(original.size / 1024)} kB)`;
    block.append(link); container.append(block);
  }
  container.hidden = !container.children.length;
}

/* Bootdisk Web deliberately consumes presentation data rather than archive internals.
 * The frontend is disposable: Catalog owns identity and Publish owns web assets. */
function requestedEntry() {
  const parameters = new URLSearchParams(window.location.search);
  // Without an entry parameter index.html is the Bootdisk front page (landing.js).
  if (!parameters.has("entry")) return null;
  const requested = parameters.get("entry");
  // Entry ids become filenames only after strict validation; source values never become paths.
  if (!/^(?:[a-z0-9]+(?:-[a-z0-9]+)*--)?[a-z][a-z0-9]{0,63}$/i.test(requested)) throw Object.assign(new Error(`Invalid entry id: ${requested}`), { unknownEntry: true });
  return requested.toLowerCase();
}

function derivative(asset, kind = "thumbnail") {
  return asset?.derivatives?.find(item => item.kind === kind);
}

function assetFor(assets, kind) {
  return assets.find(asset => asset.kind === kind);
}

function statusLabel(status, identificationStatus) {
  if (identificationStatus === "interpreted") return "Foreløpig identifisering";
  return { identified: "Identifisert", pending: "Venter på identifisering" }[status] ?? "Ukjent";
}

function entryName(entry) {
  return entry?.software_name ?? entry?.editorial_title ?? entry?.entry;
}

function preferredDescription(software, language = "nb-NO") {
  const descriptions = software?.descriptions ?? [];
  return descriptions.find(item => item.language === language)?.text ?? descriptions[0]?.text;
}

function bindArrowNavigation(previous, next) {
  document.addEventListener("keydown", event => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const destination = event.key === "ArrowLeft" ? previous : event.key === "ArrowRight" ? next : null;
    if (!destination) return;
    window.location.href = `index.html?entry=${encodeURIComponent(destination.entry)}`;
  });
}

function setMetadata(name, version, entry, curatedDescription) {
  const title = `${name}${version ? ` ${version}` : ""} — Bootdisk`;
  const description = curatedDescription ?? `${name}${version ? ` ${version}` : ""} fra ${entry.medium ?? "Bootdisk-arkivet"}, kildepost ${entry.entry}.`;
  const url = new URL("index.html", "https://bootdisk.no/");
  url.searchParams.set("entry", entry.entry);
  document.title = title;
  document.querySelector("#page-description").content = description;
  document.querySelector("#canonical-url").href = url.href;
  document.querySelector("#og-title").content = title;
  document.querySelector("#og-description").content = description;
  document.querySelector("#og-url").content = url.href;
}

/* Bootdisk → collection → medium → entry. The registry only adds names and links; if it
 * cannot be read the entry still renders, with the archive as its parent. */
function breadcrumbTrail(entry, name, registry) {
  const trail = [{ label: "Bootdisk", href: "./" }];
  const collection = registry ? collectionForPublication(registry, entry.publication) : null;
  trail.push(collection ? { label: collection.title, href: collectionHref(collection) } : { label: "Alle kildeposter", href: "archive.html" });
  if (entry.medium) trail.push({ label: entry.medium, href: entry.medium_id ? `archive.html?medium=${encodeURIComponent(entry.medium_id)}` : "archive.html" });
  trail.push({ label: name, href: null });
  return trail;
}

function renderBreadcrumbs(trail) {
  const list = document.querySelector("#entry-breadcrumbs");
  list.replaceChildren(...trail.map(item => {
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
}

async function render() {
  const entryId = requestedEntry();
  if (!entryId) return;
  const dataUrl = `data/${entryId}.json`;
  const registryRequest = typeof loadRegistry === "function" ? loadRegistry().catch(error => { console.warn(error); return null; }) : Promise.resolve(null);
  const [response, indexResponse] = await Promise.all([fetch(dataUrl), fetch("data/index.json")]);
  if (!response.ok) throw Object.assign(new Error(`Cannot load ${dataUrl}: ${response.status}`), { unknownEntry: response.status === 404 });
  if (!indexResponse.ok) throw new Error(`Cannot load archive index: ${indexResponse.status}`);
  const [entry, index] = await Promise.all([response.json(), indexResponse.json()]);
  const software = entry.software?.[0];
  const name = software?.software_name ?? entry.editorial_title ?? entry.entry;
  const knownVersion = software?.version && software.version !== "unknown" ? software.version : null;
  const version = knownVersion ?? "Ikke oppgitt";
  const description = entry.source_context?.description?.value ?? preferredDescription(software);
  const sourceEntry = entry.source_entry ?? entry.entry;

  document.querySelector("#source-context").textContent = `${entry.publication ?? "KOMPUTER FOR ALLE"} · ${entry.medium ?? "K-CD 15/2001"} · ${sourceEntry}`;
  document.querySelector("#software-name").textContent = name;
  document.querySelector("#software-version").textContent = knownVersion ? `versjon ${version}` : version;
  const descriptionElement = document.querySelector("#software-description");
  if (description) descriptionElement.textContent = description;
  else descriptionElement.textContent = "Ingen entydig omtale er hentet fra CD-en ennå.";
  document.querySelector("#description-label").hidden = !entry.source_context?.description;
  renderSourceDocuments(entry, description);
  const notes = [];
  if (entry.curation_status === "pending") notes.push("Navnet er hentet fra CD-menyen. Programidentitet, versjon og utgave er ikke bekreftet.");
  if (entry.source_context?.issues?.value?.length) notes.push("CD-menyen har motstridende eller manglende filhenvisninger. Innholdstilknytningen må undersøkes nærmere.");
  const note = document.querySelector("#source-note");
  note.textContent = notes.join(" ");
  note.hidden = !notes.length;
  document.querySelector("#fact-name").textContent = name;
  document.querySelector("#fact-version").textContent = version;
  document.querySelector("#fact-entry").textContent = sourceEntry;
  document.querySelector("#fact-medium").textContent = entry.medium ?? "—";
  document.querySelector("#fact-status").textContent = statusLabel(entry.curation_status, software?.status);
  setMetadata(name, knownVersion, entry, description);
  renderBreadcrumbs(breadcrumbTrail(entry, name, await registryRequest));
  document.querySelector("#fact-kind").textContent = ({application: "Program", game: "Spill", course: "Kurs / veiledning", image_collection: "Bildesamling", font_collection: "Skriftpakke", reference: "Oppslagsverk"})[software?.content_kind] ?? "Ukjent";
  document.querySelector("#fact-distribution").textContent = ({full: "Fullversjon", demo: "Demo", trial: "Prøveversjon", update: "Oppdatering", unknown: "Ukjent"})[software?.distribution_kind] ?? "Ukjent";

  const position = index.entries.findIndex(item => item.entry === entry.entry);
  if (position < 0) throw new Error(`Entry missing from archive index: ${entry.entry}`);
  const previous = index.entries[position - 1];
  const next = index.entries[position + 1];
  if (previous) {
    const link = document.querySelector("#previous-entry");
    link.href = `index.html?entry=${encodeURIComponent(previous.entry)}`;
    link.textContent = `← ${entryName(previous)}`;
    link.setAttribute("aria-label", `Forrige post: ${entryName(previous)} (${previous.entry})`);
    link.title = previous.entry;
    link.hidden = false;
  }
  if (next) {
    const link = document.querySelector("#next-entry");
    link.href = `index.html?entry=${encodeURIComponent(next.entry)}`;
    link.textContent = `${entryName(next)} →`;
    link.setAttribute("aria-label", `Neste post: ${entryName(next)} (${next.entry})`);
    link.title = next.entry;
    link.hidden = false;
  }
  bindArrowNavigation(previous, next);

  const icon = assetFor(entry.assets ?? [], "icon") ?? assetFor(entry.assets ?? [], "screenshot");
  const shot = assetFor(entry.assets ?? [], "screenshot");
  const iconImage = derivative(icon) ?? icon?.original;
  const shotImage = derivative(shot) ?? shot?.original;
  if (iconImage?.public_path) {
    const iconElement = document.querySelector("#software-icon");
    iconElement.src = iconImage.public_path;
    iconElement.alt = "";
    iconElement.hidden = false;
  }
  if (shotImage?.public_path) {
    const screenshot = document.querySelector("#software-shot");
    screenshot.src = shotImage.public_path;
    screenshot.alt = `Bilde fra CD-menyen: ${name}`;
    document.querySelector("#screenshot-frame").hidden = false;
  }
  document.querySelector("main").setAttribute("aria-busy", "false");
}

render().catch(error => {
  console.error(error);
  // A failed entry must not keep the front page's title or canonical URL.
  document.title = "Arkivposten ble ikke funnet — Bootdisk";
  document.querySelector("#canonical-url")?.remove();
  const robots = document.createElement("meta");
  robots.name = "robots";
  robots.content = "noindex";
  document.head.append(robots);
  document.querySelector("#software-name").textContent = error.unknownEntry ? "Fant ikke arkivposten" : "Kunne ikke laste arkivpost";
  document.querySelector("#software-version").textContent = error.unknownEntry ? "Lenken er ugyldig eller utdatert." : "Sjekk at frontend-data og /store er tilgjengelig.";
  document.querySelector("#source-context").textContent = "ARKIVPOST";
  document.querySelector("#software-description").textContent = "Gå til alle kildeposter for å finne det du lette etter.";
  const alert = document.querySelector("#entry-error");
  alert.textContent = error.unknownEntry ? "Det finnes ingen arkivpost med denne adressen." : "Arkivposten kunne ikke lastes.";
  alert.hidden = false;
  document.querySelector(".window").hidden = true;
  document.querySelector(".entry-navigation").hidden = true;
  document.querySelector("main").setAttribute("aria-busy", "false");
});
