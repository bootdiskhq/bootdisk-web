/* Page binding for the local curator. Rendering is text-only: source observations and
 * package members are never interpreted as HTML, executable content or file links.
 * Buttons and keyboard shortcuts resolve to the same action codes in curate-core.js. */
const FIXTURE_URL = "tests/fixtures/curator-fixtures-v1.json";
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
const QUEUE_STATE_MARKS = { pending: "●", deferred: "‖", reviewed: "✓" };
const IDENTIFICATION_LABELS = { curated: "Kuratert identitet", interpreted: "Foreløpig identitet" };
const ASSESSMENT_LABELS = { accepted: "Belagt", unresolved: "Uavklart" };
const FIELD_SPECS = [
  { field: "identity", label: "Identitet og navn", control: "identity" },
  { field: "version", label: "Versjon", control: "text", help: "Bruk «unknown» med begrunnelse når versjonen ikke er fastslått." },
  { field: "content_kind", label: "Innholdstype", control: "select", options: CONTENT_KINDS, labels: CONTENT_KIND_LABELS },
  { field: "distribution_kind", label: "Distribusjon", control: "select", options: DISTRIBUTION_KINDS, labels: DISTRIBUTION_LABELS, help: "«Ukjent» må stå som uavklart. Freeware betyr ikke automatisk full versjon." },
  { field: "description", label: "Norsk beskrivelse (nb-NO)", control: "textarea" },
];

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

/* What a claim's editable control displays, as opposed to the read-only summary text. */
function claimControlValue(field, value) {
  if (field === "identity") return value?.name ?? "";
  if (field === "description") return value?.text ?? "";
  return value ?? "";
}

function claimValueText(field, value) {
  if (field === "identity") return `${value?.name ?? ""}${value?.software_id ? ` (${value.software_id})` : " (ny eller ukjent ID)"}`;
  if (field === "description") return value?.text ?? "";
  if (field === "content_kind") return CONTENT_KIND_LABELS[value] ?? String(value ?? "");
  if (field === "distribution_kind") return DISTRIBUTION_LABELS[value] ?? String(value ?? "");
  return String(value ?? "");
}

function byteText(size) {
  return typeof size === "number" ? `${size.toLocaleString("nb-NO")} byte` : "ukjent størrelse";
}

function bootstrap(fixture) {
  const adapter = createFixtureAdapter({
    fixture,
    storage: (() => {
      try {
        window.localStorage.setItem("curator-probe", "1");
        window.localStorage.removeItem("curator-probe");
        return window.localStorage;
      } catch (error) {
        return null;
      }
    })(),
  });
  const controller = createCuratorController({ adapter });

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
    if (accepted) acceptedLine.append(element("span", null, ` — ${ASSESSMENT_LABELS[accepted.assessment] ?? accepted.assessment}`));
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
      control.value = claim.value ?? "";
      control.addEventListener("input", () => controller.editClaim(spec.field, { value: control.value }));
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
    detail.open = claim.assessment === "unresolved" || Boolean(String(claim.reason ?? "").trim());
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
      evidenceGroup.append(element("legend", null, "Kildebelegg for denne påstanden"));
      for (const item of state.entry.evidence) {
        const option = element("span", "evidence-option");
        const input = element("input");
        input.type = "checkbox";
        input.id = `evidence-${spec.field}-${item.id}`;
        input.checked = (claim.evidence_ids ?? []).includes(item.id);
        registry.evidence.set(item.id, input);
        input.addEventListener("change", () => {
          const current = new Set(controller.state.draft.claims[spec.field].evidence_ids ?? []);
          if (input.checked) current.add(item.id);
          else current.delete(item.id);
          controller.editClaim(spec.field, { evidence_ids: [...current] });
        });
        const optionLabel = element("label");
        optionLabel.htmlFor = input.id;
        optionLabel.append(element("code", null, item.id), element("span", null, ` ${item.field}`));
        option.append(input, optionLabel);
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

    nodes.evidenceCount.textContent = String(entry.evidence.length);
    nodes.evidence.replaceChildren(...entry.evidence.map(item => {
      const node = element("li");
      node.append(element("span", "evidence-id", item.id));
      node.append(element("span", "evidence-meta", `${item.field} · ${item.source_ref.entry}${item.source_ref.path ? ` · ${item.source_ref.path}` : ""}`));
      if (item.observation && typeof item.observation === "object") {
        const list = element("dl", "evidence-observation");
        for (const [key, value] of Object.entries(item.observation)) {
          list.append(element("dt", null, key), element("dd", null, String(value)));
        }
        node.append(list);
      } else {
        node.append(element("span", "evidence-observation", String(item.observation ?? "")));
      }
      return node;
    }));

    const history = entry.history ?? [];
    nodes.historyCount.textContent = String(history.length);
    nodes.history.replaceChildren(...history.map(event => element("li", null, [
      event.kind === "approve" ? "Godkjent" : event.kind === "undo" ? "Angret" : "Utsatt",
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
        const checked = chosen.has(id);
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
    const locked = state.busy || Boolean(state.conflict);
    nodes.commit.disabled = locked;
    nodes.deferButton.disabled = locked;
    nodes.retry.disabled = state.busy;
    nodes.undo.hidden = !state.entry?.undo;
    if (state.entry?.undo) {
      nodes.undo.textContent = "";
      nodes.undo.append(element("span", null, state.entry.undo.label), element("kbd", null, "Z"));
      nodes.undo.disabled = locked;
    }
    /* Editing is disabled during the short approve/defer/undo operation. */
    for (const control of nodes.form.querySelectorAll("input, select, textarea, button")) {
      control.disabled = locked;
    }

    nodes.notice.hidden = !state.notice;
    if (state.notice) nodes.notice.textContent = state.notice;

    nodes.simulateFault.value = adapter.simulation.armed() ?? "";
    nodes.simulateMedia.value = state.entry ? (adapter.simulation.overlays()[state.entry.key.entry] ?? "") : "";
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
  return controller.start().catch(error => {
    nodes.fatal.hidden = false;
    nodes.fatal.textContent = `Kunne ikke starte kurateringsskjermen: ${error.message}`;
  });
}

if (typeof document !== "undefined") {
  fetch(FIXTURE_URL)
    .then(response => {
      if (!response.ok) throw new Error(`Fant ikke prøvedataene (${response.status}).`);
      return response.json();
    })
    .then(bootstrap)
    .catch(error => {
      const fatal = document.querySelector("#curate-fatal");
      fatal.hidden = false;
      fatal.textContent = `Kunne ikke laste prøvedataene: ${error.message}`;
    });
}
