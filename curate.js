/* Page binding for the local curator. Rendering is text-only: source observations and
 * package members are never interpreted as HTML, executable content or file links.
 * Buttons and keyboard shortcuts resolve to the same action codes in curate-core.js. */
const FIXTURE_URL = "tests/fixtures/curator-fixtures-v1.json";
/* The overview screen carries the same vocabulary in curator-labels.js, and a test keeps
 * the two blocks identical. It stays inline here because Catalog's local service serves the
 * curator from a closed allowlist; a separate file would answer 404 in real local mode. */
/* --- delt kuratorvokabular: identisk blokk i curate.js og curator-labels.js --- */
const CONTENT_KIND_LABELS = {
  application: "Program",
  game: "Spill",
  course: "Kurs",
  image_collection: "Bildesamling",
  font_collection: "Fontsamling",
  reference: "Oppslagsverk",
};
const DISTRIBUTION_LABELS = {
  full: "Full versjon",
  demo: "Demo",
  trial: "Prøveversjon",
  update: "Oppdatering",
  unknown: "Ukjent",
};
const QUEUE_STATE_LABELS = { pending: "Venter", deferred: "Utsatt", reviewed: "Gjennomgått" };
/* Status is readable without colour: the mark carries it on its own. */
const QUEUE_STATE_MARKS = { pending: "●", deferred: "‖", reviewed: "✓" };
const IDENTIFICATION_LABELS = { curated: "Kuratert identitet", interpreted: "Foreløpig identitet" };
const ASSESSMENT_LABELS = { accepted: "Belagt", unresolved: "Uavklart" };

/* The stored value of the three fields both screens show as a column and as a claim.
 * «unknown» is a stored value, not a label, and is spelled out in Norwegian here. */
function curatorFieldText(field, value) {
  if (field === "version") return value === "unknown" ? "Ikke oppgitt" : String(value ?? "");
  if (field === "content_kind") return CONTENT_KIND_LABELS[value] ?? String(value ?? "");
  if (field === "distribution_kind") return DISTRIBUTION_LABELS[value] ?? String(value ?? "");
  return String(value ?? "");
}
/* --- slutt delt kuratorvokabular --- */
const FIELD_SPECS = [
  { field: "identity", label: "Identitet og navn", control: "identity" },
  { field: "version", label: "Versjon", control: "text", help: "Bruk «Ikke oppgitt» med begrunnelse når versjonen ikke er fastslått." },
  { field: "content_kind", label: "Innholdstype", control: "select", options: CONTENT_KINDS, labels: CONTENT_KIND_LABELS },
  { field: "distribution_kind", label: "Distribusjon", control: "select", options: DISTRIBUTION_KINDS, labels: DISTRIBUTION_LABELS, help: "«Ukjent» må stå som uavklart. Freeware betyr ikke automatisk full versjon." },
  { field: "description", label: "Beskrivelse – original CD-omtale", control: "textarea" },
];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

// Keep provenance IDs intact for saving, but lead with what a person can assess.
function evidenceContent(item, index) {
  const observation = item.observation;
  const record = observation && typeof observation === "object" ? observation : {};
  const titles = {
    "normalized.title": "Tittel på CD-en",
    "normalized.categories": "Kategori på CD-en",
    "raw.Licens": "Lisens oppgitt på CD-en",
    "raw.Global": "Original omtale på CD-en",
    "normalized.description": "Omtale på CD-en",
    file_content_review: "Gjennomgang av fil",
    payload_observation: "Tekst funnet i fil",
  };
  const title = titles[item.field] ?? "Kildeobservasjon";
  const text = typeof observation === "string" ? observation
    : [record.summary, record.text].filter(value => typeof value === "string" && value.trim()).join("\n\n");
  const context = [item.source_ref?.path, record.member].filter(Boolean).join(" → ");
  return {
    title: `Kilde ${index + 1}: ${title}`,
    context: context || `CD-oppføring ${item.source_ref?.entry ?? ""}`,
    text: text || "Denne observasjonen har ikke et lesbart tekstutdrag. Tekniske detaljer alene bekrefter ikke påstanden.",
  };
}

