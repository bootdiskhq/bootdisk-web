"""Behaviour tests for the local curator screen and its fixture adapter.

The JavaScript cases drive the real adapter and controller through Node, so they
verify observable behaviour (ordered writes, retries, conflicts, recovery) rather than
the presence of function names in a file.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "curator_harness.js"
CATALOG_COMMIT = "09bd0dbccac4e9ee39f1d2593558f96543449116"
FIXTURE_SHA256 = "9d5516da282578794bf913e26a2b801e674e9b97497fd5ee44d924b794e2e3e1"

NODE = shutil.which("node")


def behaviour(body: str) -> str:
    return f"""
const {{
  assert, fixture, MANIFEST, key, harness, memoryStorage,
  createFixtureAdapter, validateDraft,
  curatorActionForEvent, curatorShortcutAllowed, CURATOR_SHORTCUT_HINTS, CURATOR_ACTIONS,
}} = require({str(HARNESS)!r});

(async () => {{
{body}
}})().catch(error => {{
  console.error(error.stack || error.message || String(error));
  process.exit(1);
}});
"""


@unittest.skipUnless(NODE, "Node.js is required for the curator behaviour tests")
class CuratorBehaviourTests(unittest.TestCase):
    def run_behaviour(self, body: str) -> str:
        result = subprocess.run(
            [NODE, "-e", behaviour(body)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={"CURATOR_WEB_ROOT": str(ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        if result.returncode != 0:
            self.fail(f"curator behaviour failed:\n{result.stderr}\n{result.stdout}")
        return result.stdout

    def test_approve_opens_next_entry_only_after_the_adapter_answers(self):
        """Work order case 1: read K23's version evidence, approve, advance on the receipt."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));

  const versionEvidence = controller.state.entry.evidence.filter(item => item.field === "payload_observation");
  assert.equal(versionEvidence.length, 2, "K23 carries two payload observations");
  assert.ok(versionEvidence.some(item => item.observation.text.includes("1.10")), "product version is readable");
  assert.ok(versionEvidence.some(item => item.observation.method === "zip_member"), "the ZIP member is bound to a hash");
  const proposal = controller.state.entry.proposals.find(item => item.field === "version");
  assert.match(proposal.reason, /1\\.0\\.0\\.1 er ikke produktversjonen/, "the PE version is explained as not the product version");
  assert.equal(controller.commitLabel(), "Godkjenn og neste", "an unchanged draft is approved, not saved");

  const held = adapter.simulation.hold();
  const approving = controller.dispatch("commit");
  await held.arrived;
  assert.equal(controller.state.entry.key.entry, "K23", "no advance while the mutation is in flight");
  assert.equal(controller.state.busy, true, "editing is locked during the decision");
  held.release();
  await approving;

  assert.notEqual(controller.state.entry.key.entry, "K23", "advanced once the receipt arrived");
  const reviewed = await adapter.getEntry({ key: key("K23") });
  assert.equal(reviewed.queue_state, "reviewed");
  assert.equal(reviewed.accepted.claims.version.value, "1.10");
  assert.ok(reviewed.undo, "an approval offers a reversible decision");
""")

    def test_saved_draft_survives_reload_without_counting_as_an_approval(self):
        """Work order case 2: correct a field, save, reload, then approve the latest revision."""
        self.run_behaviour("""
  const storage = memoryStorage();
  const first = harness({ storage, prefix: "a" });
  await first.controller.start();
  await first.controller.select(key("K23"));
  first.controller.editClaim("version", { value: "1.10b" });
  assert.equal(first.controller.state.status, "dirty");
  assert.equal(first.controller.commitLabel(), "Lagre og neste", "the label changes after an edit");
  first.scheduler.run();
  await first.controller.flush();
  assert.equal(first.controller.state.status, "saved");

  // A reload rebuilds the adapter over the same browser storage.
  const second = harness({ storage, prefix: "b" });
  await second.controller.start();
  await second.controller.select(key("K23"));
  assert.equal(second.controller.state.draft.claims.version.value, "1.10b", "the correction came back");
  assert.equal(second.controller.state.entry.queue_state, "pending", "a saved draft is not an approval");
  assert.equal(second.controller.state.status, "idle", "the recovered draft is not reported as unsaved");

  await second.controller.dispatch("commit");
  const approved = await second.adapter.getEntry({ key: key("K23") });
  assert.equal(approved.queue_state, "reviewed");
  assert.equal(approved.accepted.claims.version.value, "1.10b", "the approval used the recovered draft");
