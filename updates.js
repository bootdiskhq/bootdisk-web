/* The full update overview (updates.html). Filter and search state live in the address,
 * like the archive's, so links can be shared and the back button restores them. */
function updatesState(state, text) {
  const status = document.querySelector("#updates-status");
  status.dataset.state = state;
  status.textContent = text;
  status.hidden = !text;
}

async function renderUpdates() {
  const list = document.querySelector("#updates-list");
  const more = document.querySelector("#updates-more");
  const count = document.querySelector("#updates-count");
  const search = document.querySelector("#updates-search");
  const reset = document.querySelector("#updates-reset");
  const tools = document.querySelector("#updates-tools");
  const typeInputs = [...document.querySelectorAll("input[name=update-type]")];
  const [feed, index] = await Promise.all([loadUpdates(), loadUpdateIndex()]);
  if (feed === null) {
    updatesState("missing", "Endringsoversikten er ikke publisert ennå. Arkivet og alle kildeposter er tilgjengelige som før.");
    return;
  }
  const rows = latestUpdates(feed, index);
  if (rows.length === 0) {
    updatesState("empty", "Ingen nye eller oppdaterte kildeposter er registrert ennå.");
    return;
  }
  tools.hidden = false;
  const initial = updateParameters(window.location.search);
  search.value = initial.query;
  for (const input of typeInputs) input.checked = input.value === initial.type;
  let shown = 0;
  let matches = [];

  function selectedType() {
    return typeInputs.find(input => input.checked)?.value ?? "all";
  }

  function showMore() {
    const next = matches.slice(shown, shown + UPDATES_PAGE_SIZE);
    list.append(...next.map(row => updateItem(row)));
    shown += next.length;
    more.hidden = shown >= matches.length;
    count.textContent = `Viser ${shown.toLocaleString("no")} av ${matches.length.toLocaleString("no")} ${matches.length === 1 ? "kildepost" : "kildeposter"}`;
    return next.length;
  }

  // A new filter or search always starts again at the first portion.
  function update() {
    matches = filterUpdates(rows, selectedType(), search.value);
    shown = 0;
    list.replaceChildren();
    if (matches.length === 0) {
      updatesState("no-match", "Ingen oppdateringer passer med søket eller filteret.");
      more.hidden = true;
      count.textContent = `Viser 0 av ${rows.length.toLocaleString("no")} kildeposter`;
    } else {
      updatesState("ready", "");
      showMore();
    }
    list.hidden = matches.length === 0;
    window.history.replaceState(null, "", updateSearch(selectedType(), search.value) || window.location.pathname);
  }

  search.addEventListener("input", update);
  for (const input of typeInputs) input.addEventListener("change", update);
  reset.addEventListener("click", () => {
    search.value = "";
    for (const input of typeInputs) input.checked = input.value === "all";
    update();
    search.focus();
  });
  more.addEventListener("click", () => {
    const first = shown;
    if (showMore()) list.children[first]?.querySelector("a")?.focus();
  });
  update();
}

renderUpdates().catch(error => {
  console.error(error);
  updatesState("error", "Endringsoversikten kunne ikke lastes akkurat nå. Det betyr ikke at arkivet er tomt. Last siden på nytt, eller gå til alle kildeposter.");
}).finally(() => {
  document.querySelector("main").setAttribute("aria-busy", "false");
});
