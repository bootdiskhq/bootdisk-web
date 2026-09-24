"""Behaviour tests for the automatic first-pass queue (docs/automation-queue-v1.md).

The JavaScript cases drive the real adapter and the real queue logic through Node over the
contract's own example file and the deterministic 5 000-entry sample, so they check what a
person would see counted, matched and refused, not that a function name exists.
"""
import hashlib
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "automation-queue-v1.json"
CONTRACT = ROOT / "docs" / "automation-queue-v1.md"
NODE = shutil.which("node")

# The copies handed over with the work order of 2026-09-24 (Catalog branch
# feat/automatic-first-pass). Any edit to either file must be a deliberate contract update.
FIXTURE_SHA256 = "2ae1b5369eaa788056133270c6058597d28ab3433114e59f970df8c96bb2cefd"
CONTRACT_SHA256 = "abd3af2885bb45dfb71a8520f1939e096a688f53ffeb03b7943bedf380b56cd8"

QUEUE_FILES = ("automation.html", "automation.css", "automation.js", "automation-core.js",
               "automation-adapter.js", "automation-sample.js")


def script(body: str) -> str:
    return f"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const core = require({str(ROOT / "automation-core.js")!r});
const adapters = require({str(ROOT / "automation-adapter.js")!r});
const sample = require({str(ROOT / "automation-sample.js")!r});
const FIXTURE_TEXT = fs.readFileSync({str(FIXTURE)!r}, "utf8");
const fixture = () => JSON.parse(FIXTURE_TEXT);
const load = doc => adapters.createAutomationTextAdapter(typeof doc === "string" ? doc : JSON.stringify(doc), "test").loadQueue();
async function refused(doc, kind, pattern) {{
  await assert.rejects(load(doc), error => {{
    assert.equal(error.kind, kind, error.message);
    if (pattern) assert.match(error.message, pattern);
    return true;
  }});
}}
async function sampleModel(options) {{
  const docs = await Promise.all(sample.createAutomationSampleSnapshots(options).map(load));
  return core.automationCombine(docs);
}}
(async () => {{
{body}
}})().then(() => process.stdout.write("ok"), error => {{ console.error(error); process.exit(1); }});
"""


@unittest.skipUnless(NODE, "Node.js is required for the queue behaviour tests")
class AutomationQueueBehaviourTests(unittest.TestCase):
    def run_js(self, body: str) -> str:
        result = subprocess.run([NODE, "-e", script(body)], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return result.stdout

    # --- the contract copy ---------------------------------------------------------------

    def test_contract_and_fixture_are_the_copies_handed_over(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), FIXTURE_SHA256)
        self.assertEqual(hashlib.sha256(CONTRACT.read_bytes()).hexdigest(), CONTRACT_SHA256)

    def test_the_contract_example_validates_and_its_summary_is_recounted(self):
        self.run_js("""
const doc = await load(FIXTURE_TEXT);
assert.equal(doc.entries.length, 4);
assert.deepEqual(doc.summary, fixture().summary);
assert.deepEqual(new Set(doc.entries.map(e => e.stage)), new Set(core.AUTOMATION_STAGES));
assert.deepEqual(new Set(doc.entries.flatMap(e => e.fields.map(f => f.status))), new Set(core.AUTOMATION_STATUSES));
// Whitespace and line breaks of the original description survive untouched.
const described = doc.entries[0].fields.find(f => f.field === "description");
assert.equal(described.proposed, "  Original omtale\\r\\n");
assert.equal(described.evidence[0].value, "  Original omtale\\r\\n");
""")

    def test_the_adapter_only_reads(self):
        self.run_js("""
