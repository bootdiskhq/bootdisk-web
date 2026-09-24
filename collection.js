/* One collection: its editorial introduction from the registry and a card for every
 * medium bound to it in the generated index. Text arrives with the small registry;
 * the CD overview follows when the index is loaded. */
function collectionSetMetadata(title, description, canonical) {
  document.title = title;
  document.querySelector("#page-description").content = description;
  document.querySelector("#og-title").content = title;
  document.querySelector("#og-description").content = description;
  for (const [selector, create] of [["link[rel=canonical]", () => Object.assign(document.createElement("link"), { rel: "canonical" })],
    ["meta[property='og:url']", () => { const meta = document.createElement("meta"); meta.setAttribute("property", "og:url"); return meta; }]]) {
    document.head.querySelector(selector)?.remove();
    if (!canonical) continue;
    const element = create();
    if (element.tagName === "LINK") element.href = canonical;
    else element.content = canonical;
    document.head.append(element);
  }
  if (!canonical && !document.head.querySelector("meta[name=robots]")) {
    const robots = document.createElement("meta");
    robots.name = "robots";
    robots.content = "noindex";
    document.head.append(robots);
  }
}

function collectionStatus(selector, state, text) {
  const status = document.querySelector(selector);
  status.dataset.state = state;
  status.textContent = text;
  status.hidden = !text;
}

function discCard(medium) {
  const item = document.createElement("li");
  const link = document.createElement("a");
  link.className = "disc-card";
  link.href = medium.href;
  const issue = parseIssue(medium.label);

  const cover = document.createElement("span");
  cover.className = "disc-cover";
  cover.setAttribute("aria-hidden", "true");
  const series = document.createElement("span");
  series.className = "disc-series";
  const number = document.createElement("span");
  number.className = "disc-number";
  const year = document.createElement("span");
  year.className = "disc-year";
  if (issue) {
    series.textContent = medium.label.replace(/\s*\d{1,3}\s*\/\s*\d{4}\s*$/, "") || "CD";
    number.textContent = `nr. ${issue.issue}`;
    year.textContent = String(issue.year);
  } else {
    series.textContent = "CD";
    number.textContent = medium.label;
  }
  cover.append(series, number, year);

  const copy = document.createElement("span");
  copy.className = "disc-copy";
  const label = document.createElement("strong");
  label.className = "disc-label";
  label.textContent = medium.label;
  const count = document.createElement("span");
  count.className = "disc-count";
  count.textContent = countLabel(medium.count, "kildepost", "kildeposter");
  const action = document.createElement("span");
  action.className = "disc-action";
  action.textContent = "Se innholdet →";
  copy.append(label, count, action);
  link.append(cover, copy);
  item.append(link);
  return item;
}

function yearGroup(group) {
  const section = document.createElement("section");
  section.className = "disc-year-group";
  const heading = document.createElement("h3");
  heading.id = `year-${group.year ?? "ukjent"}`;
  heading.textContent = group.year === null ? "Uten årstall" : String(group.year);
  section.setAttribute("aria-labelledby", heading.id);
  const list = document.createElement("ul");
  list.className = "disc-grid";
  list.append(...group.media.map(discCard));
  section.append(heading, list);
  return section;
}

function renderCollectionText(collection) {
  document.querySelector("#collection-title").textContent = collection.title;
  const lede = document.querySelector("#collection-lede");
  lede.textContent = collection.lede;
  lede.hidden = false;
  document.querySelector("#collection-jump").hidden = false;
  const trail = document.querySelector("#collection-breadcrumbs");
  const current = document.createElement("li");
  current.textContent = collection.title;
  current.setAttribute("aria-current", "page");
  trail.append(current);
  if (collection.history.length) {
    document.querySelector("#history-heading").textContent = collection.history_title ?? "Bakgrunn";
    document.querySelector("#history-text").replaceChildren(...collection.history.map(text => Object.assign(document.createElement("p"), { textContent: text })));
    document.querySelector("#collection-history").hidden = false;
  }
  if (collection.sources.length) {
    document.querySelector("#sources-list").replaceChildren(...collection.sources.map(source => {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = source.href;
      link.textContent = source.label;
      item.append(link);
      return item;
    }));
    document.querySelector("#collection-sources").hidden = false;
  }
  document.querySelector("#collection-note").hidden = false;
  document.querySelector("#collection-media").hidden = false;
  collectionSetMetadata(`${collection.title} — Bootdisk`, collection.lede,
    new URL(collectionHref(collection), "https://bootdisk.no/").href);
}

function renderCollectionMedia(view) {
  if (view.media.length === 0) {
    collectionStatus("#media-status", "empty", "Samlingen har ingen publiserte CD-er ennå.");
    return;
  }
  const summary = document.querySelector("#media-summary");
  summary.textContent = `${countLabel(view.media.length, "CD", "CD-er")} med til sammen ${countLabel(view.entryCount, "kildepost", "kildeposter")}. Nyeste utgave først.`;
  summary.hidden = false;
  document.querySelector("#media-years").replaceChildren(...view.years.map(yearGroup));
  collectionStatus("#media-status", "ready", "");
}

async function renderCollection() {
  const requested = new URLSearchParams(window.location.search).get("collection");
  const registryRequest = loadRegistry();
  const indexRequest = loadIndex();
  indexRequest.catch(() => {});
  let collection;
  try {
    collection = collectionById(await registryRequest, requested);
  } catch (error) {
    console.error(error);
    document.querySelector("#collection-title").textContent = "Samlingen kunne ikke lastes";
    collectionStatus("#collection-status", "error", "Samlingsoppsettet kunne ikke leses. Det betyr ikke at samlingen er tom. Last siden på nytt, eller gå til alle kildeposter.");
    collectionSetMetadata("Samlingen kunne ikke lastes — Bootdisk", "Samlingen kunne ikke lastes.", null);
    return;
  }
  if (!collection) {
    document.querySelector("#collection-title").textContent = "Fant ikke samlingen";
    collectionStatus("#collection-status", "unknown", requested ? "Det finnes ingen samling med denne adressen. Gå tilbake til Bootdisk for å se samlingene." : "Ingen samling er valgt. Gå tilbake til Bootdisk for å se samlingene.");
    collectionSetMetadata("Fant ikke samlingen — Bootdisk", "Samlingen finnes ikke.", null);
    return;
  }
  renderCollectionText(collection);
  try {
    const registry = await registryRequest;
    renderCollectionMedia(collectionView(registry, await indexRequest, collection));
  } catch (error) {
    console.error(error);
    collectionStatus("#media-status", "error", "CD-oversikten kunne ikke lastes. Det betyr ikke at samlingen er tom. Last siden på nytt, eller gå til alle kildeposter.");
  }
}

renderCollection().finally(() => document.querySelector("main").setAttribute("aria-busy", "false"));
