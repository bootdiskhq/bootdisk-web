/* "Sist lagt til og oppdatert" on the front page: the eight newest rows. It loads on
 * its own, and any failure stays inside this section; the collections above it and the
 * archive are unaffected. Without published history the section stays hidden. */
async function renderLandingUpdates() {
  if (new URLSearchParams(window.location.search).has("entry")) return;
  const section = document.querySelector("#landing-updates");
  const status = document.querySelector("#landing-updates-status");
  const list = document.querySelector("#landing-updates-list");
  const all = document.querySelector("#landing-updates-all");
  try {
    const [feed, index] = await Promise.all([loadUpdates(), loadUpdateIndex()]);
    if (feed === null) return;
    section.hidden = false;
    const rows = latestUpdates(feed, index).slice(0, UPDATES_LANDING_COUNT);
    if (rows.length === 0) {
      status.dataset.state = "empty";
      status.textContent = "Ingen nye eller oppdaterte kildeposter er registrert ennå.";
      return;
    }
    list.replaceChildren(...rows.map(row => updateItem(row)));
    list.hidden = false;
    all.hidden = false;
    status.dataset.state = "ready";
    status.textContent = "";
    status.hidden = true;
  } catch (error) {
    console.error(error);
    section.hidden = false;
    status.dataset.state = "error";
    status.textContent = "Oppdateringene kunne ikke lastes akkurat nå. Samlingene og arkivet er ikke berørt.";
  }
}

renderLandingUpdates();
