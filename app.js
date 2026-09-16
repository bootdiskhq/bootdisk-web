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

function statusLabel(status) {
  return { identified: "Identifisert", pending: "Venter på identifisering" }[status] ?? "Ukjent";
}

function entryName(entry) {
  return entry?.software_name ?? entry?.editorial_title ?? entry?.entry;
}

function bindArrowNavigation(previous, next) {
  document.addEventListener("keydown", event => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const destination = event.key === "ArrowLeft" ? previous : event.key === "ArrowRight" ? next : null;
    if (!destination) return;
    window.location.href = `index.html?entry=${encodeURIComponent(destination.entry)}`;
  });
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
  const version = software?.version ?? "Uidentifisert versjon";

  document.querySelector("#source-context").textContent = `${entry.publication ?? "KOMPUTER FOR ALLE"} · ${entry.medium ?? "K-CD 15/2001"} · ${entry.entry}`;
  document.querySelector("#software-name").textContent = name;
  document.querySelector("#software-version").textContent = software?.version ? `versjon ${version}` : version;
  document.querySelector("#fact-name").textContent = name;
  document.querySelector("#fact-version").textContent = version;
  document.querySelector("#fact-entry").textContent = entry.entry;
  document.querySelector("#fact-medium").textContent = entry.medium ?? "—";
  document.querySelector("#fact-status").textContent = statusLabel(entry.curation_status);
  document.title = `${name}${software?.version ? ` ${version}` : ""} — Bootdisk`;
  document.querySelector("#page-description").content = `${name}${software?.version ? ` ${version}` : ""} fra ${entry.medium ?? "Bootdisk-arkivet"}, kildepost ${entry.entry}.`;

  const position = index.entries.findIndex(item => item.entry === entry.entry);
  if (position < 0) throw new Error(`Entry missing from archive index: ${entry.entry}`);
  const previous = index.entries[position - 1];
  const next = index.entries[position + 1];
  if (previous) {
    const link = document.querySelector("#previous-entry");
    link.href = `index.html?entry=${encodeURIComponent(previous.entry)}`;
    link.textContent = `← ${entryName(previous)}`;
    link.setAttribute("aria-label", `Forrige program: ${entryName(previous)} (${previous.entry})`);
    link.title = previous.entry;
    link.hidden = false;
  }
  if (next) {
    const link = document.querySelector("#next-entry");
    link.href = `index.html?entry=${encodeURIComponent(next.entry)}`;
    link.textContent = `${entryName(next)} →`;
    link.setAttribute("aria-label", `Neste program: ${entryName(next)} (${next.entry})`);
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