""")

    def test_skipping_keeps_the_reason_and_the_draft_and_stays_findable(self):
        """Work order case 3: skip K4 with a reason and find it again under deferred."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K4"));
  controller.editClaim("description", { value: { language: "nb-NO", text: "Venter på dekoding av Gentee-pakken." } });

  await assert.rejects(
    adapter.defer({ key: key("K4"), expected_revision: controller.state.entry.revision, operation_id: "bare-defer", reason: "  " }),
    error => error.code === "validation_failed" && Boolean(error.field_errors.reason),
    "a defer without a reason is rejected",
  );

  await controller.dispatch("defer", "Gentee-pakken må dekodes først");
  const deferred = await adapter.getEntry({ key: key("K4") });
  assert.equal(deferred.queue_state, "deferred");
  assert.equal(deferred.draft.claims.description.value.text, "Venter på dekoding av Gentee-pakken.", "the draft survived the skip");
  assert.equal(deferred.history.at(-1).reason, "Gentee-pakken må dekodes først");

  await controller.setFilter("deferred");
  assert.deepEqual(controller.state.items.map(item => item.key.entry), ["K4"], "the skipped entry is findable again");
  await controller.setFilter("pending");
  assert.deepEqual(controller.state.items.map(item => item.key.entry), ["K23"], "an opaque installer does not block the queue");
""")

    def test_undo_restores_previous_claims_keeps_history_and_keeps_the_draft(self):
        """Work order case 4: undo an approval without deleting history or an existing draft."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.setFilter("all");
  await controller.select(key("K23"));
  const before = JSON.parse(JSON.stringify(controller.state.entry.accepted.claims));

  controller.editClaim("version", { value: "1.11" });
  await controller.flush();
  await controller.dispatch("commit");

  await controller.setFilter("all");
  await controller.select(key("K23"));
  assert.equal(controller.state.entry.queue_state, "reviewed");
  assert.equal(controller.state.entry.accepted.claims.version.value, "1.11");

  // An unrelated draft edit must not be lost by the undo.
  controller.editClaim("description", { value: { language: "nb-NO", text: "Kladd som skal overleve angring." } });
  await controller.flush();

  const undoAction = controller.state.entry.undo;
  assert.ok(undoAction, "the server supplies the reversible decision");
  await controller.dispatch("undo");

  const restored = await adapter.getEntry({ key: key("K23") });
  assert.equal(restored.queue_state, "pending", "the entry returns to the queue");
  assert.equal(restored.accepted.claims.version.value, before.version.value, "previous accepted values are back");
  assert.equal(restored.draft.claims.description.value.text, "Kladd som skal overleve angring.", "the draft was not deleted");
  assert.equal(restored.history.filter(event => event.kind === "approve").length, 1, "history keeps the approval");
  assert.equal(restored.history.filter(event => event.kind === "undo").length, 1, "undo is a compensating event, not a deletion");
  assert.equal(restored.undo, null, "there is nothing left to reverse");
  assert.equal(controller.state.entry.key.entry, "K23", "undo stays on the restored entry");
