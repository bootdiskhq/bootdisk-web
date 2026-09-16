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
  document.querySelector("#fact-status").textContent = entry.curation_status ?? "ukjent";
  document.title = `${name}${software?.version ? ` ${version}` : ""} — Bootdisk`;

  const position = index.entries.findIndex(item => item.entry === entry.entry);
  if (position < 0) throw new Error(`Entry missing from archive index: ${entry.entry}`);
  const previous = index.entries[position - 1];
  const next = index.entries[position + 1];
  if (previous) {
    const link = document.querySelector("#previous-entry");
    link.href = `index.html?entry=${encodeURIComponent(previous.entry)}`;
    link.textContent = `← ${previous.entry}`;
    link.hidden = false;
  }
  if (next) {
    const link = document.querySelector("#next-entry");
    link.href = `index.html?entry=${encodeURIComponent(next.entry)}`;
    link.textContent = `${next.entry} →`;
    link.hidden = false;
  }

  const icon = assetFor(entry.assets ?? [], "icon");
  const shot = assetFor(entry.assets ?? [], "screenshot");
  const iconImage = derivative(icon) ?? icon?.original;
  const shotImage = derivative(shot) ?? shot?.original;
  if (iconImage?.public_path) {
    const iconElement = document.querySelector("#software-icon");
    iconElement.src = iconImage.public_path;
    iconElement.hidden = false;
  }
  if (shotImage?.public_path) {
    document.querySelector("#software-shot").src = shotImage.public_path;
    document.querySelector("#screenshot-frame").hidden = false;
  }
}

render().catch(error => {
  console.error(error);
  document.querySelector("#software-name").textContent = "Kunne ikke laste arkivpost";
  document.querySelector("#software-version").textContent = "Sjekk at frontend-data og /store er tilgjengelig.";
  document.querySelector(".window").hidden = true;
  document.querySelector(".entry-navigation").hidden = true;
});