const adapter = adapters.createAutomationTextAdapter(FIXTURE_TEXT, "test");
assert.deepEqual(Object.keys(adapter), ["loadQueue"]);
assert.ok(Object.isFrozen(adapter));
// Validation never changes the document it was given.
const original = fixture();
const before = JSON.stringify(original);
core.automationValidate(original);
assert.equal(JSON.stringify(original), before);
// A file read goes out as a plain GET, and nothing else.
const calls = [];
const file = adapters.createAutomationFileAdapter("q.json", (url, init) => {
  calls.push(init.method);
  return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(FIXTURE_TEXT) });
});
await file.loadQueue();
await file.loadQueue();
assert.deepEqual(calls, ["GET", "GET"]);
""")

    # --- states that must not be confused --------------------------------------------------

    def test_missing_invalid_and_unknown_are_different_errors_and_never_sample_data(self):
        self.run_js("""
const missing = adapters.createAutomationFileAdapter("borte.json",
  () => Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve("") }));
await assert.rejects(missing.loadQueue(), e => e.kind === "missing" && /HTTP 404/.test(e.message));
const offline = adapters.createAutomationFileAdapter("borte.json", () => Promise.reject(new TypeError("Failed to fetch")));
await assert.rejects(offline.loadQueue(), e => e.kind === "missing");

await refused("{", "invalid_json");
await refused("", "invalid_json");
await refused("[]", "invalid_schema");
await refused({ ...fixture(), schema: "bootdisk-automation-queue-2" }, "invalid_schema", /schema/);
await refused({ ...fixture(), mode: "write" }, "invalid_schema", /read_only/);

let doc = fixture(); doc.entries[1].stage = "approved";
await refused(doc, "unknown_value", /approved/);
doc = fixture(); doc.entries[1].fields[0].status = "accepted";
await refused(doc, "unknown_value", /accepted/);
doc = fixture(); doc.entries[1].fields[0].field = "publisher";
await refused(doc, "unknown_value", /publisher/);

doc = fixture(); delete doc.entries[0].fields[0].proposed;
await refused(doc, "invalid_schema", /proposed/);
doc = fixture(); doc.entries[0].fields[0].reason = " ";
await refused(doc, "invalid_schema", /reason/);
doc = fixture(); doc.entries[0].tasks = "ingen";
await refused(doc, "invalid_schema", /tasks/);
doc = fixture(); delete doc.entries[0].fields[0].evidence[0].source_ref;
await refused(doc, "invalid_schema", /source_ref/);
doc = fixture(); doc.entries[0].key.manifest = "sha256:annet";
await refused(doc, "invalid_schema", /key.manifest/);
doc = fixture(); doc.entries[1].key.entry = "K1D1";
await refused(doc, "invalid_schema", /to ganger/);
doc = fixture(); doc.entries[0].tasks[0].field = "description";
doc.entries[0].fields = doc.entries[0].fields.filter(f => f.field !== "description");
doc.summary.field_status_counts.candidate -= 1;
await refused(doc, "invalid_schema", /som posten ikke har/);
""")

    def test_the_summary_must_add_up_and_decisions_stay_zero(self):
        self.run_js("""
let doc = fixture(); doc.summary.human_exceptions = 0;
await refused(doc, "invalid_schema", /human_exceptions/);
doc = fixture(); doc.summary.stage_counts.proposals = 3;
await refused(doc, "invalid_schema", /stage_counts.proposals/);
doc = fixture(); delete doc.summary.field_status_counts.conflict;
await refused(doc, "invalid_schema", /conflict/);
doc = fixture(); doc.summary.automatic_decisions = 4;
await refused(doc, "invalid_schema", /automatic_decisions/);
doc = fixture(); doc.summary.human_decisions = 1;
await refused(doc, "invalid_schema", /human_decisions/);
""")

    def test_an_empty_run_is_valid_and_distinct_from_an_error(self):
        self.run_js("""
const doc = fixture();
doc.entries = [];
doc.summary = core.automationSummary([]);
const loaded = await load(doc);
const model = core.automationCombine([loaded]);
const page = core.automationQuery(model, {});
assert.equal(page.total, 0);
assert.equal(page.matched, 0);
assert.deepEqual(page.items, []);
""")

    # --- sample marking ---------------------------------------------------------------------

    def test_an_explicit_fixture_marking_survives_validation_and_combination(self):
        self.run_js("""