""")

    def test_failed_and_uncertain_mutations_keep_input_and_decide_only_once(self):
        """Work order case 5: failures hold the input, and double-click or retry never decides twice."""
        self.run_behaviour("""
  // A failed autosave keeps the edit and blocks the next action.
  const saving = harness({ prefix: "s" });
  await saving.controller.start();
  await saving.controller.select(key("K23"));
  saving.controller.editClaim("version", { value: "1.10c" });
  saving.adapter.simulation.arm("write_failed");
  await saving.controller.flush().catch(() => {});
  assert.equal(saving.controller.state.status, "error");
  assert.equal(saving.controller.state.draft.claims.version.value, "1.10c", "the typed value is kept");
  saving.adapter.simulation.arm("write_failed");
  await saving.controller.dispatch("commit").catch(() => {});
  assert.equal(saving.controller.state.entry.key.entry, "K23", "a failed save stops the next action");
  assert.equal(saving.controller.state.status, "error");
  assert.equal(saving.controller.state.draft.claims.version.value, "1.10c", "the typed value is still kept");
  const untouched = await saving.adapter.getEntry({ key: key("K23") });
  assert.equal(untouched.queue_state, "pending", "nothing was approved");

  // Once the write succeeds, the same button saves and approves in one action.
  await saving.controller.dispatch("commit");
  const committed = await saving.adapter.getEntry({ key: key("K23") });
  assert.equal(committed.queue_state, "reviewed");
  assert.equal(committed.accepted.claims.version.value, "1.10c");

  // A double click produces one decision.
  const doubled = harness({ prefix: "d" });
  await doubled.controller.start();
  await doubled.controller.select(key("K23"));
  const held = doubled.adapter.simulation.hold();
  const firstClick = doubled.controller.dispatch("commit");
  await held.arrived;
  const secondClick = await doubled.controller.dispatch("commit");
  assert.equal(secondClick, null, "the second click is ignored while the first is in flight");
  held.release();
  await firstClick;
  const once = await doubled.adapter.getEntry({ key: key("K23") });
  assert.equal(once.history.filter(event => event.kind === "approve").length, 1);

  // A timeout after a committed write is retried with the original operation ID.
  const timedOut = harness({ prefix: "t" });
  await timedOut.controller.start();
  await timedOut.controller.select(key("K23"));
  timedOut.adapter.simulation.arm("timeout_after_commit");
  await timedOut.controller.dispatch("commit").catch(() => {});
  assert.equal(timedOut.controller.state.status, "error");
  assert.equal(timedOut.controller.state.entry.key.entry, "K23", "an uncertain mutation never advances");
  assert.ok(timedOut.controller.state.pendingRetry, "the operation is offered for retry");
  const retryId = timedOut.controller.state.pendingRetry.operation_id;
  await timedOut.controller.dispatch("retry");
  const retried = await timedOut.adapter.getEntry({ key: key("K23") });
  assert.equal(retried.history.filter(event => event.kind === "approve").length, 1, "the retry returned the original receipt");

  // Re-using that ID with another payload is an error, not a second decision.
  await assert.rejects(
    timedOut.adapter.saveDraft({ key: key("K23"), expected_revision: retried.revision, operation_id: retryId, draft: retried.draft }),
    error => error.code === "operation_id_reused",
  );
""")

    def test_revision_conflict_is_resolved_deliberately_without_losing_local_text(self):
        """Work order case 6: two revisions meet; the local draft survives either choice."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("description", { value: { language: "nb-NO", text: "Min lokale tekst." } });

  adapter.simulation.arm("revision_conflict");
  await controller.flush().catch(() => {});

  assert.ok(controller.state.conflict, "the conflict is shown rather than resolved silently");
  assert.equal(controller.state.error.code, "revision_conflict");
  assert.equal(controller.state.conflict.local.claims.description.value.text, "Min lokale tekst.", "local text is kept");
  assert.ok(controller.state.conflict.server, "the current server state is shown beside it");
  await controller.dispatch("commit").catch(() => {});
  assert.equal(controller.state.entry.key.entry, "K23", "a conflict blocks the next action");

  await controller.resolveConflict("keep_local");
  assert.equal(controller.state.conflict, null);
  assert.equal(controller.state.draft.claims.description.value.text, "Min lokale tekst.", "the choice kept the local draft");
  assert.equal(controller.state.status, "dirty", "keeping local text requires a new, deliberate write");
  await controller.flush();
  assert.equal(controller.state.status, "saved");

  // Loading the server version is the other explicit choice.
  const other = harness({ prefix: "c" });
  await other.controller.start();
  await other.controller.select(key("K23"));
  other.controller.editClaim("version", { value: "forkastes" });
  other.adapter.simulation.arm("revision_conflict");
  await other.controller.flush().catch(() => {});
  await other.controller.resolveConflict("load_server");
  assert.equal(other.controller.state.draft.claims.version.value, "1.10", "the server version replaced the draft on request");
  assert.equal(other.controller.state.status, "idle");
