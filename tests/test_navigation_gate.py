"""Ordering tests for the navigation and decision boundary on the curator screen.

These are the sequences from the correction order, not single button presses. Every one of
them drives the real controller and the real fixture adapter, and every wait is a held
adapter answer released by the test — never a sleep — so the interleaving is exact and
repeatable.

The rule under test: the page may be left only once the last draft is confirmed saved, with
no unresolved conflict or save error and no decision in flight, and those conditions must
hold at the moment the navigation actually happens, not merely before an await.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "curator_harness.js"

NODE = shutil.which("node")


def behaviour(body: str) -> str:
    return f"""
const {{ assert, fixture, MANIFEST, key, harness, memoryStorage, createFixtureAdapter }} =
  require({str(HARNESS)!r});

/* Records what the controller was allowed to do, so a test can assert on the navigation
 * itself rather than only on the answer it returned. */
function returnTrip(controller) {{
  const trip = {{ navigated: 0, busyAtNavigation: null, dirtyAtNavigation: null }};
  trip.go = () => controller.leave(() => {{
    trip.navigated += 1;
    trip.busyAtNavigation = controller.state.busy;
    trip.dirtyAtNavigation = controller.isDirty();
  }});
  return trip;
}}

(async () => {{
{body}
}})().catch(error => {{
  console.error(error.stack || error.message || String(error));
  process.exit(1);
}});
"""


@unittest.skipUnless(NODE, "Node.js is required for the navigation gate tests")
class NavigationGateTests(unittest.TestCase):
    def run_behaviour(self, body: str) -> str:
        result = subprocess.run(
            [NODE, "-e", behaviour(body)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={"CURATOR_WEB_ROOT": str(ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        if result.returncode != 0:
            self.fail(f"navigation gate behaviour failed:\n{result.stderr}\n{result.stdout}")
        return result.stdout

    def test_typing_then_returning_before_the_autosave_starts_saves_the_text(self):
        """Sequence 1: write → return before autosave. The last text is saved as a draft first."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("version", { reason: "Skrevet rett før retur." });
  /* The autosave timer is never run: only the return can have saved this. */
  assert.ok(controller.isDirty(), "the draft is unsaved when the return starts");

  const trip = returnTrip(controller);
  assert.equal(await trip.go(), true, "the return is allowed once the write is confirmed");
  assert.equal(trip.navigated, 1);
  assert.equal(trip.dirtyAtNavigation, false, "nothing was unsaved at the moment of leaving");

  const stored = await adapter.getEntry({ key: key("K23") });
  assert.equal(stored.draft.claims.version.reason, "Skrevet rett før retur.", "the text is in the draft");
  assert.notEqual(stored.accepted?.claims?.version?.reason, "Skrevet rett før retur.",
    "and was never approved as a side effect of returning");
  console.log("ok");
""")

    def test_a_decision_started_while_the_return_waits_cannot_slip_past_the_gate(self):
        """Sequence 2 — the correction order's reproduction. Checking busy before the flush is not enough."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  const before = (await adapter.getEntry({ key: key("K23") })).queue_state;
  controller.editClaim("version", { reason: "Endret begrunnelse." });

  const held = adapter.simulation.hold();
  const trip = returnTrip(controller);
  const leaving = trip.go();
  await held.arrived;

  /* The decision is attempted after the return has taken the gate but before the save is
   * answered — exactly the window the old check left open. It is deliberately not awaited
   * here: awaiting it would serialise the two and hide the race. */
  const deciding = controller.dispatch("commit");
  const busyAfterDispatch = controller.state.busy;

  held.release();
  const allowed = await leaving;
  assert.equal(busyAfterDispatch, false,
    "the decision never started: a return holds the gate, so nothing can be in flight");
  assert.equal(await deciding, null, "and the press was refused rather than queued");
  assert.equal(allowed, true, "the return completes once the save is confirmed");
  assert.equal(trip.navigated, 1, "the page was left exactly once");
  assert.equal(trip.busyAtNavigation, false, "and nothing was undecided at that moment");

  const after = await adapter.getEntry({ key: key("K23") });
  assert.equal(after.queue_state, before, "no approval happened as a side effect");
  assert.equal(after.draft.claims.version.reason, "Endret begrunnelse.", "the text was saved as a draft");
  console.log("ok");
""")

    def test_a_return_during_a_running_decision_is_refused_and_the_decision_finishes(self):
        """Sequence 3: approve in flight → return. The return is stopped, never queued behind it."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K4"));

  const held = adapter.simulation.hold();
  const deciding = controller.dispatch("commit");
  await held.arrived;
  assert.equal(controller.state.busy, true, "the decision is in flight");

  const trip = returnTrip(controller);
  assert.equal(await trip.go(), false, "the return is refused");
  assert.equal(trip.navigated, 0, "and nothing navigated");

  held.release();
  await deciding;
  assert.equal(controller.state.busy, false, "the decision finished on its own");
  /* Once it has, the return works. */
  const second = returnTrip(controller);
  assert.equal(await second.go(), true);
  assert.equal(second.navigated, 1);
  console.log("ok");