const marked = await load(FIXTURE_TEXT);
assert.equal(fixture().fixture, true, "the contract example is marked");
assert.equal(marked.fixture, true);
assert.match(marked.fixture_note, /syntetiske/);
const model = core.automationCombine([marked]);
assert.equal(model.fixture, true);
assert.deepEqual(model.fixture_notes, [fixture().fixture_note]);
assert.ok(model.entries.every(e => e.fixture === true));

// A real snapshot has no marking and is not turned into sample data.
const real = fixture(); delete real.fixture; delete real.fixture_note;
const plain = await load(real);
assert.equal(plain.fixture, false);
assert.equal(plain.fixture_note, null);
const realModel = core.automationCombine([plain]);
assert.equal(realModel.fixture, false);
assert.ok(realModel.entries.every(e => e.fixture === false));

// A marking that is not a boolean is refused rather than guessed at.
const odd = fixture(); odd.fixture = "true";
await refused(odd, "invalid_schema", /fixture/);
const note = fixture(); note.fixture_note = 3;
await refused(note, "invalid_schema", /fixture_note/);

// The generated sample carries the same explicit marking.
const generated = await Promise.all(sample.createAutomationSampleSnapshots({ manifests: 2, perManifest: 3 }).map(load));
assert.ok(generated.every(doc => doc.fixture === true));
""")

    def test_sample_and_real_snapshots_are_never_counted_together(self):
        self.run_js("""
const real = sample.createAutomationSampleSnapshots({ manifests: 2, perManifest: 3 }).map(doc => {
  delete doc.fixture; delete doc.fixture_note; return doc;
});
const realDocs = await Promise.all(real.map(load));
const both = core.automationCombine(realDocs);
assert.equal(both.fixture, false, "two real files stay real");
const marked = await load(FIXTURE_TEXT);
assert.throws(() => core.automationCombine([realDocs[0], marked]),
  e => e.kind === "mixed_fixture" && /1 av 2/.test(e.message));
assert.throws(() => core.automationCombine([marked, ...realDocs]), e => e.kind === "mixed_fixture");
""")

    # --- human work versus machine work ----------------------------------------------------

    def test_only_needs_review_can_ask_for_a_human(self):
        self.run_js("""
let doc = fixture();
const inspecting = doc.entries.find(e => e.stage === "inspecting");
inspecting.requires_human = true; doc.summary.human_exceptions = 2;
await refused(doc, "invalid_schema", /requires_human/);
doc = fixture();
doc.entries.find(e => e.stage === "needs_review").requires_human = false; doc.summary.human_exceptions = 0;
await refused(doc, "invalid_schema", /requires_human/);
""")

    def test_machine_tasks_are_never_counted_as_human_work(self):
        self.run_js("""
const model = core.automationCombine([await load(FIXTURE_TEXT)]);
assert.equal(model.summary.machine_tasks, 3);
assert.equal(model.summary.human_exceptions, 1);
// The entry with three machine tasks does not show up when asking what needs a person.
const human = core.automationQuery(model, { stage: "needs_review" });
assert.deepEqual(human.items.map(e => e.key.entry), ["EXAMPLE3"]);
assert.equal(human.humanMatched, 1);
const machine = core.automationQuery(model, { stage: "inspecting" });
assert.equal(machine.humanMatched, 0);
assert.equal(machine.tasksMatched, 3);

// First-pass-1 as delivered: only proposals and inspecting. No human work, but not done.
const firstPass = fixture();
firstPass.entries = firstPass.entries.filter(e => e.stage === "proposals" || e.stage === "inspecting");
firstPass.summary = core.automationSummary(firstPass.entries);
const only = core.automationCombine([await load(firstPass)]);
assert.equal(only.summary.human_exceptions, 0);
assert.ok(only.summary.machine_tasks > 0, "machine work is still counted when no person is needed");
""")

    # --- identity is manifest + entry ------------------------------------------------------

    def test_the_same_k_id_on_two_cds_is_two_entries_with_their_own_evidence(self):
        self.run_js("""
