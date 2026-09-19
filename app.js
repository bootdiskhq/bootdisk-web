/* Bootdisk Web deliberately consumes presentation data rather than archive internals.
 * The frontend is disposable: Catalog owns identity and Publish owns web assets. */
function requestedEntry() {
  const requested = new URLSearchParams(window.location.search).get("entry");
  if (!requested) {
    window.location.replace("archive.html");
    return null;
  }
  // Entry ids become filenames only after strict validation; source values never become paths.
  if (!/^K[0-9]+$/i.test(requested)) throw new Error(`Invalid entry id: ${requested}`);
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

async function render() {
  const entryId = requestedEntry();
  if (!entryId) return;
  const dataUrl = `data/${entryId}.json`;
  const [response, indexResponse] = await Promise.all([fetch(dataUrl), fetch("data/index.json")]);
  if (!response.ok) throw new Error(`Cannot load ${dataUrl}: ${response.status}`);
  if (!indexResponse.ok) throw new Error(`Cannot load archive index: ${indexResponse.status}`);
  const [entry, index] = await Promise.all([response.json(), indexResponse.json()]);
  const software = entry.software?.[0];
  const name = software?.software_name ?? entry.editorial_title ?? entry.entry;
  const knownVersion = software?.version && software.version !== "unknown" ? software.version : null;
  const version = knownVersion ?? "Ukjent versjon";
  const description = preferredDescription(software);

  document.querySelector("#source-context").textContent = `${entry.publication ?? "KOMPUTER FOR ALLE"} · ${entry.medium ?? "K-CD 15/2001"} · ${entry.entry}`;
  document.querySelector("#software-name").textContent = name;
  document.querySelector("#software-version").textContent = knownVersion ? `versjon ${version}` : version;
  const descriptionElement = document.querySelector("#software-description");
  if (description) descriptionElement.textContent = description;
  document.querySelector("#fact-name").textContent = name;
  document.querySelector("#fact-version").textContent = version;
  document.querySelector("#fact-entry").textContent = entry.entry;
  document.querySelector("#fact-medium").textContent = entry.medium ?? "—";
  document.querySelector("#fact-status").textContent = statusLabel(entry.curation_status, software?.status);
  setMetadata(name, knownVersion, entry, description);
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

  const icon = assetFor(entry.assets ?? [], "icon");
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
    screenshot.alt = `Skjermbilde fra ${name}`;
    document.querySelector("#screenshot-frame").hidden = false;
  }
  document.querySelector("main").setAttribute("aria-busy", "false");
}

render().catch(error => {
  console.error(error);
  document.querySelector("#software-name").textContent = "Kunne ikke laste arkivpost";
  document.querySelector("#software-version").textContent = "Sjekk at frontend-data og /store er tilgjengelig.";
  const alert = document.querySelector("#entry-error");
  alert.textContent = "Arkivposten kunne ikke lastes.";
  alert.hidden = false;
  document.querySelector(".window").hidden = true;
  document.querySelector(".entry-navigation").hidden = true;
  document.querySelector("main").setAttribute("aria-busy", "false");
});