// Merge only identical CD descriptions from the same source. Keep every stored
// ID addressable so old selections remain visible without rewriting user data.
function displayEvidence(evidence) {
  return evidence.filter(item => item.field !== "raw.Global" || !evidence.some(other =>
    other.field === "normalized.description" && other.observation === item.observation &&
    other.source_ref.manifest === item.source_ref.manifest && other.source_ref.entry === item.source_ref.entry &&
    other.source_ref.path === item.source_ref.path
  )).map(item => ({ ...item, aliases: item.field === "normalized.description" ? evidence.filter(other =>
    other.field === "raw.Global" && other.observation === item.observation &&
    other.source_ref.manifest === item.source_ref.manifest && other.source_ref.entry === item.source_ref.entry &&
    other.source_ref.path === item.source_ref.path
  ) : [] }));
}

function evidenceIds(item) {
  return [item.id, ...item.aliases.map(alias => alias.id)];
}

function evidenceDetails(item) {
  const details = element("details", "evidence-technical");
  details.append(element("summary", null, "Tekniske detaljer"));
  details.append(element("pre", null, JSON.stringify(item, null, 2)));
  return details;
}

function evidencePreview(item, index) {
  const content = evidenceContent(item, index);
  const block = element("div", "evidence-readable");
  block.append(element("strong", null, content.title), element("span", "evidence-meta", content.context));
  const limit = 280;
  block.append(element("span", "evidence-excerpt", content.text.length > limit ? `${content.text.slice(0, limit)}…` : content.text));
  if (content.text.length > limit) {
    const full = element("details", "evidence-full");
    full.append(element("summary", null, "Les hele tekstutdraget"), element("p", "evidence-excerpt", content.text));
    block.append(full);
  }
  return block;
}

/* What a claim's editable control displays, as opposed to the read-only summary text. */
function claimControlValue(field, value) {
  if (field === "version" && value === "unknown") return "Ikke oppgitt";
  if (field === "identity") return value?.name ?? "";
  if (field === "description") return value?.text ?? "";
  return value ?? "";
}

function claimValueText(field, value) {
  if (field === "identity") return `${value?.name ?? ""}${value?.software_id ? ` (${value.software_id})` : " (ny eller ukjent ID)"}`;
  if (field === "description") return value?.text ?? "";
  return curatorFieldText(field, value);
}

function returnBlockedText(state) {
  if (state.busy) return "Beslutningen er ikke bekreftet ennå. Vent til den er ferdig før du går tilbake.";
  if (state.leaving) return "Returen pågår allerede. Vent til den siste lagringen er bekreftet.";
  if (state.conflict) return "Oppføringen er endret et annet sted. Velg hvordan konflikten skal løses før du går tilbake; teksten din er beholdt.";
  return "Kladden er ikke lagret. Teksten er beholdt her; forsøk lagringen på nytt før du går tilbake til oversikten.";
}

function byteText(size) {
  return typeof size === "number" ? `${size.toLocaleString("nb-NO")} byte` : "ukjent størrelse";
}

