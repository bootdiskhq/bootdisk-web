/* Archive browsing consumes only the disposable index projection. Detailed Catalog
 * evidence and Publish metadata remain on the entry document, not duplicated here. */
function imageFor(asset) {
  return asset?.derivatives?.find(item => item.kind === "thumbnail") ?? asset?.original;
}

function normalized(value) {
  return String(value ?? "").toLocaleLowerCase("no");
}

function filterEntries(entries, query, status) {
  const needle = normalized(query.trim());
  return entries.filter(entry => {
    const matchesStatus = status === "all" || entry.curation_status === status;
    const haystack = [entry.entry, entry.editorial_title, entry.software_name, entry.version].map(normalized).join(" ");
    return matchesStatus && haystack.includes(needle);
  });
}

function sortEntries(entries, sort) {
  return [...entries].sort((left, right) => {
    if (sort === "name") {
      const leftName = left.software_name ?? left.editorial_title ?? left.entry;
      const rightName = right.software_name ?? right.editorial_title ?? right.entry;
      return leftName.localeCompare(rightName, "no", { sensitivity: "base" });
    }
    return Number(left.entry.slice(1)) - Number(right.entry.slice(1));
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
  const empty = document.querySelector("#archive-empty");
  const search = document.querySelector("#archive-search");
  const status = document.querySelector("#archive-status");
  const sort = document.querySelector("#archive-sort");
  const reset = document.querySelector("#archive-reset");
  const parameters = new URLSearchParams(window.location.search);
  search.value = parameters.get("q") ?? "";
  status.value = ["identified", "pending"].includes(parameters.get("status")) ? parameters.get("status") : "all";
  sort.value = parameters.get("sort") === "name" ? "name" : "source";
  document.querySelector("#archive-source").textContent = `${data.publication} · ${data.medium}`;

  function update() {
    const entries = sortEntries(filterEntries(data.entries, search.value, status.value), sort.value);
    grid.replaceChildren(...entries.map(card));
    empty.hidden = entries.length !== 0;
    count.textContent = `${entries.length} av ${data.entries.length} poster`;
    const next = new URLSearchParams();
    if (search.value.trim()) next.set("q", search.value.trim());
    if (status.value !== "all") next.set("status", status.value);
    if (sort.value !== "source") next.set("sort", sort.value);
    const query = next.toString();
    window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  }
  search.addEventListener("input", update);
  status.addEventListener("change", update);
  sort.addEventListener("change", update);
  reset.addEventListener("click", () => {
    search.value = "";
    status.value = "all";
    sort.value = "source";
    update();
    search.focus();
  });
  update();
}

render().catch(error => {
  console.error(error);
  document.querySelector("#archive-grid").textContent = "Kunne ikke laste arkivoversikten. Bygg frontend-data først.";
});
