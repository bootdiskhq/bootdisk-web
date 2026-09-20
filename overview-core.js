/* Overview logic for the curator, kept free of the DOM so the observable behaviour
 * (combined search and filters, stable pagination, the round trip to the detail screen and
 * the refresh after a decision) can be tested directly. overview.js binds this to the page.
 * The shared URL helpers live in curator-navigation.js.
 *
 * Nothing here writes. The controller only ever calls the read methods of the prototype
 * overview adapter, so searching and filtering cannot approve, defer or change a draft.
 */
function createOverviewController(options) {
  const adapter = options.adapter;
  /* Wrapped rather than passed by reference: a detached setTimeout throws
   * "Illegal invocation" in the browser. */
  const scheduler = options.scheduler ?? {
    set: (callback, delay) => setTimeout(callback, delay),
    clear: handle => clearTimeout(handle),
  };
  const searchDelay = options.searchDelay ?? 150;
  const listeners = new Set();

  const state = {
    ready: false,
    loading: false,
    error: null,
    /* What the curator has typed, which may not be searched for yet. */
    input: "",
    query: "",
    status: "all",
    field: "all",
    sort: "name",
    page: 1,
    pageSize: options.pageSize ?? adapter.pageSize ?? 50,
    items: [],
    total: adapter.total ?? 0,
    matched: 0,
    pageCount: 1,
    focusKey: null,
    /* Set when a decided row no longer belongs in the active filter but is kept in place. */
    outsideFilter: null,
  };

  let searchTimer = null;
  /* Every load takes the next token; only the newest one may reach the state, so a slow
   * old result can never replace a newer one. */
  let requestToken = 0;

  function emit() {
    for (const listener of listeners) listener(state);
  }

  function sameKey(left, right) {
    return Boolean(left && right && left.manifest === right.manifest && left.entry === right.entry);
  }

  function cancelSearch() {
    if (searchTimer !== null) {
      scheduler.clear(searchTimer);
      searchTimer = null;
    }
  }

  function load() {
    const token = ++requestToken;
    state.loading = true;
    state.error = null;
    emit();
    return adapter.listEntries({
      query: state.query,
      status: state.status,
      field: state.field,
      sort: state.sort,
      page: state.page,
      page_size: state.pageSize,
    }).then(result => {
      if (token !== requestToken) return null;
      state.loading = false;
      state.ready = true;
      state.items = result.items;
      state.status = result.status;
      state.field = result.field;
      state.sort = result.sort;
      state.total = result.total;
      state.matched = result.matched;
      state.page = result.page;
      state.pageCount = result.page_count;
      state.outsideFilter = null;
      emit();
      return result;
    }, error => {
      if (token !== requestToken) return null;
      state.loading = false;
      state.ready = true;
      state.error = { message: error?.message ?? "Oversikten kunne ikke lastes." };
      emit();
      return null;
    });
  }

  /* A changed search or filter always starts on the first page: keeping the page number
   * would land the curator on an empty page of a smaller result, and the row that was
   * waiting to be focused is no longer what the curator is looking at. */
  function reload() {
    state.page = 1;
    state.focusKey = null;
    return load();
  }

  function setInput(value) {
    state.input = value;
    state.focusKey = null;
    emit();
    cancelSearch();
    return new Promise(resolve => {
      searchTimer = scheduler.set(() => {
        searchTimer = null;
        state.query = state.input;
        resolve(reload());
      }, searchDelay);
    });
  }

  function searchNow() {
    cancelSearch();
    state.query = state.input;
    return reload();
  }

  function setStatus(status) {
    state.status = status;
    return reload();
  }

  function setField(field) {
    state.field = field;
    return reload();
  }

  function setSort(sort) {
    state.sort = sort;
    return reload();
  }

  function setPage(page) {
    const target = Math.min(Math.max(1, page), state.pageCount);
    if (target === state.page) return Promise.resolve(null);
    state.page = target;
    state.focusKey = null;
    return load();
  }

  function reset() {
    cancelSearch();
    state.input = "";
    state.query = "";
    state.status = "all";
    state.field = "all";
    state.focusKey = null;
    return reload();
  }

  function restore(initial) {
    cancelSearch();
    state.input = initial.query ?? "";
    state.query = initial.query ?? "";
    state.status = initial.status ?? "all";
    state.field = initial.field ?? "all";
    state.sort = initial.sort ?? "name";
    state.page = initial.page ?? 1;
    state.focusKey = initial.focusKey ?? null;
  }

  /* Reads one entry back through the ordinary adapter and puts the answer in the row. A row
   * that no longer belongs in the active filter keeps its place and says why, rather than
   * vanishing under the curator on return. */
  function refreshRow(key) {
    return adapter.refreshEntry(key).then(summary => {
      if (!summary) return null;
      const position = state.items.findIndex(item => sameKey(item.key, summary.key));
      const belongs = adapter.matches(summary, { query: state.query, status: state.status, field: state.field });
      if (position >= 0) {
        state.items[position] = summary;
      } else {
        const comparator = adapter.comparator(state.sort);
        const at = state.items.findIndex(item => comparator(summary, item) < 0);
        state.items.splice(at < 0 ? state.items.length : at, 0, summary);
      }
      state.outsideFilter = belongs ? null : { key: summary.key, title: summary.title };
      emit();
      return summary;
    }, () => null);
  }

  /* Coming back from the detail screen: the decided row is read first so the list is built
   * from the adapter's actual answer, then the page is rebuilt around it. */
  function reopen(initial) {
    restore(initial);
    const focus = state.focusKey;
    const first = focus ? adapter.refreshEntry(focus).then(() => null, () => null) : Promise.resolve(null);
    return first.then(load).then(result => (focus ? refreshRow(focus).then(() => result) : result));
  }

  function start(initial) {
    if (initial) return reopen(initial);
    return load();
  }

  return {
    state,
    start,
    reopen,
    setInput,
    searchNow,
    setStatus,
    setField,
    setSort,
    setPage,
    reset,
    refreshRow,
    urlQuery() {
      return overviewStateToQuery(state);
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { createOverviewController };
}