function bootstrap(fixture, providedAdapter = null, options = {}) {
  const adapter = providedAdapter ?? createFixtureAdapter({
    fixture,
    storage: curatorBrowserStorage(),
  });
  const controller = createCuratorController({ adapter });
  if (!adapter.fixtureMode) {
    const banner = document.querySelector('#fixture-banner');
    banner.replaceChildren(element('strong', null, 'Lokal kuratering – ekte katalogdata.'),
      element('span', null, 'Kladder og beslutninger lagres på denne maskinen. Godkjenning publiserer ikke på bootdisk.no.'));
    document.querySelector('#simulate-reset').closest('details').hidden = true;
    document.querySelector('footer').lastElementChild.textContent = 'lokal kuratering · varig arbeidsområde';
    document.querySelector('.brand').href = 'curate.html?mode=local';
  }

  if (options.sampleMode) {
    /* Opened from the overview prototype: the same fixture semantics, over synthetic
     * entries that are not catalogue findings. */
    document.querySelector("#fixture-banner").append(element("span", null,
      "Syntetiske prøvedata fra oversiktsprototypen. Oppdiktede programmer, ikke katalogfunn."));
  }

  if (options.returnQuery !== undefined) bindReturnLink(options.returnQuery);

  if (!adapter.durable) {
    /* A session that cannot keep anything says so; it never implies a draft will survive
     * a reload. */
    const banner = document.querySelector("#fixture-banner");
    banner.classList.add("fixture-banner-ephemeral");
    banner.append(element("span", "ephemeral-warning",
      "Nettleserlagring er ikke tilgjengelig. Kladder og beslutninger forsvinner når siden lastes på nytt."));
  }

  const nodes = {
    notice: document.querySelector("#curate-notice"),
    fatal: document.querySelector("#curate-fatal"),
    filter: document.querySelector("#queue-filter"),
    count: document.querySelector("#queue-count"),
    summary: document.querySelector("#queue-summary"),
    list: document.querySelector("#queue-list"),
    queueEmpty: document.querySelector("#queue-empty"),
    complete: document.querySelector("#queue-complete"),
    entryView: document.querySelector("#entry-view"),
    entryId: document.querySelector("#entry-id"),
    entryQueueState: document.querySelector("#entry-queue-state"),
    entryIdentification: document.querySelector("#entry-identification"),
    heading: document.querySelector("#entry-heading"),
    saveState: document.querySelector("#save-state"),
    error: document.querySelector("#decision-error"),
    conflict: document.querySelector("#conflict-panel"),
    conflictLocal: document.querySelector("#conflict-local"),
    conflictServer: document.querySelector("#conflict-server"),
    conflictKeep: document.querySelector("#conflict-keep"),
    conflictLoad: document.querySelector("#conflict-load"),
    issues: document.querySelector("#entry-issues"),
    form: document.querySelector("#claim-form"),
    commit: document.querySelector("#action-commit"),
    deferButton: document.querySelector("#action-defer"),
    undo: document.querySelector("#action-undo"),
    retry: document.querySelector("#action-retry"),
    deferForm: document.querySelector("#defer-form"),
    deferReason: document.querySelector("#defer-reason"),
    deferError: document.querySelector("#defer-error"),
    deferCancel: document.querySelector("#defer-cancel"),
    sourceTitle: document.querySelector("#source-title"),
    sourceDescription: document.querySelector("#source-description"),
    sourceTarget: document.querySelector("#source-target"),
    memberCount: document.querySelector("#member-count"),
    members: document.querySelector("#source-members"),
    evidenceCount: document.querySelector("#evidence-count"),
    evidence: document.querySelector("#evidence-list"),
    historyCount: document.querySelector("#history-count"),
    history: document.querySelector("#history-list"),
    shortcuts: document.querySelector("#shortcut-list"),
    simulateFault: document.querySelector("#simulate-fault"),
    simulateMedia: document.querySelector("#simulate-media"),
    simulateReset: document.querySelector("#simulate-reset"),
  };

  /* Every claim control is registered so a draft change made in code (using a proposal,
   * reconciling a conflict) can be reflected without rebuilding the form under the caret. */
  const claimControls = new Map();

  let renderedDraftToken = null;
  let renderedEntryId = null;
  let firstRender = true;

  for (const hint of CURATOR_SHORTCUT_HINTS) {
    const item = element("li");
    item.append(element("kbd", null, hint.keys), element("span", null, hint.label));
    nodes.shortcuts.append(item);
  }

  function renderQueue(state) {
    nodes.count.textContent = `${state.items.length} i filteret`;
    /* Reviewed is a pass through the entry; resolved is a claim with no open field. */
    nodes.summary.textContent = `${state.summary.reviewed} av ${state.summary.total} gjennomgått · ${state.summary.open_fields} har fortsatt åpne felt · ${state.summary.deferred} utsatt`;
    nodes.queueEmpty.hidden = state.items.length !== 0;
    nodes.list.replaceChildren(...state.items.map(item => {
      const selected = state.entry?.key?.entry === item.key.entry;
      const node = element("li", "queue-item");
      if (selected) node.setAttribute("aria-current", "true");
      const button = element("button");
      button.type = "button";
      const title = element("span", "queue-title", `${selected ? "▸ " : ""}${item.title}`);
      const meta = element("span", "queue-meta", [
        `${QUEUE_STATE_MARKS[item.queue_state] ?? "·"} ${QUEUE_STATE_LABELS[item.queue_state] ?? item.queue_state}`,
        item.identification_status ? IDENTIFICATION_LABELS[item.identification_status] : "Uten identitet",
        item.open_fields.length === 1 ? "1 åpent felt" : `${item.open_fields.length} åpne felt`,
      ].join(" · "));
      button.append(element("span", "queue-entry", item.key.entry), title, meta);
      if (selected) button.setAttribute("aria-describedby", "queue-count");
      button.addEventListener("click", () => controller.select(item.key));
      node.append(button);
      return node;
    }));
  }

  function renderClaimField(spec, state) {
    const claim = state.draft.claims[spec.field];
    const wrapper = element("section", "claim-field");
    const controlId = `claim-${spec.field}`;
    wrapper.append(element("h3", null, spec.label));

    const accepted = state.entry.accepted?.claims?.[spec.field];
    const acceptedLine = element("p", "claim-accepted");
    acceptedLine.append(element("span", null, "Akseptert nå: "));
    acceptedLine.append(element("strong", null, accepted ? claimValueText(spec.field, accepted.value) : "ingen akseptert verdi"));
    const needsReview = state.entry.issues.some(issue => issue.field === spec.field && issue.code === "classification_review_required");
    if (accepted) acceptedLine.append(element("span", null, ` — ${needsReview ? "Tidligere belagt · må kontrolleres" : (ASSESSMENT_LABELS[accepted.assessment] ?? accepted.assessment)}`));
    wrapper.append(acceptedLine);

    const label = element("label", null, spec.label);
    label.htmlFor = controlId;
    wrapper.append(label);

    let control;
    if (spec.control === "select") {
      control = element("select");
      for (const option of spec.options) {
        const node = element("option", null, spec.labels[option] ?? option);
        node.value = option;
        control.append(node);
      }
      control.value = claim.value;
      control.addEventListener("change", () => controller.editClaim(spec.field, { value: control.value }));
    } else if (spec.control === "textarea") {
      control = element("textarea");
      control.rows = 4;
      control.readOnly = Boolean(state.entry.original_description_v1);
      control.value = claim.value?.text ?? "";
      control.addEventListener("input", () => controller.editClaim(spec.field, { value: { language: "nb-NO", text: control.value } }));
    } else if (spec.control === "identity") {
      control = element("input");
      control.type = "text";
      control.value = claim.value?.name ?? "";
      control.addEventListener("input", () => {
        const unchanged = control.value === state.entry.accepted?.claims?.identity?.value?.name;
        /* A renamed identity is sent as a name proposal with a null ID; the browser never
         * renames a shared catalog record implicitly. */
        controller.editClaim("identity", {
          value: { software_id: unchanged ? (state.entry.accepted?.claims?.identity?.value?.software_id ?? null) : null, name: control.value },
        });
      });
    } else {
      control = element("input");
      control.type = "text";
      control.value = claimControlValue(spec.field, claim.value);
      control.addEventListener("input", () => controller.editClaim(spec.field, {
        value: spec.field === "version" && control.value.trim().toLocaleLowerCase("nb-NO") === "ikke oppgitt"
          ? "unknown" : control.value,
      }));
    }
    control.id = controlId;
    wrapper.append(control);
    const registry = { value: control, assessment: {}, reason: null, evidence: new Map(), detail: null };
    claimControls.set(spec.field, registry);

    if (spec.field === "identity") {
      wrapper.append(element("p", "claim-accepted", claim.value?.software_id
        ? `Katalog-ID: ${claim.value.software_id}`
        : "Uten katalog-ID. Navnet sendes som forslag; tjenesten avgjør identiteten."));
    }
    if (spec.field === "description" && state.entry.original_description_v1) wrapper.append(element("p", "claim-accepted", "Gjengitt ordrett fra CD-en. Skriv egne vurderinger i begrunnelsen; originalteksten beholdes."));
    if (spec.help) wrapper.append(element("p", "claim-accepted", spec.help));

    const assessment = element("fieldset", "assessment-group");
    assessment.append(element("legend", null, "Vurdering"));
    for (const value of ["accepted", "unresolved"]) {
      const option = element("span", "assessment-option");
      const input = element("input");
      input.type = "radio";
      input.name = `assessment-${spec.field}`;
      input.id = `assessment-${spec.field}-${value}`;
      input.value = value;
      input.checked = claim.assessment === value;
      registry.assessment[value] = input;
      input.addEventListener("change", () => {
        if (input.checked) controller.editClaim(spec.field, { assessment: value });
      });
      const optionLabel = element("label", null, ASSESSMENT_LABELS[value]);
      optionLabel.htmlFor = input.id;
      option.append(input, optionLabel);
      assessment.append(option);
    }
    wrapper.append(assessment);

    const detail = element("details", "claim-detail");
    detail.open = needsReview || claim.assessment === "unresolved" || Boolean(String(claim.reason ?? "").trim());
    detail.append(element("summary", null, "Begrunnelse og kildebelegg"));
    const detailBody = element("div");

    const reasonId = `reason-${spec.field}`;
    const reasonLabel = element("label", null, "Begrunnelse");
    reasonLabel.htmlFor = reasonId;
    const reason = element("textarea");
    reason.id = reasonId;
    reason.rows = 2;
    reason.value = claim.reason ?? "";
    reason.addEventListener("input", () => controller.editClaim(spec.field, { reason: reason.value }));
    registry.reason = reason;
    registry.detail = detail;
    detailBody.append(reasonLabel, reason);

    if (state.entry.evidence.length) {
      const evidenceGroup = element("fieldset", "evidence-choice");
      evidenceGroup.append(element("legend", null, "Hvilke kilder støtter vurderingen din?"));
      evidenceGroup.append(element("p", "evidence-meta", "Avhuking knytter kilden til dette feltet. Den endrer ikke verdien eller gjør vurderingen automatisk belagt."));
      if (spec.field === "content_kind" || spec.field === "distribution_kind") {
        evidenceGroup.append(element("p", "evidence-meta", spec.field === "content_kind"
          ? "CD-kategorien er originalens ordlyd. Forklar hvordan den eller annet kildebelegg støtter innholdstypen."
          : "Freeware og Shareware er lisensopplysninger. De fastslår ikke alene om utgaven er full, demo eller prøveversjon."));
      }
      for (const [index, item] of displayEvidence(state.entry.evidence).entries()) {
        const option = element("div", "evidence-option");
        const input = element("input");
        input.type = "checkbox";
        input.id = `evidence-${spec.field}-${item.id}`;
        input.checked = evidenceIds(item).some(id => (claim.evidence_ids ?? []).includes(id));
        input.evidenceIds = evidenceIds(item);
        registry.evidence.set(item.id, input);
        input.addEventListener("change", () => {
          const current = new Set(controller.state.draft.claims[spec.field].evidence_ids ?? []);
          for (const id of evidenceIds(item)) current.delete(id);
          if (input.checked) current.add(item.id);
          controller.editClaim(spec.field, { evidence_ids: [...current] });
        });
        const optionLabel = element("label");
        optionLabel.htmlFor = input.id;
        const content = evidenceContent(item, index);
        optionLabel.textContent = content.title;
        const body = element("div");
        const preview = evidencePreview(item, index);
        preview.firstChild.remove();
        body.append(optionLabel, preview, evidenceDetails(item));
        option.append(input, body);
        evidenceGroup.append(option);
      }
      detailBody.append(evidenceGroup);
    }
    detail.append(detailBody);
    wrapper.append(detail);

    for (const proposal of state.entry.proposals.filter(item => item.field === spec.field)) {
      const box = element("p", "claim-proposal");
      box.append(element("span", null, "Forslag: "));
      box.append(element("strong", null, claimValueText(spec.field, proposal.value)));
      box.append(element("span", null, ` — ${proposal.reason}`));
      const use = element("button", null, "Bruk forslaget");
      use.type = "button";
      /* A proposal is never accepted automatically; the assessment stays the curator's. */
      use.addEventListener("click", () => {
        controller.useProposal(proposal);
        const registered = claimControls.get(spec.field);
        if (registered?.detail) registered.detail.open = true;
        registered?.value?.focus();
      });
      box.append(document.createElement("br"), use);
      wrapper.append(box);
    }

    const error = element("p", "field-error");
    error.dataset.fieldError = spec.field;
    error.hidden = true;
    wrapper.append(error);
    return wrapper;
  }

  function renderEntryDetail(state) {
    const entry = state.entry;
    nodes.entryId.textContent = entry.key.entry;
    nodes.entryQueueState.textContent = `${QUEUE_STATE_MARKS[entry.queue_state] ?? "·"} ${QUEUE_STATE_LABELS[entry.queue_state] ?? entry.queue_state}`;
    nodes.entryIdentification.textContent = entry.accepted?.identification_status
      ? IDENTIFICATION_LABELS[entry.accepted.identification_status]
      : "Uten akseptert identitet";
    nodes.heading.textContent = entry.source.title;

    nodes.sourceTitle.textContent = entry.source.title;
    nodes.sourceDescription.textContent = entry.source.description;
    nodes.sourceTarget.textContent = `${entry.source.target.kind === "package" ? "Pakke" : "Enkeltfil"}: ${entry.source.target.id}`;
    nodes.memberCount.textContent = String(entry.source.members.length);
    nodes.members.replaceChildren(...entry.source.members.map(member => {
      const node = element("li");
      node.append(element("span", "member-path", member.path));
      node.append(element("span", "member-meta", `${byteText(member.size)} · sha256 ${member.sha256}`));
      return node;
    }));

    nodes.evidenceCount.textContent = String(displayEvidence(entry.evidence).length);
    nodes.evidence.replaceChildren(...displayEvidence(entry.evidence).map((item, index) => {
      const node = element("li");
      node.append(evidencePreview(item, index), evidenceDetails(item));
      return node;
    }));

    const history = entry.history ?? [];
    let deferNote = nodes.entryView.querySelector('[data-defer-reason]');
    if (!deferNote) {
      deferNote = element('p');
      deferNote.dataset.deferReason = '';
      nodes.form.before(deferNote);
    }
    deferNote.hidden = !entry.defer_reason;
    deferNote.textContent = entry.defer_reason ? 'Utsatt: ' + entry.defer_reason : '';
    nodes.historyCount.textContent = String(history.length);
    nodes.history.replaceChildren(...history.map(event => element("li", null, [
      event.kind === "restore_description" ? "Originalomtale gjenopprettet" : event.kind === "approve" ? "Godkjent" : event.kind === "undo" ? "Angret" : "Utsatt",
      event.reason ? `– ${event.reason}` : "",
      `(${event.at})`,
    ].filter(Boolean).join(" "))));

    nodes.issues.replaceChildren(...entry.issues.map(issue => {
      const node = element("li");
      node.append(element("span", "issue-code", issue.field ? `${issue.code} · ${issue.field}` : issue.code));
      node.append(element("span", null, issue.message));
      return node;
    }));
  }

  /* The form must never show a different claim than the one that would be approved. Every
   * control is reconciled with the draft, except the one the curator is typing in. */
  function syncClaimControls(state) {
    if (!state.draft) return;
    const active = document.activeElement;
    for (const [field, registry] of claimControls) {
      const claim = state.draft.claims[field];
      if (!claim) continue;

      const shown = String(claimControlValue(field, claim.value));
      if (registry.value && registry.value !== active && registry.value.value !== shown) {
        registry.value.value = shown;
      }
      for (const [assessment, input] of Object.entries(registry.assessment)) {
        const checked = claim.assessment === assessment;
        if (input.checked !== checked) input.checked = checked;
      }
      const reason = claim.reason ?? "";
      if (registry.reason && registry.reason !== active && registry.reason.value !== reason) {
        registry.reason.value = reason;
      }
      const chosen = new Set(claim.evidence_ids ?? []);
      for (const [id, input] of registry.evidence) {
        const checked = input.evidenceIds.some(sourceId => chosen.has(sourceId));
        if (input.checked !== checked) input.checked = checked;
      }
    }
  }

  function renderStatus(state) {
    const statusText = {
      idle: state.entry?.queue_state === "reviewed" ? "Gjennomgått. Kladden er uendret." : "Ingen ulagrede endringer.",
      dirty: "Ulagrede endringer.",
      saving: "Lagrer kladd …",
      saved: "Kladd lagret. Kladd er ikke en godkjenning.",
      error: "Handlingen mislyktes. Innholdet er beholdt.",
    };
    nodes.saveState.dataset.status = state.status;
    nodes.saveState.textContent = statusText[state.status] ?? "";

    const hasError = Boolean(state.error) && !state.conflict;
    nodes.error.hidden = !hasError;
    if (hasError) {
      nodes.error.replaceChildren(element("p", null, state.error.message));
      const entries = Object.entries(state.fieldErrors ?? {});
      if (entries.length) {
        const list = element("ul");
        for (const [field, message] of entries) {
          const spec = FIELD_SPECS.find(item => item.field === field);
          list.append(element("li", null, `${spec ? spec.label : field}: ${message}`));
        }
        nodes.error.append(list);
      }
    }
    for (const node of nodes.form.querySelectorAll("[data-field-error]")) {
      const message = state.fieldErrors?.[node.dataset.fieldError];
      node.textContent = message ?? "";
      node.hidden = !message;
    }

    nodes.retry.hidden = !(state.pendingRetry && state.status === "error" && !state.conflict);

    nodes.conflict.hidden = !state.conflict;
    if (state.conflict) {
      const fill = (target, claims) => target.replaceChildren(...FIELD_SPECS.flatMap(spec => [
        element("dt", null, spec.label),
        element("dd", null, claimValueText(spec.field, claims?.[spec.field]?.value)),
      ]));
      fill(nodes.conflictLocal, state.conflict.local?.claims);
      fill(nodes.conflictServer, state.conflict.server?.draft?.claims);
    }

    nodes.commit.textContent = "";
    nodes.commit.append(element("span", null, controller.commitLabel()), element("kbd", null, "G"));
    const deciding = state.busy || Boolean(state.conflict);
    /* Decisions are also refused while a return is waiting for the last write, so the
     * buttons say the same thing the controller does. */
    const locked = deciding || state.leaving;
    nodes.commit.disabled = locked;
    nodes.deferButton.disabled = locked;
    nodes.retry.disabled = state.busy || state.leaving;
    nodes.undo.hidden = !state.entry?.undo;
    if (state.entry?.undo) {
      nodes.undo.textContent = "";
      nodes.undo.append(element("span", null, state.entry.undo.label), element("kbd", null, "Z"));
      nodes.undo.disabled = locked;
    }
    /* Editing is disabled during the short approve/defer/undo operation. Typing stays open
     * while a return waits: the text is either saved by the flush or it stops the return. */
    for (const control of nodes.form.querySelectorAll("input, select, textarea, button")) {
      control.disabled = deciding;
    }

    nodes.notice.hidden = !state.notice;
    if (state.notice) nodes.notice.textContent = state.notice;

    if (adapter.simulation) {
      nodes.simulateFault.value = adapter.simulation.armed() ?? "";
      nodes.simulateMedia.value = state.entry ? (adapter.simulation.overlays()[state.entry.key.entry] ?? "") : "";
    }
  }

  function render(state) {
    nodes.filter.value = state.filter;
    renderQueue(state);
    nodes.complete.hidden = !state.complete;
    nodes.entryView.hidden = !state.entry;
    if (!state.entry) return;

    if (state.draftToken !== renderedDraftToken) {
      renderedDraftToken = state.draftToken;
      renderEntryDetail(state);
      claimControls.clear();
      nodes.form.replaceChildren(...FIELD_SPECS.map(spec => renderClaimField(spec, state)));
      nodes.deferForm.hidden = true;
      nodes.deferReason.value = "";
      if (!firstRender && state.entry.key.entry !== renderedEntryId) {
        /* Focus moves predictably to the new entry; a failure keeps focus where it was. */
        nodes.heading.focus();
      }
      renderedEntryId = state.entry.key.entry;
      firstRender = false;
    } else {
      renderEntryDetail(state);
      syncClaimControls(state);
    }
    renderStatus(state);
  }

  /* Going back to the overview passes the same gate as opening another entry: the draft is
   * flushed and the page is left only once the write is confirmed. A plain href would
   * navigate away mid-autosave, during a failed write, a conflict or a running decision,
   * and the text would be gone. */
  function bindReturnLink(query) {
    const node = document.querySelector("#curate-return");
    const link = document.querySelector("#curate-return-link");
    const message = document.querySelector("#curate-return-error");
    link.href = query ? `overview.html?${query}` : "overview.html";
    link.addEventListener("click", event => {
      /* A modified or middle click opens a second tab and leaves this page, and its draft,
       * exactly as they are. */
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      message.hidden = true;
      /* The navigation itself is handed to the controller, which runs it inside its own
       * gate: the entry cannot become unsettled between the check and the page going. */
      controller.leave(() => window.location.assign(link.href)).then(safe => {
        if (safe) return;
        message.textContent = returnBlockedText(controller.state);
        message.hidden = false;
        link.focus();
      });
    });
    node.hidden = false;
  }

  function openDeferForm() {
    if (nodes.deferButton.disabled) return;
    nodes.deferForm.hidden = false;
    nodes.deferError.hidden = true;
    nodes.deferReason.focus();
  }

  function submitDefer(event) {
    event.preventDefault();
    const reason = nodes.deferReason.value.trim();
    if (!reason) {
      nodes.deferError.textContent = "Skriv hvorfor oppføringen hoppes over.";
      nodes.deferError.hidden = false;
      nodes.deferReason.focus();
      return;
    }
    nodes.deferError.hidden = true;
    controller.dispatch("defer", reason).catch(() => { /* Reported through state.error. */ });
  }

  function runAction(action) {
    if (action === "defer") {
      openDeferForm();
      return;
    }
    if (action === "focus-fields") {
      nodes.form.querySelector("input, select, textarea")?.focus();
      return;
    }
    if (action === "shortcuts") {
      document.querySelector("#shortcut-list").hidden = !document.querySelector("#shortcut-list").hidden;
      return;
    }
    controller.dispatch(action).catch(() => { /* Reported through state.error. */ });
  }

  nodes.filter.addEventListener("change", () => controller.setFilter(nodes.filter.value));
  nodes.commit.addEventListener("click", () => runAction("commit"));
  nodes.deferButton.addEventListener("click", () => runAction("defer"));
  nodes.undo.addEventListener("click", () => runAction("undo"));
  nodes.retry.addEventListener("click", () => runAction("retry"));
  nodes.deferForm.addEventListener("submit", submitDefer);
  nodes.deferCancel.addEventListener("click", () => { nodes.deferForm.hidden = true; nodes.deferButton.focus(); });
  nodes.conflictKeep.addEventListener("click", () => controller.resolveConflict("keep_local"));
  nodes.conflictLoad.addEventListener("click", () => controller.resolveConflict("load_server"));

  nodes.simulateFault.addEventListener("change", () => {
    adapter.simulation.clear();
    if (nodes.simulateFault.value) adapter.simulation.arm(nodes.simulateFault.value);
  });
  nodes.simulateMedia.addEventListener("change", () => {
    if (!controller.state.entry) return;
    adapter.simulation.setOverlay(controller.state.entry.key.entry, nodes.simulateMedia.value || null);
    controller.openEntry(controller.state.entry.key, { bookmark: false });
  });
  nodes.simulateReset.addEventListener("click", () => {
    adapter.reset();
    renderedDraftToken = null;
    renderedEntryId = null;
    controller.start();
  });

  document.addEventListener("keydown", event => {
    const action = curatorActionForEvent(event);
    if (!action) return;
    if (!controller.state.entry && action !== "shortcuts") return;
    event.preventDefault();
    runAction(action);
  });

  controller.subscribe(render);
  /* An entry handed over from the overview is opened on its full identity: manifest and
   * entry together, because a K-id alone is not unique across source manifests. */
  return controller.start()
    .then(() => (options.openKey ? controller.select(options.openKey) : null))
    .catch(error => {
      nodes.fatal.hidden = false;
      nodes.fatal.textContent = `Kunne ikke starte kurateringsskjermen: ${error.message}`;
    });
}

