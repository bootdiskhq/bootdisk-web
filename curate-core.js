/* Decision logic for the curator screen, kept free of the DOM so the observable
 * behaviour (draft state, ordered writes, conflicts, retries, shortcuts) can be tested
 * directly. curate.js binds this to the page; both use the same action codes. */
const CURATOR_CLAIM_FIELDS = ["identity", "version", "content_kind", "distribution_kind", "description"];
const CURATOR_TYPING_TAGS = ["input", "textarea", "select"];
const CURATOR_ACTIONS = {
  g: "commit",
  h: "defer",
  z: "undo",
  e: "focus-fields",
  ArrowRight: "next",
  ArrowLeft: "previous",
  "?": "shortcuts",
};
const CURATOR_SHORTCUT_HINTS = [
  { keys: "G", action: "commit", label: "Godkjenn eller lagre og gå videre" },
  { keys: "H", action: "defer", label: "Hopp over med begrunnelse" },
  { keys: "Z", action: "undo", label: "Angre siste godkjenning" },
  { keys: "E", action: "focus-fields", label: "Hopp til første redigerbare felt" },
  { keys: "←/→", action: "previous", label: "Forrige og neste i køen" },
  { keys: "?", action: "shortcuts", label: "Vis eller skjul hurtigtastene" },
];

function curatorCanonical(value) {
  if (Array.isArray(value)) return value.map(curatorCanonical);
  if (value && typeof value === "object") {
    return Object.keys(value).sort().reduce((result, key) => {
      result[key] = curatorCanonical(value[key]);
      return result;
    }, {});
  }
  return value;
}

function curatorSameDraft(left, right) {
  return JSON.stringify(curatorCanonical(left)) === JSON.stringify(curatorCanonical(right));
}

/* Source identity is manifest plus entry: a K-id alone repeats across source manifests, so
 * it can never decide which entry a receipt belongs to. */
function curatorKeyId(key) {
  return key ? `${key.manifest ?? ""}/${key.entry ?? ""}` : null;
}

function curatorEntryNumber(entryId) {
  const digits = String(entryId ?? "").replace(/^K/i, "");
  return Number.isFinite(Number(digits)) ? Number(digits) : Number.MAX_SAFE_INTEGER;
}

/* Shortcuts stay out of the way of text entry, composition, key repeat and the
 * browser's own chords. Buttons and keys resolve to the same action code. */
function curatorShortcutAllowed(event) {
  if (!event || event.repeat) return false;
  if (event.isComposing || event.keyCode === 229) return false;
  if (event.ctrlKey || event.metaKey || event.altKey) return false;
  const target = event.target ?? {};
  if (target.isContentEditable) return false;
  return !CURATOR_TYPING_TAGS.includes(String(target.tagName ?? "").toLowerCase());
}

function curatorActionForEvent(event) {
  if (!curatorShortcutAllowed(event)) return null;
  const key = event.key;
  return CURATOR_ACTIONS[key] ?? CURATOR_ACTIONS[String(key ?? "").toLowerCase()] ?? null;
}

