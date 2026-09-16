/* Bootdisk Web deliberately consumes presentation data rather than archive internals.
 * The frontend is disposable: Catalog owns identity and Publish owns web assets. */
const DATA_URL = "data/k37.json";

function derivative(asset, kind = "thumbnail") {
  return asset?.derivatives?.find(item => item.kind === kind);
}

function assetFor(assets, kind) {
  return assets.find(asset => asset.kind === kind);
}

async function render() {
  const response = await fetch(DATA_URL);
  if (!response.ok) throw new Error(`Cannot load ${DATA_URL}: ${response.status}`);
  const entry = await response.json();
  const software = entry.software?.[0];
  const name = software?.software_name ?? entry.editorial_title ?? entry.entry;
  const version = software?.version ?? "Uidentifisert versjon";

  document.querySelector("#software-name").textContent = name;
  document.querySelector("#software-version").textContent = `versjon ${version}`;
  document.querySelector("#fact-name").textContent = name;
  document.querySelector("#fact-version").textContent = version;
  document.querySelector("#fact-status").textContent = entry.curation_status ?? "ukjent";
  document.title = `${name} ${version} — Bootdisk`;

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
