/* Page binding for the curator overview. Rendering is text-only, like the decision screen.
 * The page reads; it never approves, defers or writes a draft. */
const OVERVIEW_FIELD_LABELS = {
  identity: "identitet",
  version: "versjon",
  content_kind: "innholdstype",
  distribution_kind: "utgave",
  description: "beskrivelse",
};
const OVERVIEW_COLUMN_LABELS = {
  title: "Program",
  source: "Kildepost",
  version: "Versjon",
  content_kind: "Innholdstype",
  distribution_kind: "Utgave",
  status: "Status",
  resolution: "Avklaring",
};

function overviewElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function overviewFieldList(fields) {
  return fields.map(field => OVERVIEW_FIELD_LABELS[field] ?? field).join(", ");
}

/* Review state the detail screen has already stored for these synthetic manifests. Reading
 * it is prototype-only: the real service will answer the overview from its own index. */
function overviewStoredRecords(storage, manifestId) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(sampleStorageKey(manifestId));
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed?.entries ?? null;
  } catch (error) {
    return null;
  }
}

function overviewBrowserStorage() {
  try {
    window.localStorage.setItem("overview-probe", "1");
    window.localStorage.removeItem("overview-probe");
    return window.localStorage;
  } catch (error) {
    return null;
  }
}

