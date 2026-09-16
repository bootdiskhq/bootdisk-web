/* Archive browsing consumes only the disposable index projection. Detailed Catalog
 * evidence and Publish metadata remain on the entry document, not duplicated here. */
function imageFor(asset) {
  return asset?.derivatives?.find(item => item.kind === "thumbnail") ?? asset?.original;
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
  if (entry.version) {
    const version = document.createElement("span");
    version.textContent = `versjon ${entry.version}`;
    copy.append(version);
  }
  if (secondary) {
    const sourceTitle = document.createElement("small");
    sourceTitle.textContent = secondary;
    copy.append(sourceTitle);
  }

  const sourceId = document.createElement("span");
  sourceId.className = "archive-entry";
  sourceId.textContent = entry.entry;
  link.append(icon, copy, sourceId);
  return link;
}

async function render() {
  const response = await fetch("data/index.json");
  if (!response.ok) throw new Error(`Cannot load archive index: ${response.status}`);
  const data = await response.json();
  const grid = document.querySelector("#archive-grid");
  const count = document.querySelector("#archive-count");
  const search = document.querySelector("#archive-search");
  document.querySelector("#archive-source").textContent = `${data.publication} · ${data.medium}`;

  function update() {
    const needle = search.value.trim().toLocaleLowerCase("no");
    const entries = data.entries.filter(entry => [entry.entry, entry.editorial_title, entry.software_name, entry.version].filter(Boolean).join(" ").toLocaleLowerCase("no").includes(needle));
    grid.replaceChildren(...entries.map(card));
    count.textContent = `${entries.length} av ${data.entries.length} poster`;
  }
  search.addEventListener("input", update);
  update();
}

render().catch(error => {
  console.error(error);
  document.querySelector("#archive-grid").textContent = "Kunne ikke laste arkivoversikten. Bygg frontend-data først.";
});