/* Browser storage for the fixture adapters, or null when the origin refuses it. */
function curatorBrowserStorage() {
  try {
    window.localStorage.setItem("curator-probe", "1");
    window.localStorage.removeItem("curator-probe");
    return window.localStorage;
  } catch (error) {
    return null;
  }
}

/* The overview prototype's own files are fetched here and nowhere else. curate.html keeps
 * to the files Catalog's local service serves from its closed allowlist (`STATIC` in
 * `bootdisk_catalog/service.py`), so a prototype dependency can never be a script tag on
 * the page: it would answer 404 in real local mode and stop curation before it starts.
 * Sample mode only ever runs off the prototype's own static server, which serves them. */
function loadPrototypeScripts() {
  return Promise.all(["curator-navigation.js", "overview-sample.js"].map(name => new Promise((resolve, reject) => {
    const node = document.createElement("script");
    node.src = name;
    node.addEventListener("load", () => resolve(name));
    node.addEventListener("error", () => reject(new Error(`Fant ikke ${name}. Oversikten må serveres fra reporoten.`)));
    document.head.append(node);
  })));
}

/* The synthetic dataset of the overview prototype, opened on one source manifest. It reuses
 * this screen unchanged: same adapter, same decisions, same simulations. */
function startSampleCuration(params) {
  const manifest = params.get("manifest");
  const entry = params.get("entry");
  const adapter = createFixtureAdapter({
    fixture: createSampleBundle(manifest),
    datasetId: sampleDatasetId(manifest),
    storage: curatorBrowserStorage(),
  });
  return bootstrap(null, adapter, {
    sampleMode: true,
    openKey: entry ? { manifest: adapter.manifest, entry } : null,
    returnQuery: overviewSafeReturnQuery(params.get("retur")),
  });
}

/* Three ways in, one screen: the real local service, the overview prototype's synthetic
 * dataset, and Catalog's own reference fixtures. */
function startCuration(params) {
  if (params.get('mode') === 'local') {
    document.querySelector('#fixture-banner').textContent = 'Lokal kuratering – kobler til arbeidsområdet …';
    return createLiveAdapter().then(adapter => bootstrap(null, adapter));
  }
  if (params.get('dataset') === 'sample') return loadPrototypeScripts().then(() => startSampleCuration(params));
  return fetch(FIXTURE_URL).then(response => {
    if (!response.ok) throw new Error(`Fant ikke prøvedataene (${response.status}).`);
    return response.json();
  }).then(fixture => bootstrap(fixture));
}

if (typeof document !== "undefined") {
  Promise.resolve()
    .then(() => startCuration(new URLSearchParams(window.location.search)))
    .catch(error => {
      const fatal = document.querySelector('#curate-fatal');
      fatal.hidden = false;
      fatal.textContent = `Kunne ikke starte kurateringen: ${error.message}`;
    });
}
