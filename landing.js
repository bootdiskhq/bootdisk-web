/* The Bootdisk front page. Collections come from the Web-owned registry; the numbers
 * are counted from the generated archive index, never from detail documents. */
function landingCollection(view, featured) {
  const article = document.createElement("article");
  article.className = featured ? "collection-feature is-featured" : "collection-feature";
  const headingId = `collection-${view.collection.id}`;
  article.setAttribute("aria-labelledby", headingId);

  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "SAMLING";
  const heading = document.createElement("h3");
  heading.id = headingId;
  heading.textContent = view.collection.title;
  const summary = document.createElement("p");
  summary.className = "collection-summary";
  summary.textContent = view.collection.summary;

  const stats = document.createElement("dl");
  stats.className = "collection-stats";
  for (const [label, value] of [["CD-er", view.media.length], ["Kildeposter", view.entryCount]]) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const number = document.createElement("dd");
    number.textContent = value.toLocaleString("no");
    row.append(term, number);
    stats.append(row);
  }

  const link = document.createElement("a");
  link.className = "primary-link";
  link.href = collectionHref(view.collection);
  link.textContent = `Utforsk ${view.collection.title}`;
  article.append(eyebrow, heading, summary, stats, link);
  return article;
}

async function renderLanding() {
  if (new URLSearchParams(window.location.search).has("entry")) return;
  const status = document.querySelector("#landing-status");
  const list = document.querySelector("#landing-list");
  try {
    const [registry, index] = await Promise.all([loadRegistry(), loadIndex()]);
    const views = publishedCollections(registry, index);
    if (views.length === 0) {
      status.dataset.state = "empty";
      status.textContent = "Ingen samlinger er publisert ennå. Alle kildeposter i arkivet er likevel tilgjengelige.";
    } else {
      list.replaceChildren(...views.map((view, position) => landingCollection(view, position === 0)));
      status.dataset.state = "ready";
      status.textContent = "";
      status.hidden = true;
    }
  } catch (error) {
    console.error(error);
    status.dataset.state = "error";
    status.textContent = "Samlingene kunne ikke lastes akkurat nå. Det betyr ikke at arkivet er tomt. Last siden på nytt, eller gå til alle kildeposter.";
  }
  document.querySelector("main").setAttribute("aria-busy", "false");
}

renderLanding();
