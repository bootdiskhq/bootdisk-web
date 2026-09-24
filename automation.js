/* Page binding for the automatic first-pass queue. Everything from a source document is put
 * on the page with textContent; nothing is parsed as HTML. The page reads; there is no button
 * here that approves, saves or undoes anything, because the contract has no such operation. */
const AUTOMATION_STAGE_TEXT = {
  needs_review: {
    label: "Trenger din vurdering",
    help: "Maskinen har forsøkt og kan ikke avgjøre dette uten et menneske.",
  },
  inspecting: {
    label: "Undersøkes maskinelt",
    help: "Maskinen har planlagte undersøkelser igjen, også uavklarte kildekonflikter. Det er ikke oppgaver til deg, og ingenting kjører fra denne siden.",
  },
  proposals: {
    label: "Forslag klare",
    help: "Maskinen har forslag. Et forslag er ikke en godkjenning.",
  },
  protected: {
    label: "Bevarte vurderinger",
    help: "Eksisterende menneskearbeid er skjermet. Maskinen foreslår ikke å endre det.",
  },
};

const AUTOMATION_STATUS_TEXT = {
  candidate: {
    label: "Forslag",
    help: "Maskinen foreslår en verdi. Den er ikke godkjent og ikke ferdig undersøkt.",
  },
  retain_unknown: {
    label: "Ikke fastslått",
    help: "Ingen verdi er fastslått, og feltet står som ukjent. Det er ikke et krav om at du skal godkjenne noe.",
  },
  inspect: {
    label: "Til maskinell undersøkelse",
    help: "Maskinen skal se nærmere på kildene før den foreslår noe.",
  },
  conflict: {
    label: "Kildene er uenige",
    help: "Kildebeleggene peker i ulike retninger. Se dem side om side nedenfor.",
  },
  preserve: {
    label: "Bevart menneskevurdering",
    help: "En tidligere menneskelig vurdering skal stå. Maskinen rører den ikke.",
  },
};

const AUTOMATION_FIELD_TEXT = {
  identity: "Identitet",
  version: "Versjon",
  content_kind: "Innholdstype",
  distribution_kind: "Utgave",
  description: "Beskrivelse",
};

function aqElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function aqCount(value, one, many) {
  return `${value.toLocaleString("nb-NO")} ${value === 1 ? one : many}`;
}

function aqFieldList(fields) {
  return fields.map(field => AUTOMATION_FIELD_TEXT[field].toLocaleLowerCase("nb-NO")).join(", ");
}

/* How the CD is named in a row: its place in the loaded set, with the start of its digest
 * for anyone who needs to tell two apart. The full digest is in the technical details. */
function aqSourceText(entry, model) {
  const digest = entry.key.manifest.replace(/^sha256:/, "").slice(0, 8);
  return `Kildepost ${entry.key.entry} · CD ${entry.manifest_ordinal} av ${model.snapshots.length} (${digest})`;
}

/* Text of a proposed value. null is never shown as "null" and never as a deletion. */
function aqProposedText(field) {
  if (field.proposed === null) return null;
  if (typeof field.proposed === "string") {
    if (field.field === "content_kind" || field.field === "distribution_kind") {
      const label = typeof curatorFieldText === "function" ? curatorFieldText(field.field, field.proposed) : field.proposed;
      return label === field.proposed ? label : `${label} (${field.proposed})`;
    }
    return field.proposed;
  }
  return JSON.stringify(field.proposed);
}

function aqVerbatim(text) {
  /* <pre> keeps spaces and line breaks exactly as written in the source. */
  return aqElement("pre", "aq-verbatim", text);
}

function aqEvidenceValue(item) {
  if (item.shape === "text") return aqVerbatim(item.value);
  if (item.shape === "list") {
    const list = aqElement("ul", "aq-evidence-values");
    for (const part of item.value) {
      const li = aqElement("li");
      li.append(aqVerbatim(part));
      list.append(li);
    }
    return list;
  }
  const wrap = aqElement("div");
  wrap.append(aqElement("p", "aq-muted", "Uventet verditype, vist som tekst:"));
  wrap.append(aqVerbatim(JSON.stringify(item.value)));
  return wrap;
}

function aqTechnical(pairs, summaryText = "Tekniske kildedetaljer") {
  const details = aqElement("details", "aq-technical");
  details.append(aqElement("summary", null, summaryText));
  const list = aqElement("dl");
  for (const [term, value] of pairs) {
    list.append(aqElement("dt", null, term), aqElement("dd", null, value));
  }
  details.append(list);
  return details;
}

