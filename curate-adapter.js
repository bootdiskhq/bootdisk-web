/* Fixture adapter for the local curator. Implements the bootdisk-curator-v1 methods
 * against the unchanged Catalog fixture bundle so the screen can be built before the
 * local service exists. It stores simulated review state in versioned browser storage
 * and never writes catalog data; fixture mode is always visible in the interface. */
const CURATOR_SCHEMA = "bootdisk-curator-v1";
const CURATOR_STORAGE_VERSION = 1;
const CLAIM_FIELDS = ["identity", "version", "content_kind", "distribution_kind", "description"];
const CONTENT_KINDS = ["application", "game", "course", "image_collection", "font_collection", "reference"];
const DISTRIBUTION_KINDS = ["full", "demo", "trial", "update", "unknown"];
const QUEUE_FILTERS = ["pending", "deferred", "open_fields", "all"];
const SIMULATED_FAULTS = ["write_failed", "service_unavailable", "timeout_after_commit", "revision_conflict"];
const OVERLAY_ISSUES = {
  media_unavailable: "Mediet er ikke tilgjengelig. Bevart metadata vises fortsatt.",
  read_permission_denied: "Verten nekter lesing av kildefilen. Observasjonen kan ikke fornyes nå.",
};

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function curatorError(code, message, extra) {
  return Object.assign({ code, message, retryable: false, field_errors: {}, current_entry: null }, extra || {});
}

function entryNumber(entryId) {
  const digits = String(entryId ?? "").replace(/^K/i, "");
  return Number.isFinite(Number(digits)) ? Number(digits) : Number.MAX_SAFE_INTEGER;
}

function openFieldsOf(claims) {
  return CLAIM_FIELDS.filter(field => claims?.[field]?.assessment === "unresolved");
}

/* Fingerprints let a repeated operation ID be recognised as an exact retry rather than
 * a second decision. The backend checks the operation ID before the revision. */
function fingerprint(kind, payload) {
  return `${kind}:${JSON.stringify(payload ?? null)}`;
}

function validateDraft(draft, evidence) {
  const fieldErrors = {};
  const claims = draft?.claims ?? {};
  const knownEvidence = new Set((evidence ?? []).map(item => item.id));

  for (const field of CLAIM_FIELDS) {
    const claim = claims[field];
    if (!claim || typeof claim !== "object") {
      fieldErrors[field] = "Påstanden mangler i kladden.";
      continue;
    }
    if (claim.assessment !== "accepted" && claim.assessment !== "unresolved") {
      fieldErrors[field] = "Vurderingen må være «belagt» eller «uavklart».";
      continue;
    }
    if (claim.assessment === "unresolved" && !String(claim.reason ?? "").trim()) {
      fieldErrors[field] = "Uavklarte felt må ha en begrunnelse.";
      continue;
    }
    const evidenceIds = Array.isArray(claim.evidence_ids) ? claim.evidence_ids : [];
    const unknown = evidenceIds.filter(id => !knownEvidence.has(id));
    if (unknown.length) {
      fieldErrors[field] = `Ukjent kildebelegg: ${unknown.join(", ")}.`;
      continue;
    }
    if (claim.assessment === "accepted" && evidenceIds.length === 0) {
      fieldErrors[field] = "Et belagt felt må vise til minst ett kildebelegg.";
    }
  }

  if (!fieldErrors.identity && !String(claims.identity?.value?.name ?? "").trim()) {
    fieldErrors.identity = "Navnet kan ikke være tomt.";
  }
  if (!fieldErrors.version) {
    const version = String(claims.version?.value ?? "").trim();
    if (!version) fieldErrors.version = "Versjonen kan ikke være tom. Bruk «unknown» når den ikke er fastslått.";
    else if (version === "unknown" && claims.version.assessment === "accepted") {
      fieldErrors.version = "«unknown» kan ikke godkjennes som belagt versjon.";
    }
  }
  if (!fieldErrors.content_kind && !CONTENT_KINDS.includes(claims.content_kind?.value)) {
    fieldErrors.content_kind = "Ukjent innholdstype.";
  }
  if (!fieldErrors.distribution_kind) {
    if (!DISTRIBUTION_KINDS.includes(claims.distribution_kind?.value)) {
      fieldErrors.distribution_kind = "Ukjent distribusjon.";
    } else if (claims.distribution_kind.value === "unknown" && claims.distribution_kind.assessment === "accepted") {
      fieldErrors.distribution_kind = "«unknown» distribusjon må stå som uavklart.";
    }
  }
  if (!fieldErrors.description) {
    if (claims.description?.value?.language !== "nb-NO") fieldErrors.description = "Beskrivelsen må være på nb-NO.";
    else if (!String(claims.description?.value?.text ?? "").trim()) fieldErrors.description = "Beskrivelsen kan ikke være tom.";
  }
  return fieldErrors;
}