function bootstrapOverview() {
  const storage = overviewBrowserStorage();
  const manifestLabels = sampleManifestLabels();
  const rows = sampleSummaries(overviewSummary);

  const stored = new Map();
  for (const manifest of OVERVIEW_SAMPLE_MANIFESTS) {
    const records = overviewStoredRecords(storage, manifest.id);
    if (records) stored.set(manifest.id, records);
  }
  if (stored.size) {
    for (let index = 0; index < rows.length; index += 1) {
      const record = stored.get(rows[index].key.manifest)?.[rows[index].key.entry];
      if (record) rows[index] = overviewApplyRecord(rows[index], record);
    }
  }

  /* One v1 adapter per manifest, built the first time that manifest is read. Nothing is
   * built at startup, so opening the overview costs no detail call at all. */
  const curators = new Map();
  function curatorFor(manifestId) {
    if (!curators.has(manifestId)) {
      curators.set(manifestId, createFixtureAdapter({
        fixture: createSampleBundle(manifestId),
        datasetId: sampleDatasetId(manifestId),
        storage,
      }));
    }
    return curators.get(manifestId);
  }

  const adapter = createOverviewAdapter({ rows, curatorFor, manifestLabels });
  const controller = createOverviewController({ adapter });

  const nodes = {
    fatal: document.querySelector("#overview-fatal"),
    search: document.querySelector("#overview-search"),
    status: document.querySelector("#overview-status"),
    field: document.querySelector("#overview-field"),
    sort: document.querySelector("#overview-sort"),
    reset: document.querySelector("#overview-reset"),
    count: document.querySelector("#overview-count"),
    loading: document.querySelector("#overview-loading"),
    error: document.querySelector("#overview-error"),
    empty: document.querySelector("#overview-empty"),
    outside: document.querySelector("#overview-outside"),
    rows: document.querySelector("#overview-rows"),
    previous: document.querySelector("#page-previous"),
    next: document.querySelector("#page-next"),
    pageState: document.querySelector("#page-state"),
    filters: document.querySelector("#overview-filters"),
  };

  /* Set while a restored row still has to receive focus, so returning from the detail screen
   * lands the keyboard exactly where it left. Re-rendering detaches the link, so the focus
   * is re-applied until the curator moves it somewhere themselves. */
  let focusWanted = null;

  function rowHref(row) {
    const back = controller.urlQuery();
    back.set("manifest", row.key.manifest);
    back.set("rad", row.key.entry);
    const target = new URLSearchParams();
    target.set("dataset", "sample");
    target.set("manifest", row.key.manifest);
    target.set("entry", row.key.entry);
    target.set("retur", back.toString());
    return `curate.html?${target.toString()}`;
  }

  /* A changed source selection is work like any other, and the row says which way it went
   * rather than only that something moved. */
  function evidenceNote(value) {
    if (value.evidence_added && value.evidence_removed) return "byttet kildebelegg";
    if (value.evidence_added) {
      return value.evidence_added === 1 ? "lagt til kildebelegg" : `lagt til ${value.evidence_added} kildebelegg`;
    }
    if (value.evidence_removed) {
      return value.evidence_removed === 1 ? "fjernet kildebelegg" : `fjernet ${value.evidence_removed} kildebelegg`;
    }
    return "endret kildebelegg";
  }

  /* What the draft says about a field that the approved state does not. The value may be
   * identical: a changed assessment or a changed reason is a draft change too, and the
   * curator has to be able to see it from the overview. */
  function draftNote(field, value) {
    const parts = [];
    if (value.value_changed || value.accepted_assessment === null) {
      parts.push(curatorFieldText(field, value.draft));
    } else {
      parts.push("samme verdi");
    }
    if (value.assessment_changed) {
      parts.push(`vurdert som «${ASSESSMENT_LABELS[value.draft_assessment] ?? value.draft_assessment}»`);
    }
    if (value.reason_changed) parts.push("endret begrunnelse");
    if (value.evidence_changed) parts.push(evidenceNote(value));
    return `Kladd: ${parts.join(", ")}`;
  }

  function valueCell(row, field) {
    const cell = overviewElement("td");
    cell.dataset.label = OVERVIEW_COLUMN_LABELS[field];
    const value = row.values[field];
    if (row.has_accepted) {
      const accepted = overviewElement("span", null, curatorFieldText(field, value.accepted));
      cell.append(accepted);
      /* An approved value that is itself unresolved says so, so «Uavklart» in the approved
       * state is never read as a settled answer. */
      if (value.accepted_assessment === "unresolved") {
        cell.append(overviewElement("span", "row-open", `Godkjent som «${ASSESSMENT_LABELS.unresolved}»`));
      }
    } else {
      cell.append(overviewElement("span", "row-unaccepted", "Ingen godkjent verdi ennå"));
    }
    /* A changed draft is labelled as a draft. It is never shown as the approved value, and
     * a draft that sets a field to «Belagt» is not a new approved assessment. */
    if (value.differs) {
      cell.append(overviewElement("span", "row-draft", draftNote(field, value)));
    }
    return cell;
  }

  function resolutionCell(row) {
    const cell = overviewElement("td");
    cell.dataset.label = OVERVIEW_COLUMN_LABELS.resolution;
    if (row.fully_resolved) {
      cell.append(overviewElement("span", "row-resolved", "Fullstendig avklart"));
    } else if (!row.has_accepted) {
      cell.append(overviewElement("span", "row-open", "Ingen godkjent verdi ennå"));
    } else if (row.open_fields.length) {
      const count = row.open_fields.length === 1 ? "1 uavklart felt" : `${row.open_fields.length} uavklarte felt`;
      cell.append(overviewElement("span", "row-open", `${count} i kladden: ${overviewFieldList(row.open_fields)}`));
    } else if (!row.accepted_open_fields.length && !row.review_required_fields.length && !row.draft_changed_fields.length) {
      cell.append(overviewElement("span", "row-open", "Ingen uavklarte felt"));
    }
    /* Fields the approved state leaves unresolved, even where the draft has already moved
     * on. They are still open until someone approves the draft. */
    const acceptedOnly = row.accepted_open_fields.filter(field => !row.open_fields.includes(field));
    if (row.has_accepted && acceptedOnly.length) {
      cell.append(overviewElement("span", "row-open", `Uavklart i godkjent verdi: ${overviewFieldList(acceptedOnly)}`));
    }
    if (row.review_required_fields.length) {
      cell.append(overviewElement("span", "row-review", `Trenger ny kontroll: ${overviewFieldList(row.review_required_fields)}`));
    }
    if (row.has_accepted && row.draft_changed_fields.length) {
      cell.append(overviewElement("span", "row-draft",
        `Kladd venter på godkjenning: ${overviewFieldList(row.draft_changed_fields)}`));
    }
    return cell;
  }

  function statusCell(row) {
    const cell = overviewElement("td", "row-status");
    cell.dataset.label = OVERVIEW_COLUMN_LABELS.status;
    cell.append(overviewElement("span", null,
      `${QUEUE_STATE_MARKS[row.queue_state] ?? "·"} ${QUEUE_STATE_LABELS[row.queue_state] ?? row.queue_state}`));
    cell.append(overviewElement("span", "row-source",
      row.identification_status ? IDENTIFICATION_LABELS[row.identification_status] : "Uten akseptert identitet"));
    return cell;
  }

  function renderRow(row, state) {
    const node = document.createElement("tr");
    const focused = Boolean(state.focusKey)
      && state.focusKey.manifest === row.key.manifest
      && state.focusKey.entry === row.key.entry;
    if (focused) node.setAttribute("aria-current", "true");

    const name = overviewElement("td");
    name.dataset.label = OVERVIEW_COLUMN_LABELS.title;
    const link = overviewElement("a", null, row.title);
    link.href = rowHref(row);
    name.append(link);
    if (focused && state.outsideFilter) {
      name.append(overviewElement("span", "row-outside", "Passer ikke lenger til filteret"));
    }

    const source = overviewElement("td");
    source.dataset.label = OVERVIEW_COLUMN_LABELS.source;
    source.append(overviewElement("span", "row-entry", row.key.entry));
    source.append(overviewElement("span", "row-source", row.manifest_label));

    node.append(name, source, valueCell(row, "version"), valueCell(row, "content_kind"),
      valueCell(row, "distribution_kind"), statusCell(row), resolutionCell(row));
    if (focused) focusWanted = link;
    return node;
  }

  function syncUrl(state) {
    const query = overviewStateToQuery(state).toString();
    const target = query ? `overview.html?${query}` : "overview.html";
    window.history.replaceState(null, "", target);
  }

  function render(state) {
    if (nodes.search.value !== state.input) nodes.search.value = state.input;
    nodes.status.value = state.status;
    nodes.field.value = state.field;
    nodes.sort.value = state.sort;

    nodes.loading.hidden = !state.loading;
    nodes.error.hidden = !state.error;
    if (state.error) nodes.error.textContent = state.error.message;
    nodes.empty.hidden = !(state.ready && !state.loading && !state.error && state.items.length === 0);

    nodes.outside.hidden = !state.outsideFilter;
    if (state.outsideFilter) {
      nodes.outside.textContent = `«${state.outsideFilter.title}» passer ikke lenger til det aktive filteret etter beslutningen. Raden står igjen der du forlot den.`;
    }

    nodes.count.textContent = state.ready
      ? `${state.matched.toLocaleString("nb-NO")} treff av ${state.total.toLocaleString("nb-NO")} oppføringer · viser ${state.items.length}`
      : "";
    nodes.pageState.textContent = state.ready ? `Side ${state.page} av ${state.pageCount}` : "";
    nodes.previous.disabled = state.page <= 1;
    nodes.next.disabled = state.page >= state.pageCount;

    focusWanted = null;
    nodes.rows.replaceChildren(...state.items.map(row => renderRow(row, state)));
    /* Only when nothing else holds the keyboard: a curator who has already moved on keeps
     * their place. */
    const idle = !document.activeElement || document.activeElement === document.body;
    if (focusWanted && idle) focusWanted.focus();
    syncUrl(state);
  }

  nodes.search.addEventListener("input", () => controller.setInput(nodes.search.value));
  nodes.filters.addEventListener("submit", event => { event.preventDefault(); controller.searchNow(); });
  nodes.status.addEventListener("change", () => controller.setStatus(nodes.status.value));
  nodes.field.addEventListener("change", () => controller.setField(nodes.field.value));
  nodes.sort.addEventListener("change", () => controller.setSort(nodes.sort.value));
  nodes.reset.addEventListener("click", () => {
    controller.reset();
    nodes.search.focus();
  });
  nodes.previous.addEventListener("click", () => controller.setPage(controller.state.page - 1));
  nodes.next.addEventListener("click", () => controller.setPage(controller.state.page + 1));

  controller.subscribe(render);
  const initial = overviewStateFromQuery(new URLSearchParams(window.location.search));
  return controller.start(initial).catch(error => {
    nodes.fatal.hidden = false;
    nodes.fatal.textContent = `Kunne ikke laste oversikten: ${error.message}`;
  });
}

if (typeof document !== "undefined" && document.querySelector("#overview-rows")) {
  bootstrapOverview();
}