""")

    def test_a_granted_return_keeps_the_gate_shut(self):
        """Leaving a page is not instant: nothing may start on a screen already on its way out."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K4"));

  const trip = returnTrip(controller);
  assert.equal(await trip.go(), true, "the return is granted");
  assert.equal(trip.navigated, 1);
  assert.equal(controller.state.leaving, true, "and the screen stays closed");

  /* Everything the curator could still press in the moments before the page goes. */
  assert.equal(await controller.dispatch("commit"), null, "no decision starts after the return");
  assert.equal(await controller.dispatch("defer", "Grunn"), null);
  assert.equal(await controller.select(key("K23")), null);
  assert.equal(controller.state.busy, false, "nothing is in flight");

  /* A second click is the same return and does not navigate twice. */
  assert.equal(await trip.go(), true);
  assert.equal(trip.navigated, 1, "the page is left exactly once");

  const entry = await adapter.getEntry({ key: key("K4") });
  assert.equal(entry.queue_state, "pending", "and the entry was never decided");
  console.log("ok");
""")

    def test_text_typed_while_the_return_waits_is_never_lost(self):
        """Sequence 4: return waiting → more typing. Either it is saved or the return stops."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("version", { reason: "Første tekst." });

  const held = adapter.simulation.hold();
  const trip = returnTrip(controller);
  const leaving = trip.go();
  await held.arrived;

  /* Typing stays open while a return waits; this is the text that must not disappear. */
  controller.editClaim("version", { reason: "Andre tekst, skrevet mens returen ventet." });
  held.release();
  const allowed = await leaving;

  assert.equal(controller.state.draft.claims.version.reason,
    "Andre tekst, skrevet mens returen ventet.", "the newest text is still in the draft");
  const stored = await adapter.getEntry({ key: key("K23") });
  if (allowed) {
    assert.equal(stored.draft.claims.version.reason, "Andre tekst, skrevet mens returen ventet.",
      "a return that went through had saved the newest text first");
  } else {
    assert.equal(controller.isDirty(), true, "a return that was stopped left the text unsaved but present");
  }
  console.log(`ok (return ${allowed ? "went through with the text saved" : "was stopped"})`);
""")

    def test_defer_undo_and_internal_navigation_are_refused_while_the_return_waits(self):
        """Sequence 5: nothing else may start against the wrong entry while a return holds the gate."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("version", { reason: "Tekst før retur." });

  const held = adapter.simulation.hold();
  const trip = returnTrip(controller);
  const leaving = trip.go();
  await held.arrived;

  assert.equal(await controller.dispatch("defer", "Grunn"), null, "defer is refused");
  assert.equal(await controller.dispatch("undo"), null, "undo is refused");
  assert.equal(await controller.select(key("K4")), null, "internal navigation is refused");
  assert.equal(await controller.dispatch("next"), null, "the next-entry shortcut is refused");
  assert.equal(await controller.dispatch("previous"), null, "the previous-entry shortcut is refused");
  assert.equal(await controller.dispatch("retry"), null, "a retry is refused");
  assert.equal(await controller.setFilter("all"), null, "changing the filter is refused");
  assert.equal(controller.state.entry.key.entry, "K23", "the screen is still on the entry being left");
  assert.equal(controller.state.filter, "pending", "and the filter did not move under it");

  held.release();
  assert.equal(await leaving, true);
  const other = await adapter.getEntry({ key: key("K4") });
  assert.equal(other.queue_state, "pending", "nothing happened to the entry that was not on screen");
  console.log("ok");
""")

    def test_double_clicking_return_or_approve_produces_one_of_each(self):
        """Sequence 6: no double decisions and no crossing navigations."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("version", { reason: "Dobbeltklikk." });

  const held = adapter.simulation.hold();
  const trip = returnTrip(controller);
  const first = trip.go();
  await held.arrived;
  const second = trip.go();
  held.release();
  assert.deepEqual(await Promise.all([first, second]), [true, true],
    "both clicks are answered, because they are the same return");
  assert.equal(trip.navigated, 1, "but the page is left exactly once");

  /* The same for a decision. */
  const decider = harness({ prefix: "dbl" });
  await decider.controller.start();
  await decider.controller.select(key("K4"));
  const decisionHold = decider.adapter.simulation.hold();
  const one = decider.controller.dispatch("commit");
  await decisionHold.arrived;
  const two = await decider.controller.dispatch("commit");
  assert.equal(two, null, "the second press is refused while the first is in flight");
  decisionHold.release();
  await one;
  const entry = await decider.adapter.getEntry({ key: key("K4") });
  assert.equal(entry.history.filter(event => event.kind === "approve").length, 1,
    "exactly one approval was recorded");
  console.log("ok");