function createCuratorController(options) {
  const adapter = options.adapter;
  const manifest = options.manifest ?? adapter.manifest;
  /* Wrapped rather than passed by reference: a detached setTimeout throws
   * "Illegal invocation" in the browser. */
  const scheduler = options.scheduler ?? {
    set: (callback, delay) => setTimeout(callback, delay),
    clear: handle => clearTimeout(handle),
  };
  const autosaveDelay = options.autosaveDelay ?? 900;
  const newOperationId = options.operationId ?? (() => `op-${Math.random().toString(36).slice(2)}-${Date.now()}`);
  const listeners = new Set();

  const state = {
    ready: false,
    filter: "pending",
    items: [],
    summary: { pending: 0, deferred: 0, reviewed: 0, open_fields: 0, total: 0 },
    entry: null,
    draft: null,
    status: "idle",
    error: null,
    fieldErrors: {},
    conflict: null,
    busy: false,
    /* True while a return to the overview holds the gate. Decisions and internal
     * navigation are refused for that window, so the two can never overlap. */
    leaving: false,
    complete: false,
    notice: null,
    shortcutsVisible: false,
    pendingRetry: null,
    /* Bumped only when the draft is replaced wholesale, so the page can rebuild the
     * form without stealing the caret during ordinary typing. */
    draftToken: 0,
  };

  let autosaveTimer = null;
  let leaving = null;
  let writing = null;
  let inflightSave = null;
  /* The last failed operation, kept whole so a retry re-sends an identical request. */
  let pendingOperation = null;

  function emit() {
    for (const listener of listeners) listener(state);
  }

  function clone(value) {
    return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  }

  function dirty() {
    return Boolean(state.entry && state.draft && !curatorSameDraft(state.draft, state.entry.draft));
  }

  function cancelAutosave() {
    if (autosaveTimer !== null) {
      scheduler.clear(autosaveTimer);
      autosaveTimer = null;
    }
  }

  function scheduleAutosave() {
    cancelAutosave();
    autosaveTimer = scheduler.set(() => {
      autosaveTimer = null;
      save().catch(() => { /* Reported through state.error; never rethrown into a timer. */ });
    }, autosaveDelay);
  }

  function applyError(error, fallbackMessage) {
    const code = error?.code ?? "unknown_error";
    if (code === "revision_conflict" && error.current_entry) {
      /* Local text is never overwritten: both versions are shown for a deliberate choice. */
      state.conflict = { local: clone(state.draft), server: clone(error.current_entry) };
      state.status = "error";
      state.error = { code, message: error.message ?? "Oppføringen er endret et annet sted." };
      state.fieldErrors = {};
      return;
    }
    state.status = "error";
    state.error = { code, message: error?.message ?? fallbackMessage, retryable: Boolean(error?.retryable) };
    state.fieldErrors = error?.field_errors ?? {};
  }

  /* Writes are serialised per entry: a receipt that arrives after further typing updates
   * the revision but must not present newer input as saved. */
  function write(kind, run) {
    const previous = writing ?? Promise.resolve();
    const task = previous.catch(() => {}).then(run);
    writing = task.catch(() => {});
    return task;
  }

  function quiesce() {
    return (writing ?? Promise.resolve()).then(() => null, () => null);
  }

  function forgetPendingOperation() {
    pendingOperation = null;
    state.pendingRetry = null;
  }

  /* One gate for every mutation. The request is built inside the serialised write so it
   * carries the current revision, then kept verbatim: a retry sends the same operation ID
   * and the same payload, which is what makes a committed-but-timed-out write safe. */
  function submit(kind, build, apply) {
    const sentFor = curatorKeyId(state.entry?.key);
    let request = null;

    const attempt = () => write(kind, () => {
      if (!request) request = build();
      return adapter[kind](request);
    }).then(receipt => {
      forgetPendingOperation();
      return apply(receipt, sentFor);
    }, error => {
      pendingOperation = { kind, entryId: sentFor, replay: attempt };
      state.pendingRetry = { kind, operation_id: request?.operation_id ?? null };
      applyError(error, "Handlingen kunne ikke fullføres.");
      emit();
      throw error;
    });

    return attempt();
  }

  function save() {
    cancelAutosave();
    /* Even a clean draft may have a write still on its way back; callers must be able to
     * wait for it before moving on. */
    if (!state.entry || !dirty() || state.conflict) return quiesce();
    const draft = clone(state.draft);
    const payloadKey = JSON.stringify(curatorCanonical(draft));
    if (inflightSave && inflightSave.payloadKey === payloadKey) return inflightSave.promise;

    state.status = "saving";
    state.error = null;
    emit();

    const promise = submit(
      "saveDraft",
      () => ({
        key: clone(state.entry.key),
        expected_revision: state.entry.revision,
        operation_id: newOperationId(),
        draft,
      }),
      (receipt, sentFor) => {
        /* A receipt belongs to the entry it was sent for, identified by manifest and entry
         * together. If the curator has moved on, it must never become the state of the
         * entry now on screen. */
        if (curatorKeyId(state.entry?.key) !== sentFor) return receipt;
        state.entry = receipt.entry;
        /* The receipt only reports what it carried. Newer edits stay unsaved. */
        if (curatorSameDraft(state.draft, draft)) {
          state.status = "saved";
          state.fieldErrors = {};
        } else {
          state.status = "dirty";
          scheduleAutosave();
        }
        emit();
        return receipt;
      },
    );

    const settled = () => {
      if (inflightSave && inflightSave.promise === promise) inflightSave = null;
    };
    promise.then(settled, settled);
    inflightSave = { payloadKey, promise };
    return promise;
  }

  function loadQueue() {
    return Promise.all([
      adapter.getQueue({ manifest, filter: state.filter }),
      adapter.getQueue({ manifest, filter: "all" }),
    ]).then(([active, all]) => {
      state.items = active.items;
      state.summary = {
        total: all.items.length,
        pending: all.items.filter(item => item.queue_state === "pending").length,
        deferred: all.items.filter(item => item.queue_state === "deferred").length,
        reviewed: all.items.filter(item => item.queue_state === "reviewed").length,
        open_fields: all.items.filter(item => item.open_fields.length > 0).length,
      };
      return active;
    });
  }

  function openEntry(key, { bookmark = true } = {}) {
    return adapter.getEntry({ key }).then(entry => {
      state.entry = entry;
      state.draft = clone(entry.draft);
      state.draftToken += 1;
      state.status = "idle";
      state.error = null;
      state.fieldErrors = {};
      state.conflict = null;
      state.complete = false;
      forgetPendingOperation();
      emit();
      if (!bookmark) return entry;
      return adapter.setResume({ key }).then(() => entry, () => {
        /* A failed bookmark is a visible warning, never a failed decision. */
        state.notice = "Bokmerket for «fortsett der du slapp» kunne ikke lagres.";
        emit();
        return entry;
      });
    });
  }

  function start() {
    return loadQueue().then(active => {
      const resume = active.resume_key && state.items.some(item => item.key.entry === active.resume_key.entry)
        ? active.resume_key
        : state.items[0]?.key ?? null;
      state.ready = true;
      if (!resume) {
        state.complete = true;
        state.entry = null;
        state.draft = null;
        emit();
        return null;
      }
      /* Resuming must not change the entry's review status. */
      return openEntry(resume, { bookmark: false });
    });
  }

  function setFilter(filter) {
    if (state.busy || state.leaving) return Promise.resolve(null);
    return flush().then(() => {
      if (state.busy || state.leaving || dirty()) return null;
      state.filter = filter;
      return loadQueue().then(() => {
        /* Switching filter out of a finished queue opens that filter's first entry
         * instead of leaving the completion notice up. */
        if (!state.entry || state.complete) {
          state.complete = state.items.length === 0;
          if (state.items.length) return openEntry(state.items[0].key);
        }
        emit();
        return null;
      });
    }, () => null);
  }

  /* Settles the entry: waits out any write already on its way back, then saves whatever
   * the returning receipt left unsaved. A revert typed during a save looks clean until
   * that receipt lands, so one pass is not enough. */
  function flush(remaining = 3) {
    cancelAutosave();
    return save().then(result => {
      if (remaining > 1 && dirty() && !state.conflict && state.status !== "error") {
        return flush(remaining - 1);
      }
      return result;
    });
  }

  function editClaim(field, patch) {
    if (!state.draft || state.busy || state.conflict) return;
    const claim = state.draft.claims[field];
    /* Editing a value never promotes the claim on its own; assessment is an explicit choice. */
    state.draft.claims[field] = Object.assign({}, claim, patch);
    state.status = dirty() ? "dirty" : "idle";
    state.error = null;
    scheduleAutosave();
    emit();
  }

  function useProposal(proposal) {
    if (!proposal) return;
    editClaim(proposal.field, {
      value: clone(proposal.value),
      evidence_ids: clone(proposal.evidence_ids) ?? [],
    });
  }

  function commitLabel() {
    return dirty() || state.status === "saved" ? "Lagre og neste" : "Godkjenn og neste";
  }

  /* `state.busy` is set before the flush below, and `leave` refuses outright while it is
   * set, so a return can never open between this check and the decision. */
  function decide(run) {
    if (state.busy || state.leaving || !state.entry || state.conflict) return Promise.resolve(null);
    state.busy = true;
    state.error = null;
    /* A retry has to reach the adapter: the error left by the previous attempt is cleared
     * before flushing, so only a fresh failure blocks this one. */
    if (state.status === "error") state.status = dirty() ? "dirty" : "idle";
    emit();

    return flush().then(() => true, () => false).then(flushed => {
      if (!flushed || state.conflict || state.status === "error") {
        /* Never advance on an unsaved or rejected draft. */
        state.busy = false;
        emit();
        return null;
      }
      return run().then(receipt => {
        state.busy = false;
        emit();
        return receipt;
      }, error => {
        state.busy = false;
        emit();
        throw error;
      });
    });
  }

  function advance() {
    const currentNumber = curatorEntryNumber(state.entry?.key?.entry);
    return loadQueue().then(() => {
      const next = state.items.find(item => curatorEntryNumber(item.key.entry) > currentNumber) ?? state.items[0] ?? null;
      if (!next) {
        state.complete = true;
        state.entry = null;
        state.draft = null;
        state.draftToken += 1;
        state.status = "idle";
        emit();
        return null;
      }
      return openEntry(next.key);
    });
  }

  function approve() {
    return decide(() => submit(
      "approve",
      () => ({
        key: clone(state.entry.key),
        expected_revision: state.entry.revision,
        operation_id: newOperationId(),
      }),
      receipt => {
        state.entry = receipt.entry;
        state.draft = clone(receipt.entry.draft);
        state.draftToken += 1;
        state.status = "idle";
        return advance().then(() => receipt);
      },
    ));
  }

  function defer(reason) {
    return decide(() => submit(
      "defer",
      () => ({
        key: clone(state.entry.key),
        expected_revision: state.entry.revision,
        operation_id: newOperationId(),
        reason,
      }),
      receipt => {
        state.entry = receipt.entry;
        return advance().then(() => receipt);
      },
    ));
  }

  function undo() {
    const available = state.entry?.undo ?? null;
    if (!available) return Promise.resolve(null);
    return decide(() => submit(
      "undo",
      () => ({
        key: clone(state.entry.key),
        expected_revision: state.entry.revision,
        operation_id: newOperationId(),
        decision_id: available.decision_id,
      }),
      receipt => {
        /* Undo stays on the restored entry and keeps the current draft. */
        const keptDraft = clone(state.draft);
        state.entry = receipt.entry;
        state.draft = keptDraft;
        state.draftToken += 1;
        state.status = dirty() ? "dirty" : "idle";
        return loadQueue().then(() => {
          emit();
          return receipt;
        });
      },
    ));
  }

  function retry() {
    const operation = pendingOperation;
    if (!operation || state.leaving) return Promise.resolve(null);
    if (operation.kind === "saveDraft") {
      state.error = null;
      state.status = "saving";
      emit();
      return operation.replay();
    }
    /* approve, defer and undo all re-enter through the same gate. */
    return decide(() => operation.replay());
  }

  function resolveConflict(choice) {
    const conflict = state.conflict;
    if (!conflict) return Promise.resolve(null);
    state.entry = conflict.server;
    state.conflict = null;
    state.error = null;
    forgetPendingOperation();
    state.draftToken += 1;
    if (choice === "load_server") {
      state.draft = clone(conflict.server.draft);
      state.status = "idle";
    } else {
      /* Keeping local text requires a new, deliberate write against the fresh revision. */
      state.draft = clone(conflict.local);
      state.status = dirty() ? "dirty" : "idle";
    }
    emit();
    return Promise.resolve(state.status);
  }

  function select(key) {
    /* Waits for any write already on its way back, so a late receipt can never land on
     * the entry the curator has just opened. The conditions are read again after the wait,
     * for the same reason `leave` does: a decision may have started meanwhile. */
    if (state.busy || state.leaving) return Promise.resolve(null);
    return flush().then(() => {
      if (state.busy || state.leaving || dirty() || state.status === "error" || state.conflict) return null;
      return openEntry(key);
    }, () => null);
  }

  /* Leaving the screen altogether. One boundary, held for the whole return.
   *
   * Checking the entry is settled *before* waiting for the flush is not enough: a decision
   * started while the flush is in the air would leave the page mid-decision. So the return
   * takes the gate for its whole duration — `decide`, `select`, `setFilter` and `retry` all
   * refuse while `state.leaving` is set — the conditions are re-read after the wait, and the
   * caller's navigation runs inside the gate, before it is released. Nothing can start
   * between the check and the page going away.
   *
   * Typing is deliberately still allowed: the flush saves whatever arrives, and text that
   * lands after the last pass simply leaves the entry dirty and stops the return. Either
   * way no text is lost, which is what matters.
   *
   * `navigate` is called once, and only when the answer is true. A second click while a
   * return is already running is the same return, not a competing one, so it is given the
   * same promise and the same answer. Once a return has been granted the gate stays shut:
   * leaving a page is not instant, and nothing may start on a screen on its way out. */
  function leave(navigate) {
    if (leaving) return leaving;
    if (state.busy) return Promise.resolve(false);
    state.leaving = true;
    emit();

    leaving = flush().then(() => true, () => false).then(flushed => {
      const safe = flushed && !state.busy && !dirty() && state.status !== "error" && !state.conflict;
      if (!safe) {
        /* Stopped: the screen is staying, so everything works again. */
        state.leaving = false;
        leaving = null;
        emit();
        return false;
      }
      emit();
      if (navigate) navigate();
      return true;
    });
    return leaving;
  }

  function step(direction) {
    const currentNumber = curatorEntryNumber(state.entry?.key?.entry);
    const ordered = state.items;
    const position = ordered.findIndex(item => curatorEntryNumber(item.key.entry) === currentNumber);
    const target = direction === "next" ? ordered[position + 1] : ordered[position - 1];
    return target ? select(target.key) : Promise.resolve(null);
  }

  /* One action table for buttons and keys alike. */
  function dispatch(action, payload) {
    switch (action) {
      case "commit": return approve();
      case "defer": return defer(payload);
      case "undo": return undo();
      case "next": return step("next");
      case "previous": return step("previous");
      case "retry": return retry();
      case "shortcuts":
        state.shortcutsVisible = !state.shortcutsVisible;
        emit();
        return Promise.resolve(null);
      case "focus-fields":
        return Promise.resolve("focus-fields");
      default:
        return Promise.resolve(null);
    }
  }

  return {
    state,
    start,
    dispatch,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    editClaim,
    useProposal,
    setFilter,
    select,
    leave,
    flush,
    save,
    resolveConflict,
    retry,
    loadQueue,
    openEntry,
    commitLabel,
    isDirty: dirty,
    clearNotice() {
      state.notice = null;
      emit();
    },
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    createCuratorController,
    curatorShortcutAllowed,
    curatorActionForEvent,
    curatorSameDraft,
    curatorEntryNumber,
    curatorKeyId,
    CURATOR_CLAIM_FIELDS,
    CURATOR_SHORTCUT_HINTS,
    CURATOR_ACTIONS,
  };
}