""")

    def test_shortcuts_fire_outside_text_entry_only(self):
        """Work order case 7: shortcuts stay out of typing, composition, repeats and browser chords."""
        self.run_behaviour("""
  const body = { tagName: "BODY", isContentEditable: false };
  assert.equal(curatorActionForEvent({ key: "g", target: body }), "commit");
  assert.equal(curatorActionForEvent({ key: "G", target: body }), "commit");
  assert.equal(curatorActionForEvent({ key: "h", target: body }), "defer");
  assert.equal(curatorActionForEvent({ key: "z", target: body }), "undo");
  assert.equal(curatorActionForEvent({ key: "ArrowRight", target: body }), "next");
  assert.equal(curatorActionForEvent({ key: "ArrowLeft", target: body }), "previous");
  assert.equal(curatorActionForEvent({ key: "?", target: body }), "shortcuts");

  for (const tagName of ["INPUT", "TEXTAREA", "SELECT"]) {
    assert.equal(curatorActionForEvent({ key: "g", target: { tagName } }), null, `${tagName} keeps its own keys`);
  }
  assert.equal(curatorActionForEvent({ key: "g", target: { tagName: "DIV", isContentEditable: true } }), null);
  assert.equal(curatorActionForEvent({ key: "g", target: body, isComposing: true }), null, "text composition is not a shortcut");
  assert.equal(curatorActionForEvent({ key: "g", target: body, keyCode: 229 }), null, "an IME keycode is not a shortcut");
  assert.equal(curatorActionForEvent({ key: "g", target: body, repeat: true }), null, "held keys do not repeat a decision");
  for (const chord of ["ctrlKey", "metaKey", "altKey"]) {
    assert.equal(curatorActionForEvent({ key: "g", target: body, [chord]: true }), null, "browser chords are not overridden");
  }
  assert.equal(curatorActionForEvent({ key: "F5", target: body }), null);

  // Every advertised hint maps to a real action, so keys and buttons share one code.
  for (const hint of CURATOR_SHORTCUT_HINTS) {
    assert.ok(Object.values(CURATOR_ACTIONS).includes(hint.action), `${hint.keys} is a real action`);
  }

  // The shortcut reaches the controller that the buttons use.
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  await controller.dispatch(curatorActionForEvent({ key: "g", target: body }));
  const approved = await adapter.getEntry({ key: key("K23") });
  assert.equal(approved.queue_state, "reviewed", "the keyboard used the same action code as the button");
""")

    def test_open_fields_and_unreachable_sources_stay_visible_without_blocking_the_queue(self):
        """Work order case 8: uncertainty is shown, and a broken entry does not stop the rest."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  adapter.simulation.setOverlay("K4", "media_unavailable");
  await controller.start();
  await controller.select(key("K4"));

  const codes = controller.state.entry.issues.map(issue => issue.code);
  assert.ok(codes.includes("media_unavailable"), "the unavailable source is visible");
  assert.ok(codes.includes("unsupported_archive"), "the undecoded Gentee package stays visible");
  assert.ok(codes.includes("identity_provisional"), "a provisional identity is not presented as settled");
  assert.equal(controller.state.entry.source.members.length, 4, "preserved metadata is still usable");
  assert.equal(controller.state.entry.source.title, "Blockout");
  assert.deepEqual(
    controller.state.items.find(item => item.key.entry === "K4").open_fields.sort(),
    ["distribution_kind", "identity", "version"],
    "open fields are listed per claim",
  );

  // Reviewing an entry with an unknown version is allowed and stays an open field.
  await controller.select(key("K23"));
  await controller.dispatch("commit");
  const reviewed = await adapter.getEntry({ key: key("K23") });
  assert.equal(reviewed.queue_state, "reviewed", "the rest of the queue is processable");
  assert.equal(reviewed.accepted.claims.distribution_kind.assessment, "unresolved");
  assert.ok(
    reviewed.issues.some(issue => issue.field === "distribution_kind"),
    "reviewed does not mean every field is resolved",
  );
  assert.equal(reviewed.accepted.identification_status, "curated");

  // A read failure is reported, not hidden behind an empty entry.
  adapter.simulation.setOverlay("K4", "read_permission_denied");
  const denied = await adapter.getEntry({ key: key("K4") });
  assert.ok(denied.issues.some(issue => issue.code === "read_permission_denied"));
  assert.equal(denied.source.members.length, 4);
""")

    def test_a_late_autosave_receipt_cannot_mark_newer_input_as_saved(self):
        """Work order case 9: a receipt only reports what it carried."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));

  controller.editClaim("version", { value: "1.10-first" });
  const held = adapter.simulation.hold();
  // save() is the single write whose receipt is under test; flush() deliberately settles.
  const saving = controller.save();
  await held.arrived;
  assert.equal(controller.state.status, "saving");

  // The curator keeps typing while the first save is still on its way back.
  controller.editClaim("version", { value: "1.10-second" });
  held.release();
  await saving;

  assert.notEqual(controller.state.status, "saved", "the late receipt did not claim the newer text was saved");
  assert.equal(controller.state.status, "dirty");
  assert.equal(controller.state.draft.claims.version.value, "1.10-second", "the newer input survived");
  const stored = await adapter.getEntry({ key: key("K23") });
  assert.equal(stored.draft.claims.version.value, "1.10-first", "only the carried draft was written");

  // The follow-up save is what makes the newer text durable.
  await controller.flush();
  assert.equal(controller.state.status, "saved");
  const settled = await adapter.getEntry({ key: key("K23") });
  assert.equal(settled.draft.claims.version.value, "1.10-second");
