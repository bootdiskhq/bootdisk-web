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
  link.innerHTML = `<div class="archive-card-icon">${image?.public_path ? `<img src="${image.public_path}" alt="" width="32" height="32">` : "<span>?</span>"}</div><div class="archive-card-copy"><strong>${name}</strong>${entry.version ? `<span>versjon ${entry.version}</span>` : ""}${secondary ? `<small>${secondary}</small>` : ""}</div><span class="archive-entry">${entry.entry}</span>`;
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