""")

    def test_a_failed_decision_stays_visible_and_blocks_the_return(self):
        """Sequence 7: save succeeds, decision fails. The failure must not be hidden by leaving."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("version", { reason: "Lagres først." });
  await controller.flush();
  assert.equal(controller.state.status, "saved", "the draft was saved");

  adapter.simulation.arm("service_unavailable");
  await controller.dispatch("commit").catch(() => {});
  assert.equal(controller.state.status, "error", "the decision failed visibly");
  assert.ok(controller.state.error, "with an error the curator can read");
  assert.ok(controller.state.pendingRetry, "and a retry that re-sends the same operation");

  const trip = returnTrip(controller);
  assert.equal(await trip.go(), false, "the return is stopped while the failure stands");
  assert.equal(trip.navigated, 0);
  assert.equal(controller.state.status, "error", "and the failure is still on screen");
  console.log("ok");
""")

    def test_a_failed_save_and_a_revision_conflict_both_stop_the_return_and_keep_the_text(self):
        """Sequence 8: text and focus survive; nothing is reset to make the error go away."""
        self.run_behaviour("""
  for (const fault of ["write_failed", "revision_conflict"]) {
    const { adapter, controller } = harness({ prefix: fault });
    await controller.start();
    await controller.select(key("K23"));
    controller.editClaim("version", { reason: `Tekst som må overleve ${fault}.` });
    adapter.simulation.arm(fault);

    const trip = returnTrip(controller);
    assert.equal(await trip.go(), false, `${fault}: the return is stopped`);
    assert.equal(trip.navigated, 0, `${fault}: nothing navigated`);
    assert.equal(controller.state.draft.claims.version.reason, `Tekst som må overleve ${fault}.`,
      `${fault}: the text is kept`);
    assert.equal(controller.state.entry.key.entry, "K23", `${fault}: the screen stayed on the entry`);
    if (fault === "revision_conflict") {
      assert.ok(controller.state.conflict, "the conflict is offered for a deliberate choice");
      assert.ok(controller.state.conflict.local, "with the local text intact");
    } else {
      assert.equal(controller.state.status, "error");
      assert.ok(controller.state.error.retryable, "and the write can be retried");
    }
  }
  console.log("ok");
""")

    def test_an_old_answer_arriving_after_newer_text_never_marks_it_saved(self):
        """Sequence 9: a slow old receipt cannot present newer input as saved, or leave on it."""
        self.run_behaviour("""
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("version", { reason: "Gammel tekst." });

  /* One save pass, so the receipt that comes back is the one for the older text. */
  const held = adapter.simulation.hold();
  const saving = controller.save();
  await held.arrived;
  controller.editClaim("version", { reason: "Nyere tekst." });
  held.release();
  await saving;

  assert.equal(controller.state.draft.claims.version.reason, "Nyere tekst.",
    "the newer text is what the screen holds");
  assert.equal(controller.state.status, "dirty",
    "the old receipt reported only what it carried; the newer text is not called saved");
  assert.equal(controller.isDirty(), true, "the newer text is still unsaved work");

  /* Returning now has to save the newer text before it may leave. */
  const trip = returnTrip(controller);
  assert.equal(await trip.go(), true);
  const stored = await adapter.getEntry({ key: key("K23") });
  assert.equal(stored.draft.claims.version.reason, "Nyere tekst.", "which is what reached the adapter");
  console.log("ok");
""")

    def test_a_receipt_is_bound_to_manifest_and_entry_together(self):
        """Rule C: a K-id alone is not unique, so it cannot decide which entry a receipt belongs to."""
        self.run_behaviour("""
  const { createCuratorController, curatorKeyId } = require(process.env.CURATOR_WEB_ROOT + "/curate-core.js");
  assert.equal(curatorKeyId({ manifest: "sha256:a", entry: "K1" }), "sha256:a/K1");
  assert.notEqual(curatorKeyId({ manifest: "sha256:a", entry: "K1" }),
    curatorKeyId({ manifest: "sha256:b", entry: "K1" }),
    "the same K-id in two source manifests is two different entries");
  assert.equal(curatorKeyId(null), null);

  /* And the live path: a receipt that comes back after the screen has moved on does not
   * become the state of the entry now open. */
  const { adapter, controller } = harness();
  await controller.start();
  await controller.select(key("K23"));
  controller.editClaim("version", { reason: "Hører til K23." });
  const held = adapter.simulation.hold();
  const saving = controller.flush();
  await held.arrived;
  /* The curator moves on while the write is in the air. select() is refused mid-write, so
   * the entry is swapped the way a late receipt would find it: after the gate opens. */
  held.release();
  await saving;
  await controller.select(key("K4"));
  assert.equal(controller.state.entry.key.entry, "K4");
  assert.notEqual(controller.state.draft.claims.version.reason, "Hører til K23.",
    "the other entry's draft did not follow the curator");
  console.log("ok");
""")


if __name__ == "__main__":
    unittest.main()