function createFixtureAdapter(options) {
  const fixture = clone(options.fixture);
  const datasetId = options.datasetId ?? "curator-fixtures-v1";
  const storage = options.storage ?? null;
  const now = options.now ?? (() => new Date().toISOString());
  const storageKey = `${CURATOR_SCHEMA}/v${CURATOR_STORAGE_VERSION}/${datasetId}`;
  const sources = new Map(fixture.entries.map(entry => [entry.key.entry, entry]));
  const manifest = fixture.entries[0]?.key?.manifest ?? null;

  const simulation = { fault: null, overlays: {}, held: null, decisionCounter: 0 };
  let state = null;

  function initialState() {
    const entries = {};
    for (const source of fixture.entries) {
      entries[source.key.entry] = {
        revision: source.revision,
        revisionCounter: 0,
        queue_state: source.queue_state,
        accepted: clone(source.accepted),
        draft: clone(source.draft),
        history: [],
        reversible: [],
        operations: {},
      };
    }
    return { version: CURATOR_STORAGE_VERSION, dataset: datasetId, resume_key: null, entries };
  }

  function load() {
    if (state) return state;
    if (storage) {
      try {
        const raw = storage.getItem(storageKey);
        const parsed = raw ? JSON.parse(raw) : null;
        if (parsed && parsed.version === CURATOR_STORAGE_VERSION && parsed.entries) {
          state = parsed;
          return state;
        }
      } catch (error) {
        /* Unreadable local state falls back to the fixture baseline rather than failing. */
      }
    }
    state = initialState();
    persist();
    return state;
  }

  function persist() {
    if (!storage || !state) return;
    try {
      storage.setItem(storageKey, JSON.stringify(state));
    } catch (error) {
      /* Storage refusal must not fake a failed decision; the in-memory state stays authoritative. */
    }
  }

  function nextRevision(entryId, record) {
    record.revisionCounter += 1;
    return `fixture-${entryId}-${record.revisionCounter}`;
  }

  function nextDecisionId(entryId) {
    simulation.decisionCounter += 1;
    return `fixture-decision-${entryId}-${simulation.decisionCounter}`;
  }

  function requireEntry(key) {
    const entryId = key?.entry;
    const source = sources.get(entryId);
    if (!source) throw curatorError("not_found", `Ukjent oppføring: ${entryId}`);
    return { source, record: load().entries[entryId] };
  }

  function issuesFor(entryId, source, record) {
    const issues = clone(source.issues) ?? [];
    const overlay = simulation.overlays[entryId];
    if (overlay && OVERLAY_ISSUES[overlay]) {
      issues.push({ code: overlay, field: null, message: OVERLAY_ISSUES[overlay] });
    }
    /* Open fields stay visible after a review pass; reviewed does not mean resolved. */
    for (const field of openFieldsOf(record.accepted?.claims ?? record.draft?.claims)) {
      if (!issues.some(issue => issue.field === field)) {
        issues.push({ code: `${field}_unresolved`, field, message: "Feltet er beholdt som uavklart." });
      }
    }
    return issues;
  }

  function entryDocument(entryId) {
    const source = sources.get(entryId);
    const record = load().entries[entryId];
    const reversible = record.reversible[record.reversible.length - 1] ?? null;
    return {
      schema: CURATOR_SCHEMA,
      key: clone(source.key),
      revision: record.revision,
      queue_state: record.queue_state,
      source: clone(source.source),
      accepted: clone(record.accepted),
      draft: clone(record.draft),
      proposals: clone(source.proposals) ?? [],
      evidence: clone(source.evidence) ?? [],
      issues: issuesFor(entryId, source, record),
      undo: reversible ? { decision_id: reversible.decision_id, label: reversible.label } : null,
      history: clone(record.history),
    };
  }

  function queueItem(entryId) {
    const source = sources.get(entryId);
    const record = load().entries[entryId];
    const claims = record.accepted?.claims ?? record.draft?.claims;
    return {
      key: clone(source.key),
      title: source.source.title,
      queue_state: record.queue_state,
      identification_status: record.accepted?.identification_status ?? null,
      open_fields: openFieldsOf(claims),
    };
  }

  function matchesFilter(item, filter) {
    if (filter === "all") return true;
    if (filter === "open_fields") return item.open_fields.length > 0;
    return item.queue_state === filter;
  }

  /* A simulated fault is armed explicitly and consumed once, so no network error can
   * silently turn a real adapter into a fixture success or the other way round. */
  function takeFault() {
    const fault = simulation.fault;
    simulation.fault = null;
    return fault;
  }

  function settle(value) {
    if (!simulation.held) return Promise.resolve(value);
    const held = simulation.held;
    simulation.held = null;
    return new Promise((resolve, reject) => {
      held.resolveWith = () => resolve(value);
      held.rejectWith = error => reject(error);
      held.ready();
    });
  }

  /* Every mutation runs the same gate: operation ID first, then revision, then validation. */
  function mutate(kind, request, apply) {
    return new Promise((resolve, reject) => {
      let context;
      try {
        context = requireEntry(request.key);
      } catch (error) {
        reject(error);
        return;
      }
      const { source, record } = context;
      const entryId = source.key.entry;
      const mark = fingerprint(kind, request);
      const previous = record.operations[request.operation_id];

      if (previous) {
        if (previous.fingerprint !== mark) {
          reject(curatorError("operation_id_reused", "Operasjons-ID-en er allerede brukt med et annet innhold. Klienten må rette forespørselen."));
          return;
        }
        settle(clone(previous.receipt)).then(resolve, reject);
        return;
      }

      const fault = takeFault();
      if (fault === "revision_conflict") {
        record.revision = nextRevision(entryId, record);
        persist();
      }
      if (fault === "write_failed" || fault === "service_unavailable") {
        settle(null).then(
          () => reject(curatorError(fault, fault === "write_failed"
            ? "Skrivingen mislyktes. Endringene er beholdt lokalt."
            : "Den lokale tjenesten svarer ikke. Endringene er beholdt lokalt.", { retryable: true })),
          reject,
        );
        return;
      }

      if (request.expected_revision !== record.revision) {
        settle(null).then(
          () => reject(curatorError("revision_conflict", "Oppføringen er endret et annet sted. Velg hvordan den lokale kladden skal håndteres.", {
            current_entry: entryDocument(entryId),
          })),
          reject,
        );
        return;
      }

      let outcome;
      try {
        outcome = apply({ source, record, entryId });
      } catch (error) {
        settle(null).then(() => reject(error), reject);
        return;
      }

      record.revision = nextRevision(entryId, record);
      const receipt = {
        schema: CURATOR_SCHEMA,
        operation_id: request.operation_id,
        entry: entryDocument(entryId),
        decision_id: outcome?.decision_id ?? null,
      };
      record.operations[request.operation_id] = { fingerprint: mark, receipt: clone(receipt) };
      persist();

      /* A commit that times out on the way back is already durable: retrying the same
       * operation ID returns this receipt instead of deciding twice. */
      if (fault === "timeout_after_commit") {
        settle(null).then(
          () => reject(curatorError("service_unavailable", "Tjenesten svarte ikke i tide. Forsøk samme operasjon på nytt.", { retryable: true })),
          reject,
        );
        return;
      }
      settle(clone(receipt)).then(resolve, reject);
    });
  }

  function getQueue(request) {
    const filter = QUEUE_FILTERS.includes(request?.filter) ? request.filter : "pending";
    const current = load();
    const items = [...sources.keys()]
      .sort((left, right) => entryNumber(left) - entryNumber(right))
      .map(queueItem)
      .filter(item => matchesFilter(item, filter));
    return Promise.resolve({ schema: CURATOR_SCHEMA, items, resume_key: clone(current.resume_key) });
  }

  function getEntry(request) {
    try {
      const { source } = requireEntry(request.key);
      return Promise.resolve(entryDocument(source.key.entry));
    } catch (error) {
      return Promise.reject(error);
    }
  }

  function saveDraft(request) {
    return mutate("saveDraft", request, ({ record }) => {
      record.draft = clone(request.draft);
      return { decision_id: null };
    });
  }

  function defer(request) {
    return mutate("defer", request, ({ record }) => {
      if (!String(request.reason ?? "").trim()) {
        throw curatorError("validation_failed", "Utsettelse krever en begrunnelse.", { field_errors: { reason: "Skriv hvorfor oppføringen hoppes over." } });
      }
      record.queue_state = "deferred";
      record.history.push({ kind: "defer", reason: request.reason, at: now() });
      return { decision_id: null };
    });
  }

  function approve(request) {
    return mutate("approve", request, ({ source, record, entryId }) => {
      const fieldErrors = validateDraft(record.draft, source.evidence);
      if (Object.keys(fieldErrors).length) {
        throw curatorError("validation_failed", "Kladden kan ikke godkjennes ennå.", { field_errors: fieldErrors });
      }
      const identity = record.draft.claims.identity;
      if (identity.value.software_id === null) {
        const collision = [...sources.entries()].find(([otherId, other]) =>
          otherId !== entryId &&
          String(other.accepted?.claims?.identity?.value?.name ?? "").toLowerCase() === String(identity.value.name).toLowerCase());
        if (collision) {
          throw curatorError("shared_record_conflict", `Navnet er allerede knyttet til en delt post (${collision[0]}). Delt identitet må løses separat før denne endringen kan lagres.`, {
            field_errors: { identity: "Delt post må avklares av den lokale tjenesten." },
          });
        }
      }

      const decisionId = nextDecisionId(entryId);
      const previousAccepted = clone(record.accepted);
      record.accepted = {
        /* Identity is promoted only by an explicit supported identity decision. */
        identification_status: identity.assessment === "accepted"
          ? "curated"
          : (previousAccepted?.identification_status ?? "interpreted"),
        claims: clone(record.draft.claims),
      };
      record.queue_state = "reviewed";
      record.history.push({
        kind: "approve",
        decision_id: decisionId,
        previous_claims: previousAccepted?.claims ?? null,
        new_claims: clone(record.accepted.claims),
        at: now(),
      });
      record.reversible.push({ decision_id: decisionId, label: "Angre siste godkjenning", previous: previousAccepted });
      return { decision_id: decisionId };
    });
  }

  function undo(request) {
    return mutate("undo", request, ({ record, entryId }) => {
      const reversible = record.reversible[record.reversible.length - 1] ?? null;
      if (!reversible || reversible.decision_id !== request.decision_id) {
        throw curatorError("undo_conflict", "Beslutningen kan ikke angres nå. Hent oppdatert tilstand og prøv igjen.");
      }
      record.reversible.pop();
      const compensationId = nextDecisionId(entryId);
      record.history.push({
        kind: "undo",
        decision_id: compensationId,
        reverses: reversible.decision_id,
        previous_claims: clone(record.accepted?.claims ?? null),
        new_claims: clone(reversible.previous?.claims ?? null),
        at: now(),
      });
      /* Undo is a compensating event: previous claims return, the draft survives. */
      record.accepted = clone(reversible.previous);
      record.queue_state = "pending";
      return { decision_id: compensationId };
    });
  }

  function setResume(request) {
    const current = load();
    current.resume_key = clone(request.key);
    persist();
    return Promise.resolve({ schema: CURATOR_SCHEMA, resume_key: clone(current.resume_key) });
  }

  return {
    schema: CURATOR_SCHEMA,
    fixtureMode: true,
    manifest,
    getQueue,
    getEntry,
    saveDraft,
    defer,
    approve,
    undo,
    setResume,
    reset() {
      state = initialState();
      simulation.fault = null;
      simulation.overlays = {};
      persist();
    },
    simulation: {
      faults: SIMULATED_FAULTS,
      overlayIssues: Object.keys(OVERLAY_ISSUES),
      arm(fault) {
        if (!SIMULATED_FAULTS.includes(fault)) throw new Error(`Ukjent simulering: ${fault}`);
        simulation.fault = fault;
      },
      armed() {
        return simulation.fault;
      },
      clear() {
        simulation.fault = null;
      },
      setOverlay(entryId, code) {
        if (code === null) delete simulation.overlays[entryId];
        else simulation.overlays[entryId] = code;
      },
      overlays() {
        return { ...simulation.overlays };
      },
      /* Holds the next mutation so a test can release it after further typing and prove
       * a late receipt cannot mark newer input as saved. */
      hold() {
        let ready;
        const handle = {
          arrived: new Promise(resolve => { ready = resolve; }),
          ready: () => ready(handle),
          release() { handle.resolveWith(); },
          fail(error) { handle.rejectWith(error); },
        };
        simulation.held = handle;
        return handle;
      },
    },
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { createFixtureAdapter, validateDraft, openFieldsOf, entryNumber, CURATOR_SCHEMA, CLAIM_FIELDS, CONTENT_KINDS, DISTRIBUTION_KINDS, QUEUE_FILTERS };
}
