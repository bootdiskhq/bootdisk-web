/* Bootdisk Web deliberately consumes presentation data rather than archive internals.
 * The frontend is disposable: Catalog owns identity and Publish owns web assets. */
function requestedEntry() {
  const requested = new URLSearchParams(window.location.search).get("entry") ?? "K37";
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
  const dataUrl = `data/${entryId}.json`;
  const response = await fetch(dataUrl);
  if (!response.ok) throw new Error(`Cannot load ${dataUrl}: ${response.status}`);
  const entry = await response.json();
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

  const icon = assetFor(entry.assets ?? [], "icon");
  const shot = assetFor(entry.assets ?? [], "screenshot");
  const iconImage = derivative(icon) ?? icon?.original;
  const shotImage = derivative(shot) ?? shot?.original;
  if (iconImage?.public_path) document.querySelector("#software-icon").src = iconImage.public_path;
  if (shotImage?.public_path) document.querySelector("#software-shot").src = shotImage.public_path;
}

render().catch(error => {
  console.error(error);
  document.querySelector("#software-name").textContent = "Kunne ikke laste arkivpost";
  document.querySelector("#software-version").textContent = "Sjekk at frontend-data og /store er tilgjengelig.";
});