""")

    def test_a_late_save_receipt_never_lands_on_another_entry(self):
        """Review #27 P1: a write is bound to the entry it was sent for."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  assert.equal(controller.state.entry.key.entry, "K4");
  const original = JSON.parse(JSON.stringify(controller.state.draft.claims.version));

  controller.editClaim("version", { value: "endret" });
  const held = adapter.simulation.hold();
  const saving = controller.save();
  await held.arrived;

  // The curator undoes the edit by hand, so the draft looks clean again, and moves on
  // while K4's write is still out.
  controller.editClaim("version", original);
  const selecting = controller.select(key("K23"));
  held.release();
  await saving;
  await selecting;

  assert.equal(controller.state.entry.key.entry, "K23", "the selected entry is the one on screen");
  assert.equal(controller.state.draft.claims.identity.value.name, "CPU-Z", "its draft belongs to it");
  assert.equal(controller.state.entry.draft.claims.identity.value.name, "CPU-Z", "the late receipt did not replace the entry");

  // Whatever is saved next must not carry CPU-Z's claims onto K4.
  controller.editClaim("description", { value: { language: "nb-NO", text: "Ny tekst for K23." } });
  await controller.flush();

  const k4 = await adapter.getEntry({ key: key("K4") });
  const k23 = await adapter.getEntry({ key: key("K23") });
  assert.equal(k4.draft.claims.identity.value.name, "Blockout", "K4 kept its own identity");
  assert.equal(k4.draft.claims.version.value, original.value, "K4 kept its own version");
  assert.equal(k23.draft.claims.identity.value.name, "CPU-Z", "K23 kept its own identity");
  assert.equal(k23.draft.claims.description.value.text, "Ny tekst for K23.", "the edit landed on K23");