function aqEvidenceList(evidence) {
  if (!evidence.length) return aqElement("p", "aq-muted", "Ingen kildebelegg er oppgitt.");
  const list = aqElement("ol", evidence.length > 1 ? "aq-evidence aq-evidence-many" : "aq-evidence");
  for (const item of evidence) {
    const li = aqElement("li", "aq-evidence-item");
    li.append(aqElement("p", "aq-evidence-label", item.label));
    li.append(aqEvidenceValue(item));
    li.append(aqTechnical([
      ["Manifest", item.source_ref.manifest],
      ["Kildepost", item.source_ref.entry],
      ["JSON-peker", item.source_ref.pointer || "(hele posten)"],
    ]));
    list.append(li);
  }
  return list;
}

function bootstrapAutomationQueue() {
  const $ = selector => document.querySelector(selector);
  const nodes = {
    banner: $("#aq-sample-banner"),
    bannerText: $("#aq-sample-text"),
    source: $("#aq-source"),
    sourceText: $("#aq-source-text"),
    file: $("#aq-file"),
    fileInput: $("#aq-file-input"),
    loading: $("#aq-loading"),
    error: $("#aq-error"),
    errorTitle: $("#aq-error-title"),
    errorText: $("#aq-error-text"),
    queue: $("#aq-queue"),
    summary: $("#aq-summary"),
    stages: $("#aq-stages"),
    humanNote: $("#aq-human-note"),
    unknown: $("#aq-unknown"),
    legend: $("#aq-legend"),
    listView: $("#aq-list-view"),
    filters: $("#aq-filters"),
    search: $("#aq-search"),
    stage: $("#aq-stage"),
    field: $("#aq-field"),
    status: $("#aq-status"),
    sort: $("#aq-sort"),
    reset: $("#aq-reset"),
    resultsTitle: $("#aq-results-title"),
    count: $("#aq-count"),
    empty: $("#aq-empty"),
    missing: $("#aq-missing"),
    list: $("#aq-list"),
    previous: $("#aq-previous"),
    next: $("#aq-next"),
    page: $("#aq-page"),
    panel: $("#aq-panel"),
    panelTitle: $("#aq-panel-title"),
    panelBody: $("#aq-panel-body"),
    close: $("#aq-close"),
    closeBottom: $("#aq-close-bottom"),
  };

  const initial = automationStateFromQuery(new URLSearchParams(window.location.search));
  const state = { ...initial };
  let model = null;
  let result = null;
  /* Set while the panel was opened from this page, so closing goes back one history step
   * and the browser's own back button does the same thing. */
  let pushedPanel = false;
  /* True once the address bar asked for sample data, whatever the loaded file says. */
  let sampleChosen = false;

  function fillSelect(select, options) {
    select.replaceChildren(...options.map(([value, label]) => {
      const option = aqElement("option", null, label);
      option.value = value;
      return option;
    }));
  }
  fillSelect(nodes.stage, [["all", "Alle innganger"], ...AUTOMATION_STAGES.map(stage => [stage, AUTOMATION_STAGE_TEXT[stage].label])]);
  fillSelect(nodes.field, [["all", "Alle felt"], ...AUTOMATION_FIELDS.map(field => [field, AUTOMATION_FIELD_TEXT[field]])]);
  fillSelect(nodes.status, [["all", "Alle feltstatuser"], ...AUTOMATION_STATUSES.map(status => [status, AUTOMATION_STATUS_TEXT[status].label])]);
  nodes.legend.replaceChildren(...AUTOMATION_STATUSES.flatMap(status => [
    aqElement("dt", `aq-status aq-status-${status}`, AUTOMATION_STATUS_TEXT[status].label),
    aqElement("dd", null, AUTOMATION_STATUS_TEXT[status].help),
  ]));

  function syncUrl(push) {
    const query = automationStateToQuery(state).toString();
    const target = query ? `automation.html?${query}` : "automation.html";
    if (push) window.history.pushState({ aqPanel: true }, "", target);
    else window.history.replaceState(window.history.state, "", target);
  }

  function showOnly(which) {
    nodes.loading.hidden = which !== "loading";
    nodes.error.hidden = which !== "error";
    nodes.queue.hidden = which !== "queue";
    nodes.source.hidden = which !== "source";
  }

  const ERROR_TITLES = {
    missing: "Fant ikke køfilen",
    invalid_json: "Køfilen er ikke gyldig JSON",
    mixed_fixture: "Prøvedata og ekte køfiler er blandet",
    invalid_schema: "Køfilen følger ikke kontrakten",
    unknown_value: "Køfilen har en ukjent verdi",
    no_source: "Ukjent datakilde",
  };

  function showError(error) {
    showOnly("error");
    const kind = error?.kind ?? "unexpected";
    nodes.error.dataset.kind = kind;
    nodes.errorTitle.textContent = ERROR_TITLES[kind] ?? "Køen kunne ikke leses";
    nodes.errorText.textContent = error?.message ?? String(error);
  }

  /* ---- Summary: the four ways in, and what they do not mean ---- */
  function renderSummary() {
    const summary = model.summary;
    nodes.stages.replaceChildren(...AUTOMATION_STAGES.map(stage => {
      const count = summary.stage_counts[stage];
      const item = aqElement("li", `aq-stage aq-stage-${stage}`);
      item.dataset.stage = stage;
      const button = aqElement("button", "aq-stage-button");
      button.type = "button";
      button.dataset.stage = stage;
      button.setAttribute("aria-pressed", String(state.stage === stage));
      button.append(aqElement("span", "aq-stage-count", count.toLocaleString("nb-NO")),
        aqElement("span", "aq-stage-label", AUTOMATION_STAGE_TEXT[stage].label));
      button.addEventListener("click", () => setFilters({ stage: state.stage === stage ? "all" : stage }));
      item.append(button, aqElement("p", "aq-stage-help", AUTOMATION_STAGE_TEXT[stage].help));
      return item;
    }));

    /* An empty human queue is not a finished catalogue while the machine still has work. */
    const humans = summary.human_exceptions;
    const machineEntries = summary.stage_counts.inspecting;
    const parts = [];
    if (humans === 0) parts.push("Ingen poster trenger din vurdering nå.");
    else parts.push(`${aqCount(humans, "post trenger", "poster trenger")} din vurdering.`);
    if (summary.machine_tasks > 0) {
      parts.push(`Maskinen har fortsatt ${aqCount(summary.machine_tasks, "planlagt undersøkelse", "planlagte undersøkelser")} i ${aqCount(machineEntries, "post", "poster")}, så ${humans === 0 ? "det betyr ikke at programmene er ferdig kuratert" : "køen er ikke ferdig"}.`);
    }
    parts.push(`${aqCount(summary.stage_counts.proposals, "post har", "poster har")} bare forslag; ingen forslag er godkjent (${summary.automatic_decisions} automatiske og ${summary.human_decisions} menneskelige beslutninger i denne kjøringen).`);
    nodes.humanNote.textContent = parts.join(" ");

    const unknown = automationUnknownByField(model.entries);
    const listed = AUTOMATION_FIELDS.filter(field => unknown[field] > 0)
      .map(field => `${AUTOMATION_FIELD_TEXT[field].toLocaleLowerCase("nb-NO")} i ${aqCount(unknown[field], "post", "poster")}`);
    nodes.unknown.textContent = listed.length
      ? `Fortsatt ukjent: ${listed.join(", ")}. Ukjent er ikke en oppgave til deg; det betyr bare at ingen verdi er fastslått.`
      : "Ingen felt står som ukjente.";
  }

  /* ---- The list ---- */
  function fieldLine(entry) {
    const groups = new Map();
    for (const field of entry.fields) {
      if (!groups.has(field.status)) groups.set(field.status, []);
      groups.get(field.status).push(field.field);
    }
    const line = aqElement("p", "aq-row-fields");
    for (const status of AUTOMATION_STATUSES) {
      if (!groups.has(status)) continue;
      const part = aqElement("span", `aq-status aq-status-${status}`,
        `${AUTOMATION_STATUS_TEXT[status].label}: ${aqFieldList(groups.get(status))}`);
      line.append(part);
    }
    return line;
  }

  function renderRow(entry) {
    const item = aqElement("li", `aq-row aq-row-${entry.stage}`);
    item.dataset.manifest = entry.key.manifest;
    item.dataset.entry = entry.key.entry;
    const button = aqElement("button", "aq-open", entry.title);
    button.type = "button";
    button.dataset.id = entry.id;
    button.setAttribute("aria-describedby", `aq-row-${entry.manifest_ordinal}-${entry.key.entry}`);
    button.addEventListener("click", () => openEntry(entry.key));
    const meta = aqElement("div", "aq-row-meta");
    meta.id = `aq-row-${entry.manifest_ordinal}-${entry.key.entry}`;
    meta.append(aqElement("p", "aq-row-source", aqSourceText(entry, model)));
    const stage = aqElement("p", `aq-row-stage aq-stage-text-${entry.stage}`, AUTOMATION_STAGE_TEXT[entry.stage].label);
    meta.append(stage);
    meta.append(fieldLine(entry));
    if (entry.tasks.length) {
      meta.append(aqElement("p", "aq-row-tasks", `${aqCount(entry.tasks.length, "planlagt maskinoppgave", "planlagte maskinoppgaver")} – ikke oppgaver til deg`));
    }
    item.append(button, meta);
    return item;
  }

  function renderList() {
    result = automationQuery(model, state);
    Object.assign(state, result.filters);
    if (nodes.search.value !== state.query) nodes.search.value = state.query;
    nodes.stage.value = state.stage;
    nodes.field.value = state.field;
    nodes.status.value = state.status;
    nodes.sort.value = state.sort;
    for (const button of nodes.stages.querySelectorAll(".aq-stage-button")) {
      button.setAttribute("aria-pressed", String(button.dataset.stage === state.stage));
    }

    const humansHere = result.humanMatched;
    nodes.count.textContent = `${model.fixture || sampleChosen ? "Prøvedata · " : ""}${result.matched.toLocaleString("nb-NO")} treff av ${aqCount(result.total, "post", "poster")}`
      + ` · ${aqCount(humansHere, "trenger", "trenger")} din vurdering · viser ${result.items.length}`;
    nodes.empty.hidden = result.matched !== 0;
    if (result.matched === 0) {
      nodes.empty.textContent = result.total === 0
        ? "Køen er tom: denne kjøringen har ingen poster. Det betyr ikke at programmene er kuratert."
        : "Ingen poster passer til søket og filtrene. Tilbakestill for å se hele køen igjen.";
    }
    nodes.page.textContent = `Side ${result.page} av ${result.pageCount}`;
    nodes.previous.disabled = result.page <= 1;
    nodes.next.disabled = result.page >= result.pageCount;
    nodes.list.replaceChildren(...result.items.map(renderRow));
  }

  function focusRow(key) {
    const button = key
      ? [...nodes.list.querySelectorAll(".aq-open")].find(node => node.dataset.id === automationKeyId(key))
      : null;
    (button ?? nodes.resultsTitle).focus();
  }

  function setFilters(changes) {
    Object.assign(state, changes, { page: 1 });
    nodes.missing.hidden = true;
    renderList();
    syncUrl(false);
  }

  function setPage(page) {
    state.page = page;
    renderList();
    syncUrl(false);
    /* The new page starts at its heading, so the keyboard and a screen reader continue from
     * the top of the rows that just appeared. */
    nodes.resultsTitle.focus();
  }

  /* ---- The read-only panel ---- */
  function fieldSection(field) {
    const section = aqElement("section", `aq-field aq-field-${field.status}`);
    section.dataset.field = field.field;
    section.append(aqElement("h3", null, AUTOMATION_FIELD_TEXT[field.field]));
    const status = aqElement("p", "aq-field-status");
    status.append(aqElement("span", `aq-status aq-status-${field.status}`, AUTOMATION_STATUS_TEXT[field.status].label),
      aqElement("span", "aq-muted", ` – ${AUTOMATION_STATUS_TEXT[field.status].help}`));
    section.append(status);

    const facts = aqElement("dl", "aq-facts");
    const proposed = aqProposedText(field);
    const value = aqElement("dd", "aq-proposed");
    if (proposed === null) {
      value.append(aqElement("span", "aq-not-established", "Ikke fastslått"));
      if (field.status === "preserve") {
        value.append(aqElement("span", "aq-muted aq-block", "Menneskevurderingen står. Den bevarte verdien følger ikke med i denne køen."));
      }
    } else if (field.field === "description" && typeof field.proposed === "string") {
      value.append(aqVerbatim(proposed));
    } else {
      value.append(aqElement("span", null, proposed));
    }
    if (field.status === "candidate") value.append(aqElement("span", "aq-muted aq-block", "Forslag, ikke godkjent."));
    facts.append(aqElement("dt", null, "Maskinens forslag"), value);
    facts.append(aqElement("dt", null, "Begrunnelse"), aqElement("dd", null, field.reason));
    facts.append(aqElement("dt", null, "Regel"), aqElement("dd", "aq-rule", field.rule));
    section.append(facts);
    section.append(aqElement("h4", null, field.evidence.length > 1 ? `Kildebelegg (${field.evidence.length}, side om side)` : "Kildebelegg"));
    section.append(aqEvidenceList(field.evidence));
    return section;
  }

  function renderPanel(entry) {
    nodes.panelTitle.textContent = entry.title;
    const body = [];
    if (entry.fixture || sampleChosen) {
      body.push(aqElement("p", "aq-panel-fixture",
        "Prøvedata: denne posten er oppdiktet og er ikke et katalogfunn eller et resultat av maskinens gjennomgang."));
    }
    body.push(aqElement("p", "aq-row-source", aqSourceText(entry, model)));
    const stage = aqElement("p", `aq-panel-stage aq-stage-text-${entry.stage}`);
    stage.append(aqElement("strong", null, AUTOMATION_STAGE_TEXT[entry.stage].label),
      aqElement("span", null, ` – ${AUTOMATION_STAGE_TEXT[entry.stage].help}`));
    body.push(stage);
    body.push(aqElement("p", "aq-muted", entry.requires_human
      ? "Denne posten krever en menneskelig vurdering. Selve vurderingen gjøres ikke her: siden leser bare."
      : "Denne posten krever ingen menneskelig vurdering nå. Siden leser bare, og ingenting kan godkjennes her."));
    body.push(aqElement("p", "aq-muted", `Regelversjon: ${entry.rules_version}`));

    if (entry.tasks.length) {
      const tasks = aqElement("section", "aq-tasks");
      tasks.append(aqElement("h3", null, "Planlagte maskinoppgaver"));
      tasks.append(aqElement("p", "aq-muted", "Dette er arbeid maskinen skal gjøre, ikke spørsmål til deg. Ingen av dem kjører fra denne siden."));
      const list = aqElement("ul", "aq-task-list");
      for (const task of entry.tasks) {
        const li = aqElement("li", "aq-task");
        li.append(aqElement("p", null, `${AUTOMATION_FIELD_TEXT[task.field]}: ${task.reason}`));
        li.append(aqEvidenceList(task.evidence));
        li.append(aqTechnical([["Oppgavekode", task.code]], "Teknisk oppgavekode"));
        list.append(li);
      }
      tasks.append(list);
      body.push(tasks);
    }
    for (const field of entry.fields) body.push(fieldSection(field));
    body.push(aqTechnical([
      ["Manifest", entry.key.manifest],
      ["Kildepost", entry.key.entry],
      ["Kandidatdata (SHA-256)", entry.candidates_sha256],
      ["Regelversjon", entry.rules_version],
    ], "Tekniske detaljer for posten"));
    nodes.panelBody.replaceChildren(...body);
  }

  function showPanel(entry) {
    renderPanel(entry);
    nodes.listView.hidden = true;
    nodes.summary.hidden = true;
    nodes.panel.hidden = false;
    nodes.panelTitle.focus();
  }

  function openEntry(key) {
    const entry = automationFind(model, key);
    if (!entry) return;
    state.open = { ...key };
    syncUrl(true);
    pushedPanel = true;
    showPanel(entry);
  }

  function hidePanel() {
    const key = state.open;
    state.open = null;
    nodes.panel.hidden = true;
    nodes.panelBody.replaceChildren();
    nodes.listView.hidden = false;
    nodes.summary.hidden = false;
    focusRow(key);
  }

  function closePanel() {
    if (nodes.panel.hidden) return;
    if (pushedPanel) {
      /* popstate below does the actual closing, so the back button and this button agree. */
      pushedPanel = false;
      window.history.back();
      return;
    }
    hidePanel();
    syncUrl(false);
  }

  window.addEventListener("popstate", () => {
    if (!model) return;
    const next = automationStateFromQuery(new URLSearchParams(window.location.search));
    pushedPanel = false;
    const wasOpen = !nodes.panel.hidden;
    Object.assign(state, { query: next.query, stage: next.stage, field: next.field, status: next.status, sort: next.sort, page: next.page });
    renderList();
    const entry = next.open ? automationFind(model, next.open) : null;
    if (entry) {
      state.open = next.open;
      showPanel(entry);
    } else if (wasOpen) {
      hidePanel();
    }
  });

  nodes.close.addEventListener("click", closePanel);
  nodes.closeBottom.addEventListener("click", closePanel);
  nodes.panel.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      closePanel();
    }
  });

  nodes.search.addEventListener("input", () => setFilters({ query: nodes.search.value }));
  nodes.filters.addEventListener("submit", event => event.preventDefault());
  nodes.stage.addEventListener("change", () => setFilters({ stage: nodes.stage.value }));
  nodes.field.addEventListener("change", () => setFilters({ field: nodes.field.value }));
  nodes.status.addEventListener("change", () => setFilters({ status: nodes.status.value }));
  nodes.sort.addEventListener("change", () => setFilters({ sort: nodes.sort.value }));
  nodes.reset.addEventListener("click", () => {
    setFilters({ query: "", stage: "all", field: "all", status: "all", sort: "stage" });
    nodes.search.focus();
  });
  nodes.previous.addEventListener("click", () => setPage(state.page - 1));
  nodes.next.addEventListener("click", () => setPage(state.page + 1));

  /* ---- Loading ---- */
  function show(documents) {
    model = automationCombine(documents);
    /* The marking comes from the documents themselves, so a sample file opened through the
     * file picker is labelled exactly like the sample chosen from the address bar. */
    if (model.fixture && !sampleChosen) {
      const which = documents.length === 1 ? "Den valgte filen er merket" : "De valgte filene er merket";
      sampleBanner([`${which} som prøvedata (fixture: true). Postene er ikke katalogfunn.`, ...model.fixture_notes].join(" "));
    } else if (!model.fixture && !sampleChosen) {
      nodes.banner.hidden = true;
    }
    showOnly("queue");
    renderSummary();
    renderList();
    const wanted = state.open;
    state.open = null;
    const entry = wanted ? automationFind(model, wanted) : null;
    if (entry) {
      state.open = wanted;
      showPanel(entry);
    } else if (wanted) {
      nodes.missing.hidden = false;
      nodes.missing.textContent = `Kildeposten ${wanted.entry} finnes ikke i den innlastede køen for dette manifestet.`;
    }
    syncUrl(false);
  }

  function load(adapters) {
    showOnly("loading");
    return Promise.all(adapters.map(adapter => adapter.loadQueue()))
      .then(show)
      .catch(showError);
  }

  function sampleBanner(text) {
    sampleChosen = sampleChosen || state.source === "prove" || state.source === "syntetisk";
    nodes.banner.hidden = false;
    nodes.bannerText.textContent = text;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new AutomationQueueError("missing", `Fant ikke ${src}.`));
      document.body.append(script);
    });
  }

  const SAMPLE_NOTE = "Postene er oppdiktet og er ikke katalogfunn. «Trenger din vurdering» og «Bevarte vurderinger» er fremtidsscenarier: den første maskinleveransen lager bare forslag og undersøkelser.";

  if (state.source === "prove") {
    sampleBanner(`Kontraktens eksempelfil fra Catalog. ${SAMPLE_NOTE}`);
    return load([createAutomationFileAdapter("tests/fixtures/automation-queue-v1.json")]);
  }
  if (state.source === "syntetisk") {
    sampleBanner(`5 000 syntetiske poster på 125 CD-er, generert likt hver gang. ${SAMPLE_NOTE}`);
    showOnly("loading");
    return loadScript("automation-sample.js").then(() => load(createAutomationSampleSnapshots()
      .map((snapshot, index) => createAutomationTextAdapter(JSON.stringify(snapshot), `Prøve-CD ${index + 1}`))))
      .catch(showError);
  }
  if (state.source === "fil") {
    showOnly("source");
    nodes.sourceText.textContent = "Velg én eller flere køfiler (én per CD-manifest). Filene leses bare i nettleseren og endres ikke.";
    nodes.file.hidden = false;
    nodes.fileInput.addEventListener("change", () => {
      const files = [...nodes.fileInput.files];
      if (!files.length) return;
      Promise.all(files.map(file => file.text().then(text => createAutomationTextAdapter(text, file.name))))
        .then(load, showError);
    });
    return Promise.resolve();
  }
  if (state.source) {
    showError(new AutomationQueueError("no_source", `Datakilden «${state.source}» finnes ikke. Velg en kilde fra siden uten parametre.`));
    return Promise.resolve();
  }
  showOnly("source");
  return Promise.resolve();
}

if (typeof document !== "undefined" && document.querySelector("#aq-list")) {
  bootstrapAutomationQueue();
}