const model = await sampleModel({ manifests: 2, perManifest: 5 });
const k1 = model.entries.filter(e => e.key.entry === "K1");
assert.equal(k1.length, 2);
assert.notEqual(k1[0].key.manifest, k1[1].key.manifest);
for (const entry of k1) {
  const found = core.automationFind(model, entry.key);
  assert.equal(found, entry);
  for (const field of found.fields) for (const item of field.evidence) {
    assert.equal(item.source_ref.manifest, entry.key.manifest);
    assert.equal(item.source_ref.entry, "K1");
  }
}
assert.notEqual(core.automationFind(model, k1[0].key).fields[0].evidence[0].value,
  core.automationFind(model, k1[1].key).fields[0].evidence[0].value);
// The same manifest twice would be two answers for one CD.
const again = await load(sample.createAutomationSampleSnapshots({ manifests: 1, perManifest: 2 })[0]);
assert.throws(() => core.automationCombine([again, again]), /to ganger/);
""")

    # --- search, filters, order and pages --------------------------------------------------

    def test_search_filters_and_pages_combine_over_the_whole_queue(self):
        self.run_js("""
const model = await sampleModel();
assert.equal(model.entries.length, 5000);
const all = core.automationQuery(model, {});
assert.equal(all.items.length, core.AUTOMATION_PAGE_SIZE);
assert.equal(all.pageCount, 200);
// Search on name and on source entry.
const byName = core.automationQuery(model, { query: "kvasarskriv" });
assert.ok(byName.matched > 0 && byName.items.every(e => e.title.toLowerCase().includes("kvasarskriv")));
const byEntry = core.automationQuery(model, { query: "K17", sort: "source" });
assert.ok(byEntry.items.every(e => e.key.entry.startsWith("K17") || e.title.includes("K17")));
assert.equal(byEntry.matched, 125, "K17 exists once on every one of the 125 CDs");
// Field + status: only entries whose version is in conflict.
const conflicts = core.automationQuery(model, { field: "version", status: "conflict" });
assert.ok(conflicts.matched > 0);
for (const entry of conflicts.items) assert.equal(entry.fields.find(f => f.field === "version").status, "conflict");
// Stage + status + search together.
const combined = core.automationQuery(model, { query: "kvasar", stage: "inspecting", status: "conflict" });
assert.ok(combined.matched > 0 && combined.matched < core.automationQuery(model, { query: "kvasar" }).matched);
for (const entry of combined.items) {
  assert.equal(entry.stage, "inspecting");
  assert.ok(entry.fields.some(f => f.status === "conflict"));
}
// A page past the end lands on the last page instead of an empty one.
const beyond = core.automationQuery(model, { query: "kvasar", page: 999 });
assert.equal(beyond.page, beyond.pageCount);
assert.ok(beyond.items.length > 0);
""")

    def test_the_order_is_stable_and_independent_of_input_order(self):
        self.run_js("""
const model = await sampleModel({ manifests: 6, perManifest: 40 });
for (const sort of core.AUTOMATION_SORTS) {
  const first = model.entries.slice().sort(core.automationComparator(sort)).map(e => core.automationKeyId(e.key));
  const reversed = model.entries.slice().reverse().sort(core.automationComparator(sort)).map(e => core.automationKeyId(e.key));
  assert.deepEqual(reversed, first, sort);
}
// The default order puts what needs a person first.
assert.equal(core.automationQuery(model, {}).items[0].stage, "needs_review");
const stages = model.entries.slice().sort(core.automationComparator("stage")).map(e => e.stage);
const rank = stages.map(s => core.AUTOMATION_STAGES.indexOf(s));
assert.deepEqual(rank, rank.slice().sort((a, b) => a - b));
// Natural order of source entries: K2 before K10.
const bySource = model.entries.filter(e => e.manifest_ordinal === 1).sort(core.automationComparator("source")).map(e => e.key.entry);
assert.ok(bySource.indexOf("K2") < bySource.indexOf("K10"));
""")

    def test_the_address_bar_round_trips_and_refuses_unknown_values(self):
        self.run_js("""
const state = { source: "syntetisk", query: "kvasar", stage: "inspecting", field: "version", status: "conflict",
  sort: "title", page: 3, open: { manifest: "sha256:abc", entry: "K1" } };