""")

    def test_retry_resends_the_original_operation_for_every_mutation(self):
        """Review #27 P2: a retry reaches the adapter and the original receipt is processed."""
        self.run_behaviour("""
  for (const kind of ["approve", "defer", "undo"]) {
    const { adapter, controller } = harness({ prefix: kind });
    await controller.start();
    await controller.setFilter("all");
    await controller.select(key("K23"));
    if (kind === "undo") {
      await controller.dispatch("commit");
      await controller.setFilter("all");
      await controller.select(key("K23"));
    }

    const seen = [];
    const real = adapter[kind];
    adapter[kind] = request => {
      seen.push(request);
      return real(request);
    };

    adapter.simulation.arm("timeout_after_commit");
    const action = kind === "approve" ? "commit" : kind;
    await controller.dispatch(action, kind === "defer" ? "Undersøk senere" : undefined).catch(() => {});

    assert.equal(controller.state.status, "error", `${kind}: the timeout is reported`);
    assert.ok(controller.state.pendingRetry, `${kind}: a retry is offered`);
    assert.equal(controller.state.pendingRetry.kind, kind);
    assert.equal(seen.length, 1, `${kind}: one attempt so far`);

    await controller.dispatch("retry");

    assert.equal(seen.length, 2, `${kind}: the retry reached the adapter`);
    assert.deepEqual(seen[1], seen[0], `${kind}: the retry sent an identical request`);
    assert.equal(controller.state.pendingRetry, null, `${kind}: the retry cleared`);
    assert.notEqual(controller.state.status, "error", `${kind}: the original receipt was processed`);

    const entry = await adapter.getEntry({ key: key("K23") });
    assert.equal(entry.history.filter(event => event.kind === kind).length, 1, `${kind}: decided exactly once`);
  }

  // After a committed approve, the screen advances on the retry rather than staying put.
  const { adapter, controller } = harness({ prefix: "advance" });
  await controller.start();
  await controller.select(key("K23"));
  adapter.simulation.arm("timeout_after_commit");
  await controller.dispatch("commit").catch(() => {});
  assert.equal(controller.state.entry.key.entry, "K23", "no advance while the outcome is unknown");
  await controller.dispatch("retry");
  assert.notEqual(controller.state.entry.key.entry, "K23", "the confirmed decision advances the queue");
""")

    def test_a_refused_browser_store_is_a_failed_write_not_a_saved_draft(self):
        """Review #27 P3: storage that rejects the write must not report a saved draft."""
        self.run_behaviour("""
  const storage = memoryStorage();
  const adapter = createFixtureAdapter({ fixture, storage });
  assert.equal(adapter.durable, true, "storage is available at startup");
  const entry = await adapter.getEntry({ key: key("K23") });

  // The store starts refusing writes, as a full quota does mid-session.
  storage.setItem = () => { throw new Error("QuotaExceededError"); };

  const draft = JSON.parse(JSON.stringify(entry.draft));
  draft.claims.version.value = "CHANGED";
  await assert.rejects(
    adapter.saveDraft({ key: entry.key, expected_revision: entry.revision, operation_id: "quota-1", draft }),
    error => error.code === "write_failed" && error.retryable === true,
    "a refused store is a failed write",
  );

  const live = await adapter.getEntry({ key: key("K23") });
  assert.equal(live.draft.claims.version.value, "1.10", "the in-memory state was rolled back");
  assert.equal(live.revision, entry.revision, "no revision was spent on a write that did not happen");
  const reloaded = await createFixtureAdapter({ fixture, storage }).getEntry({ key: key("K23") });
  assert.equal(reloaded.draft.claims.version.value, "1.10", "nothing was promised that a reload would lose");

  // An approval is refused the same way, and stays unapproved.
  await assert.rejects(
    adapter.approve({ key: entry.key, expected_revision: live.revision, operation_id: "quota-2" }),
    error => error.code === "write_failed",
  );
  assert.equal((await adapter.getEntry({ key: key("K23") })).queue_state, "pending", "nothing was decided");

  // The controller keeps the edit and refuses to advance.
  const { adapter: live2, controller } = harness({ prefix: "quota" });
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("version", { value: "1.10-lokal" });
  live2.saveDraft = () => Promise.reject({ code: "write_failed", message: "Nettleserlagringen avviste skrivingen.", retryable: true, field_errors: {}, current_entry: null });
  await controller.dispatch("commit").catch(() => {});
  assert.equal(controller.state.status, "error");
  assert.equal(controller.state.draft.claims.version.value, "1.10-lokal", "the edit is kept on screen");
  assert.equal(controller.state.entry.key.entry, "K23", "a failed store stops the advance");

  // With no storage at all the adapter says so, so the page can state it.
  const ephemeral = createFixtureAdapter({ fixture, storage: null });
  assert.equal(ephemeral.durable, false, "an ephemeral session is explicit, not silent");
  await ephemeral.saveDraft({ key: entry.key, expected_revision: entry.revision, operation_id: "ephemeral-1", draft });
""")

    def test_contract_validation_refuses_guesses_and_unsupported_claims(self):
        """ADR-005: unknown stays unknown, and an approval cannot certify an unsupported claim."""
        self.run_behaviour("""
  const entry = fixture.entries.find(item => item.key.entry === "K23");
  const base = () => JSON.parse(JSON.stringify(entry.draft));

  assert.deepEqual(validateDraft(base(), entry.evidence), {}, "the fixture draft is valid as delivered");

  const coerced = base();
  coerced.claims.distribution_kind.assessment = "accepted";
  assert.ok(validateDraft(coerced, entry.evidence).distribution_kind, "unknown distribution cannot be approved as settled");

  const guessedVersion = base();
  guessedVersion.claims.version.value = "unknown";
  guessedVersion.claims.version.assessment = "accepted";
  assert.ok(validateDraft(guessedVersion, entry.evidence).version, "an unknown version cannot be marked supported");

  const retained = base();
  retained.claims.version.value = "unknown";
  retained.claims.version.assessment = "unresolved";
  retained.claims.version.reason = "Produktversjonen er ikke fastslått i kilden.";
  assert.deepEqual(validateDraft(retained, entry.evidence), {}, "documented uncertainty is a valid review outcome");

  const silent = base();
  silent.claims.version.assessment = "unresolved";
  silent.claims.version.reason = "";
  assert.ok(validateDraft(silent, entry.evidence).version, "an unresolved claim needs a reason");

  const unsupported = base();
  unsupported.claims.identity.evidence_ids = [];
  assert.ok(validateDraft(unsupported, entry.evidence).identity, "a supported claim needs evidence");

  const invented = base();
  invented.claims.identity.evidence_ids = ["K23-e99"];
  assert.ok(validateDraft(invented, entry.evidence).identity, "evidence IDs are checked against the entry");

  const blank = base();
  blank.claims.description.value = { language: "nb-NO", text: "   " };
  assert.ok(validateDraft(blank, entry.evidence).description);

  // A rename with a null ID that collides with a shared record is rejected, not applied.
  const { adapter, controller } = harness();
  await controller.start();
  await controller.setFilter("all");
  await controller.select(key("K4"));
  controller.editClaim("identity", { value: { software_id: null, name: "CPU-Z" }, assessment: "accepted" });
  await controller.flush();
  await controller.dispatch("commit").catch(() => {});
  assert.equal(controller.state.error.code, "shared_record_conflict");
  assert.equal(controller.state.draft.claims.identity.value.name, "CPU-Z", "the edit is kept for a separate resolution");
  const untouched = await adapter.getEntry({ key: key("K4") });
  assert.equal(untouched.queue_state, "pending", "no shared record was renamed implicitly");
""")

    def test_fixture_mode_is_explicit_and_resettable_and_namespaced(self):
        """ADR-004: fixture state is visibly simulated, namespaced and never a silent fallback."""
        self.run_behaviour("""
  const storage = memoryStorage();
  const adapter = createFixtureAdapter({ fixture, storage, datasetId: "curator-fixtures-v1" });
  assert.equal(adapter.fixtureMode, true, "the adapter states that it is fixture mode");
  assert.equal(adapter.schema, "bootdisk-curator-v1");

  await adapter.saveDraft({
    key: key("K23"),
    expected_revision: (await adapter.getEntry({ key: key("K23") })).revision,
    operation_id: "namespace-1",
    draft: (await adapter.getEntry({ key: key("K23") })).draft,
  });
  assert.ok(storage.getItem("bootdisk-curator-v1/v1/curator-fixtures-v1"), "storage is namespaced by schema and dataset");

  await adapter.approve({ key: key("K23"), expected_revision: (await adapter.getEntry({ key: key("K23") })).revision, operation_id: "namespace-2" });
  assert.equal((await adapter.getEntry({ key: key("K23") })).queue_state, "reviewed");
  adapter.reset();
  const afterReset = await adapter.getEntry({ key: key("K23") });
  assert.equal(afterReset.queue_state, "pending", "an explicit reset returns to the fixture baseline");
  assert.equal(afterReset.revision, "fixture-K23-0");

  // A simulated fault is armed deliberately and consumed once; it never flips silently.
  assert.equal(adapter.simulation.armed(), null);
  adapter.simulation.arm("service_unavailable");
  assert.equal(adapter.simulation.armed(), "service_unavailable");
  await assert.rejects(
    adapter.saveDraft({ key: key("K23"), expected_revision: afterReset.revision, operation_id: "fault-1", draft: afterReset.draft }),
    error => error.code === "service_unavailable" && error.retryable === true,
  );
  assert.equal(adapter.simulation.armed(), null, "the simulated fault is not sticky");
  assert.throws(() => adapter.simulation.arm("silently_succeed"), /Ukjent simulering/);

  // The fixture bundle itself is never mutated by the adapter.
  assert.equal(fixture.entries.find(item => item.key.entry === "K23").queue_state, "pending");
  assert.equal(fixture.fixture_only, true);
""")

    def test_resume_bookmark_does_not_change_review_status(self):
        """The contract's resume key is a bookmark, not a decision."""
        self.run_behaviour("""
  const storage = memoryStorage();
  const first = harness({ storage, prefix: "r" });
  await first.controller.start();
  assert.equal(first.controller.state.entry.key.entry, "K4", "the first pending entry opens by default");
  await first.controller.select(key("K23"));

  const second = harness({ storage, prefix: "q" });
  await second.controller.start();
  assert.equal(second.controller.state.entry.key.entry, "K23", "the last visited entry is resumed");
  assert.equal(second.controller.state.entry.queue_state, "pending", "resuming did not review the entry");

  // A resume key outside the active filter falls back to the first item.
  await second.controller.dispatch("defer", "Utsatt for å teste gjenopptakelse");
  const third = harness({ storage, prefix: "p" });
  await third.controller.start();
  assert.ok(third.controller.state.entry, "a filtered-out bookmark still opens an entry");
  assert.equal(third.controller.state.entry.queue_state, "pending");
""")

    def test_queue_filters_counts_and_completion(self):
        """The queue separates reviewed from resolved and reports an explicit ending."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  assert.deepEqual(controller.state.items.map(item => item.key.entry), ["K4", "K23"], "numeric source order");
  assert.equal(controller.state.summary.total, 2);
  assert.equal(controller.state.summary.reviewed, 0);
  assert.equal(controller.state.summary.open_fields, 2);

  await controller.select(key("K23"));
  await controller.dispatch("commit");
  assert.equal(controller.state.summary.reviewed, 1, "one entry has been through a review pass");
  assert.equal(controller.state.summary.open_fields, 2, "both still carry an unresolved claim");
  assert.equal(controller.state.items.length, 1, "counts describe the loaded filter");

  await controller.select(key("K4"));
  await controller.dispatch("commit").catch(() => {});
  assert.equal(controller.state.complete, true, "an empty queue shows a clear ending");
  assert.equal(controller.state.entry, null);

  await controller.setFilter("all");
  assert.equal(controller.state.complete, false);
  assert.equal(controller.state.items.length, 2);
  await controller.setFilter("open_fields");
  assert.equal(controller.state.items.length, 2, "reviewed entries keep their open fields");
""")


