/* Where the curator is in the overview, carried in the address bar.
 *
 * The overview keeps its search, filters, page and row here so a link is shareable and the
 * detail screen can hand the exact same view back. Both curator screens load this file.
 */
const OVERVIEW_QUERY_KEYS = ["q", "status", "felt", "sort", "side", "manifest", "rad"];

/* Values are passed on as they are read; the adapter decides what is allowed and reports
 * the effective request back, so the allowed values live in one place only. */
function overviewStateFromQuery(params) {
  const read = key => params.get(key) ?? "";
  const page = Number.parseInt(read("side"), 10);
  const manifest = read("manifest");
  const entry = read("rad");
  return {
    query: read("q"),
    status: read("status") || "all",
    field: read("felt") || "all",
    sort: read("sort") || "name",
    page: Number.isFinite(page) && page > 0 ? page : 1,
    focusKey: manifest && entry ? { manifest, entry } : null,
  };
}

function overviewStateToQuery(state) {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.status && state.status !== "all") params.set("status", state.status);
  if (state.field && state.field !== "all") params.set("felt", state.field);
  if (state.sort && state.sort !== "name") params.set("sort", state.sort);
  if (state.page && state.page !== 1) params.set("side", String(state.page));
  if (state.focusKey) {
    params.set("manifest", state.focusKey.manifest);
    params.set("rad", state.focusKey.entry);
  }
  return params;
}

/* Rebuilds a return address from untrusted text: only the known keys survive, and the
 * result is always a query string for the overview page itself. */
function overviewSafeReturnQuery(raw) {
  const params = new URLSearchParams(String(raw ?? ""));
  const safe = new URLSearchParams();
  for (const key of OVERVIEW_QUERY_KEYS) {
    const value = params.get(key);
    if (value !== null && value !== "") safe.set(key, value);
  }
  return safe.toString();
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    overviewStateFromQuery,
    overviewStateToQuery,
    overviewSafeReturnQuery,
    OVERVIEW_QUERY_KEYS,
  };
}