const back = core.automationStateFromQuery(new URLSearchParams(core.automationStateToQuery(state).toString()));
assert.deepEqual(back, state);
const odd = core.automationStateFromQuery(new URLSearchParams("stage=approved&feltstatus=godkjent&felt=pris&sort=x&side=-2"));
assert.deepEqual([odd.stage, odd.status, odd.field, odd.sort, odd.page], ["all", "all", "all", "stage", 1]);
assert.equal(core.automationStateToQuery({ stage: "all", field: "all", status: "all", sort: "stage", page: 1 }).toString(), "");
""")

    def test_five_thousand_entries_are_filtered_fast_enough(self):
        out = self.run_js("""
const started = performance.now();
const model = await sampleModel();
const loaded = performance.now() - started;
const times = [];
for (const query of ["k", "kv", "kva", "kvas", "kvasar", "k17", "polarsjakk"]) {
  const t = performance.now();
  core.automationQuery(model, { query, stage: "all" });
  times.push(performance.now() - t);
}
const worst = Math.max(...times);
assert.ok(worst < 100, `search took ${worst} ms`);
process.stderr.write(`5000 entries: validate+combine ${loaded.toFixed(0)} ms, worst search ${worst.toFixed(1)} ms\\n`);
""")
        self.assertEqual(out, "ok")


class AutomationQueueSourceTests(unittest.TestCase):
    """Rules that are about the files themselves."""

    def read(self, name: str) -> str:
        return (ROOT / name).read_text(encoding="utf-8")

    def test_source_text_is_never_parsed_as_html(self):
        for name in ("automation.js", "automation-core.js", "automation-adapter.js", "automation-sample.js"):
            source = self.read(name)
            for pattern in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "DOMParser"):
                self.assertNotIn(pattern, source, f"{name} uses {pattern}")

    def test_the_queue_never_writes(self):
        for name in QUEUE_FILES:
            source = self.read(name)
            self.assertNotIn("localStorage", source, name)
            self.assertNotIn("sessionStorage", source, name)
            self.assertIsNone(re.search(r"method:\s*['\"](POST|PUT|PATCH|DELETE)", source), name)
        # No button that pretends to decide something.
        page = self.read("automation.html") + self.read("automation.js")
        for word in ("Godkjenn", "Lagre", "Angre", "Utsett"):
            self.assertIsNone(re.search(rf">\s*{word}", page), word)
            self.assertNotIn(f'"{word}"', page, word)

    def test_sample_data_is_loaded_only_when_chosen(self):
        page = self.read("automation.html")
        self.assertNotIn("automation-sample.js", page, "the sample generator must not load by default")
        self.assertNotIn("automation-queue-v1.json", page)
        binding = self.read("automation.js")
        # The only paths to sample data sit behind an explicit source choice.
        self.assertEqual(binding.count('loadScript("automation-sample.js")'), 1)
        self.assertEqual(binding.count("tests/fixtures/automation-queue-v1.json"), 1)
        self.assertIn('state.source === "syntetisk"', binding)
        self.assertIn('state.source === "prove"', binding)
        # No catch path swaps in sample data.
        for match in re.finditer(r"\.catch\(([^)]*)\)", binding):
            self.assertIn("showError", match.group(1))

    def test_the_old_curator_is_not_offered_for_director_candidates(self):
        for name in QUEUE_FILES:
            self.assertNotIn("curate.html", self.read(name), name)

    def test_nothing_of_the_queue_is_in_the_public_release(self):
        build = self.read("scripts/build-release.py")
        static = re.search(r"STATIC_FILES = \((.*?)\)\n", build, re.S).group(1)
        self.assertNotIn("automation", static)
        verifier = self.read("scripts/verify-deployment.py")
        for name in (*QUEUE_FILES, "tests/fixtures/automation-queue-v1.json"):
            self.assertIn(f'"{name}"', verifier, f"{name} is not checked to be 404 in production")


if __name__ == "__main__":
    unittest.main()