class CuratorSourceRulesTests(unittest.TestCase):
    def test_fixture_bundle_is_the_unchanged_catalog_document(self):
        fixture_path = ROOT / "tests" / "fixtures" / "curator-fixtures-v1.json"
        digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
        self.assertEqual(digest, FIXTURE_SHA256, "the fixture bundle must stay byte-identical to Catalog's")
        document = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], "bootdisk-curator-v1")
        self.assertTrue(document["fixture_only"])
        readme = (ROOT / "tests" / "fixtures" / "README.md").read_text(encoding="utf-8")
        self.assertIn(CATALOG_COMMIT, readme, "the README records the Catalog commit it came from")
        self.assertIn(FIXTURE_SHA256, readme)

    def test_curator_renders_source_text_as_text_only(self):
        for name in ("curate.js", "curate-core.js", "curate-adapter.js"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("innerHTML", source, f"{name} must not inject markup")
            self.assertNotIn("outerHTML", source)
            self.assertNotIn("insertAdjacentHTML", source)
            self.assertNotIn("document.write", source)
        page = (ROOT / "curate.html").read_text(encoding="utf-8")
        self.assertIn('name="robots" content="noindex"', page, "the local curator is not a public page")
        self.assertIn('class="skip-link" href="#main-content"', page)
        self.assertIn('id="main-content"', page)
        self.assertIn("<noscript>", page)
        self.assertIn('href="accessibility.css"', page)
        self.assertIn('role="alert"', page)
        self.assertIn('aria-live="polite"', page)

    def test_fixture_mode_is_labelled_on_the_page(self):
        page = (ROOT / "curate.html").read_text(encoding="utf-8")
        self.assertIn("Prøvedata – endrer ikke katalogen", page)
        self.assertIn('id="fixture-banner"', page)

    def test_public_release_excludes_the_curator_and_its_fixtures(self):
        """Work order case 10: the curator never reaches the public release allowlist."""
        builder = (ROOT / "scripts" / "build-release.py").read_text(encoding="utf-8")
        allowlist = builder.split("STATIC_FILES = (")[1].split(")")[0]
        for forbidden in ("curate", "fixture"):
            self.assertNotIn(forbidden, allowlist, f"{forbidden} must stay out of the release allowlist")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontend = root / "data"
            publish = root / "publish"
            output = root / "release"
            frontend.mkdir()
            publish.mkdir()
            (frontend / "index.json").write_text(json.dumps({
                "publication": "Test",
                "medium": "Test medium",
                "entries": [{"entry": "K1", "curation_status": "identified"}],
            }), encoding="utf-8")
            (frontend / "k1.json").write_text(json.dumps({
                "entry": "K1",
                "publication": "Test",
                "medium": "Test medium",
                "curation_status": "identified",
                "software": [],
                "assets": [],
            }), encoding="utf-8")

            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build-release.py"), str(frontend), str(publish),
                 "--output", str(output), "--expected-entries", "1"],
                check=True, capture_output=True, text=True,
            )

            published = {path.name for path in output.rglob("*") if path.is_file()}
            for name in ("curate.html", "curate.js", "curate-core.js", "curate-adapter.js", "curate.css", "curator-fixtures-v1.json"):
                self.assertNotIn(name, published, f"{name} must not be published")
            self.assertIn("archive.html", published, "the existing public archive still builds")
            self.assertFalse((output / "tests").exists(), "test fixtures are not part of a release")


if __name__ == "__main__":
    unittest.main()
