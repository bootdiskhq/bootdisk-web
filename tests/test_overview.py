"""Behaviour tests for the curator overview prototype.

The JavaScript cases drive the real prototype overview adapter, the real controller and the
existing fixture adapter through Node, so they verify observable behaviour (combined search
and filters, stable pagination, the round trip to the detail screen, refresh after a
decision and the stale-result guard) rather than the presence of function names in a file.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "overview_harness.js"

NODE = shutil.which("node")


def behaviour(body: str) -> str:
    return f"""
const {{
  assert, sample, overviewHarness, detailHarness, memoryStorage, heldSettle,
  createOverviewAdapter, overviewSummary, overviewSummaryFromEntry,
  overviewStateFromQuery, overviewStateToQuery, overviewSafeReturnQuery,
  createFixtureAdapter, OVERVIEW_CONTRACT, OVERVIEW_PAGE_SIZE,
}} = require({str(HARNESS)!r});
const {{ overviewApplyRecord }} = require({str(ROOT / "overview-adapter.js")!r});
const {{ curatorFieldText, CONTENT_KIND_LABELS, DISTRIBUTION_LABELS }} = require({str(ROOT / "curator-labels.js")!r});
const {{ CONTENT_KINDS, DISTRIBUTION_KINDS }} = require({str(ROOT / "curate-adapter.js")!r});

function search(harness, text) {{
  const pending = harness.controller.setInput(text);
  harness.scheduler.run();
  return pending;
}}

/* A row whose identity is settled and that still has another field open, so approving it
 * cannot hit the shared-identity conflict and still leaves something unresolved. */
function openButIdentified(items) {{
  return items.find(row => row.queue_state === "pending"
    && row.identification_status === "curated"
    && row.open_fields.length > 0
    && !row.open_fields.includes("identity"));
}}

(async () => {{
{body}
}})().catch(error => {{
  console.error(error.stack || error.message || String(error));
  process.exit(1);
}});
"""


@unittest.skipUnless(NODE, "Node.js is required for the overview behaviour tests")
class OverviewBehaviourTests(unittest.TestCase):
    def run_behaviour(self, body: str) -> str:
        result = subprocess.run(
            [NODE, "-e", behaviour(body)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={"CURATOR_WEB_ROOT": str(ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        if result.returncode != 0:
            self.fail(f"overview behaviour failed:\n{result.stderr}\n{result.stdout}")
        return result.stdout

    def test_search_and_filters_combine_and_reset(self):
        """Work order case 1: search plus field and status filter, no hits, and reset."""
        self.run_behaviour("""
  const harness = overviewHarness();
  await harness.controller.start();
  const everything = harness.controller.state.matched;
  assert.ok(everything > 0, "the overview starts with rows");

  await harness.controller.setStatus("pending");
  assert.ok(harness.controller.state.items.every(row => row.queue_state === "pending"));
  const afterStatus = harness.controller.state.matched;
  assert.ok(afterStatus < everything, "the status filter narrows the result");

  await harness.controller.setField("version");
  assert.ok(harness.controller.state.items.every(row => row.open_fields.includes("version")));
  const afterField = harness.controller.state.matched;
  assert.ok(afterField <= afterStatus, "the field filter narrows it further");

  await search(harness, "kvasar");
  assert.ok(harness.controller.state.matched <= afterField, "search narrows the filtered result");
  for (const row of harness.controller.state.items) {
    assert.ok(row.search.includes("kvasar"), "every row still matches the search");
    assert.equal(row.queue_state, "pending", "every row still matches the status filter");
    assert.ok(row.open_fields.includes("version"), "every row still matches the field filter");
  }

  await search(harness, "ingensomhelstheter");
  assert.equal(harness.controller.state.matched, 0);
  assert.equal(harness.controller.state.items.length, 0);
  assert.equal(harness.controller.state.pageCount, 1, "an empty result is still one page");

  await harness.controller.reset();
  assert.equal(harness.controller.state.matched, everything, "reset restores the whole queue");
  assert.equal(harness.controller.state.status, "all");
  assert.equal(harness.controller.state.field, "all");
  assert.equal(harness.controller.state.query, "");
  console.log("ok");
""")

    def test_pagination_is_stable_across_repeated_names_and_shared_entry_ids(self):
        """Work order case 2: every row appears exactly once, with equal names and shared K-ids."""
        self.run_behaviour("""
  const harness = overviewHarness({ manifests: 6, pageSize: 40 });
  await harness.controller.start();
  const expected = harness.controller.state.matched;

  const seen = [];
  for (let page = 1; page <= harness.controller.state.pageCount; page += 1) {
    await harness.controller.setPage(page);
    for (const row of harness.controller.state.items) seen.push(`${row.key.manifest}/${row.key.entry}`);
  }
  assert.equal(seen.length, expected, "paging through visits every matched row once");
  assert.equal(new Set(seen).size, expected, "no row is repeated across page boundaries");

  /* The same K-id exists in every manifest, and names repeat by construction. */
  const perEntry = seen.filter(id => id.endsWith("/K7"));
  assert.equal(perEntry.length, harness.manifests.length, "K7 appears once per manifest");
  assert.equal(new Set(perEntry).size, perEntry.length, "the shared K-id stays distinct per manifest");

  const titles = new Map();
  for (const row of harness.rows) titles.set(row.title, (titles.get(row.title) ?? 0) + 1);
  assert.ok(Math.max(...titles.values()) > 1, "the sample really does repeat program names");

  const again = overviewHarness({ manifests: 6, pageSize: 40 });
  await again.controller.start();
  const order = [];
  for (let page = 1; page <= again.controller.state.pageCount; page += 1) {
    await again.controller.setPage(page);
    for (const row of again.controller.state.items) order.push(`${row.key.manifest}/${row.key.entry}`);
  }
  assert.deepEqual(order, seen, "a second run produces the same order and the same pages");
  console.log("ok");
""")

    def test_round_trip_to_the_detail_screen_restores_search_filters_page_and_row(self):
        """Work order case 3: overview to detail and back keeps position, filters and focus."""
        self.run_behaviour("""
  const harness = overviewHarness();
  await harness.controller.start();
  await harness.controller.setStatus("pending");
  await search(harness, "a");
  await harness.controller.setPage(2);
  const row = harness.controller.state.items[3];

  /* The address the overview hands over, and the address the detail screen hands back. */
  const handover = overviewStateToQuery({ ...harness.controller.state, focusKey: row.key }).toString();
  const returned = overviewSafeReturnQuery(handover);

  const curator = harness.curatorFor(row.key.manifest);
  const detail = detailHarness(curator);
  await detail.controller.start();
  await detail.controller.select(row.key);
  assert.equal(detail.controller.state.entry.key.entry, row.key.entry, "the detail screen opened the chosen row");
  assert.equal(detail.controller.state.entry.key.manifest, row.key.manifest, "on its own manifest, not another one");

  const back = overviewHarness({ storage: harness.storage });
  await back.controller.reopen(overviewStateFromQuery(new URLSearchParams(returned)));
  assert.equal(back.controller.state.query, "a", "the search came back");
  assert.equal(back.controller.state.status, "pending", "the status filter came back");
  assert.equal(back.controller.state.page, 2, "the page came back");
  assert.deepEqual(back.controller.state.focusKey, row.key, "the row to focus came back");
  assert.ok(back.controller.state.items.some(item =>
    item.key.entry === row.key.entry && item.key.manifest === row.key.manifest), "the row is on the restored page");
  console.log("ok");
""")

    def test_return_address_keeps_only_its_own_keys(self):
        """A return address is rebuilt from known keys, never followed as supplied."""
        self.run_behaviour("""
  const safe = overviewSafeReturnQuery("q=kart&status=pending&side=3&annet=x&url=https://example.invalid");
  const params = new URLSearchParams(safe);
  assert.equal(params.get("q"), "kart");
  assert.equal(params.get("status"), "pending");
  assert.equal(params.get("side"), "3");
  assert.equal(params.get("annet"), null, "an unknown key is dropped");
  assert.equal(params.get("url"), null, "a supplied address is dropped");
  assert.equal(overviewSafeReturnQuery(null), "");
  assert.equal(overviewSafeReturnQuery("//example.invalid/overview"), "");
  console.log("ok");
""")

    def test_decisions_update_the_row_from_what_the_adapter_answers(self):
        """Work order case 4: approve, defer and undo, and reviewed is not resolved."""
        self.run_behaviour("""
  const harness = overviewHarness();
  await harness.controller.start();
  await harness.controller.setStatus("pending");
  const row = openButIdentified(harness.controller.state.items);
  assert.ok(row, "the sample has a pending row with an open field and a settled identity");

  const curator = harness.curatorFor(row.key.manifest);
  const detail = detailHarness(curator);
  await detail.controller.start();
  await detail.controller.select(row.key);
  await detail.controller.dispatch("commit");

  const approved = await harness.controller.refreshRow(row.key);
  assert.equal(approved.queue_state, "reviewed", "the row is reviewed after approval");
  assert.ok(approved.open_fields.length > 0, "the entry still has an open field");
  assert.equal(approved.fully_resolved, false, "a reviewed row with open fields is not fully resolved");
  assert.ok(harness.controller.state.outsideFilter, "a row that left the filter says so");
  assert.ok(harness.controller.state.items.some(item => item.key.entry === row.key.entry),
    "and keeps its place in the list");

  /* Undo returns the entry to pending, and the row follows the adapter's answer. */
  await detail.controller.select(row.key);
  assert.ok(detail.controller.state.entry.undo, "the approval is reversible");
  await detail.controller.dispatch("undo");
  const undone = await harness.controller.refreshRow(row.key);
  assert.equal(undone.queue_state, "pending", "undo puts the row back to pending");
  assert.equal(harness.controller.state.outsideFilter, null, "and it belongs in the filter again");

  const other = harness.controller.state.items.find(item => item.key.entry !== row.key.entry);
  const second = detailHarness(harness.curatorFor(other.key.manifest));
  await second.controller.start();
  await second.controller.select(other.key);
  await second.controller.dispatch("defer", "Uleselig installasjonsfil i prøvedataene.");
  const deferred = await harness.controller.refreshRow(other.key);
  assert.equal(deferred.queue_state, "deferred", "a skipped row shows as deferred");
  console.log("ok");
""")

    def test_failed_write_and_conflict_keep_the_draft_and_block_navigation(self):
        """Work order case 5: the overview never shows an unsaved draft as decided."""
        self.run_behaviour("""
  const harness = overviewHarness();
  await harness.controller.start();
  const row = harness.controller.state.items.find(item => item.has_accepted);
  const curator = harness.curatorFor(row.key.manifest);
  const detail = detailHarness(curator);
  await detail.controller.start();
  await detail.controller.select(row.key);

  const before = await harness.controller.refreshRow(row.key);
  detail.controller.editClaim("version", { value: "9.9", assessment: "accepted" });

  /* Leaving the entry flushes the draft first. While that write keeps failing, the move is
   * refused rather than silently dropping the edit. */
  const other = harness.controller.state.items.find(item => item.key.entry !== row.key.entry
    && item.key.manifest === row.key.manifest);
  curator.simulation.arm("write_failed");
  await detail.controller.select(other.key);
  assert.equal(detail.controller.state.entry.key.entry, row.key.entry, "navigation is refused on a failed draft");
  assert.equal(detail.controller.state.status, "error", "the failed write is reported");
  assert.equal(detail.controller.state.draft.claims.version.value, "9.9", "the draft is kept");

  const during = await harness.controller.refreshRow(row.key);
  assert.deepEqual(during.values.version, before.values.version, "a failed write reaches the overview not at all");

  /* Once the write succeeds the row shows the text as a draft, never as an approved value. */
  await detail.controller.save();
  const saved = await harness.controller.refreshRow(row.key);
  assert.equal(saved.values.version.draft, "9.9", "the saved draft is visible as a draft");
  assert.notEqual(saved.values.version.accepted, "9.9", "and is not the approved value");
  assert.equal(saved.values.version.differs, true, "so the row marks the two apart");
  assert.equal(saved.queue_state, row.queue_state, "saving a draft is not a decision");

  detail.controller.editClaim("version", { value: "9.10", assessment: "accepted" });
  curator.simulation.arm("revision_conflict");
  await detail.controller.save().catch(() => {});
  assert.ok(detail.controller.state.conflict, "a stale write is reported as a conflict");
  assert.equal(detail.controller.state.draft.claims.version.value, "9.10", "and the local draft survives it");
  const conflicted = await harness.controller.refreshRow(row.key);
  assert.equal(conflicted.values.version.draft, "9.9", "the overview still shows the last stored draft");
  console.log("ok");
""")

    def test_a_slow_old_search_result_cannot_replace_a_newer_one(self):
        """Work order case 6: the newest request owns the result, whatever order they land in."""
        self.run_behaviour("""
  const held = heldSettle();
  const harness = overviewHarness({ settle: held.settle });
  const started = harness.controller.start();
  await held.releaseAll();
  await started;

  const first = search(harness, "kvasar");
  const second = search(harness, "nimbus");
  assert.equal(held.pending(), 2, "both searches are in flight");

  /* The newer answer lands first, then the older one arrives late. */
  await held.release(1);
  await second;
  await held.release(0);
  await first;

  assert.ok(harness.controller.state.items.length > 0, "the newer search produced rows");
  for (const row of harness.controller.state.items) {
    assert.ok(row.search.includes("nimbus"), `a stale result replaced the newer one: ${row.title}`);
  }
  console.log("ok");
""")

    def test_reading_the_overview_never_writes_and_never_reads_entry_by_entry(self):
        """Work order case 7: no write calls, no detail call per row, bounded rows at scale."""
        self.run_behaviour("""
  const harness = overviewHarness();
  await harness.controller.start();
  assert.deepEqual(harness.calls, { getQueue: 0, getEntry: 0, saveDraft: 0, defer: 0, approve: 0, undo: 0, setResume: 0 },
    "opening the overview calls the curator adapter not at all");

  await harness.controller.setStatus("reviewed");
  await harness.controller.setField("any_open");
  await harness.controller.setSort("source");
  await search(harness, "kart");
  await harness.controller.setPage(1);
  await harness.controller.reset();
  assert.equal(harness.calls.saveDraft + harness.calls.approve + harness.calls.defer
    + harness.calls.undo + harness.calls.setResume, 0, "searching and filtering writes nothing");
  assert.equal(harness.calls.getEntry, 0, "searching and filtering reads no entry document");

  const scale = overviewHarness({ manifests: sample.OVERVIEW_SAMPLE_MANIFESTS.length });
  await scale.controller.start();
  assert.ok(scale.controller.state.total >= 5000, `the scale set is ${scale.controller.state.total} entries`);
  assert.equal(scale.calls.getEntry, 0, "no entry document is read at startup, at any size");
  assert.ok(scale.controller.state.items.length <= OVERVIEW_PAGE_SIZE,
    `one page renders ${scale.controller.state.items.length} rows`);
  await search(scale, "k23");
  assert.ok(scale.controller.state.matched > 100, "the shared K-id matches across manifests");
  assert.ok(scale.controller.state.items.length <= OVERVIEW_PAGE_SIZE, "a large result is still one page of rows");
  console.log("ok");
""")

    def test_a_draft_is_never_presented_as_the_approved_value(self):
        """Draft, approved and never-approved are three different things in a row."""
        self.run_behaviour("""
  const harness = overviewHarness({ manifests: 8 });
  await harness.controller.start();

  const edited = harness.rows.find(row => row.has_accepted && row.values.version.differs);
  assert.ok(edited, "the sample contains an edited draft");
  assert.notEqual(edited.values.version.accepted, edited.values.version.draft);

  const unapproved = harness.rows.find(row => !row.has_accepted);
  assert.ok(unapproved, "the sample contains an entry with no approved value");
  assert.equal(unapproved.values.version.accepted, null, "there is no approved value to show");
  assert.equal(unapproved.identification_status, null);
  assert.equal(unapproved.fully_resolved, false, "nothing unapproved counts as resolved");

  /* «unknown» is a stored value, and is spelled out in Norwegian wherever it is shown. */
  assert.equal(curatorFieldText("version", "unknown"), "Ikke oppgitt");
  assert.equal(curatorFieldText("distribution_kind", "unknown"), "Ukjent");
  for (const kind of CONTENT_KINDS) assert.ok(CONTENT_KIND_LABELS[kind], `${kind} has a Norwegian label`);
  for (const kind of DISTRIBUTION_KINDS) assert.ok(DISTRIBUTION_LABELS[kind], `${kind} has a Norwegian label`);
  console.log("ok");
""")

    def test_summary_matches_the_entry_document_and_stored_review_state(self):
        """The row and the detail screen cannot describe the same entry differently."""
        self.run_behaviour("""
  const manifest = sample.OVERVIEW_SAMPLE_MANIFESTS[2];
  const bundle = sample.createSampleBundle(manifest.id);
  for (const entry of bundle.entries.slice(0, 12)) {
    const fromDocument = overviewSummaryFromEntry(entry, manifest.label);
    const fromRecord = overviewSummary(sample.sampleRecord(manifest, Number(entry.key.entry.slice(1)) - 1));
    assert.deepEqual(fromDocument, fromRecord, `${entry.key.entry} is described the same way both ways`);
  }

  /* The stored review state of the detail screen replaces a generated row exactly. */
  const storage = memoryStorage();
  const curator = createFixtureAdapter({
    fixture: bundle,
    datasetId: sample.sampleDatasetId(manifest.id),
    storage,
  });
  const target = bundle.entries.find(entry => entry.queue_state === "pending");
  await curator.defer({
    key: target.key,
    expected_revision: target.revision,
    operation_id: "overview-store-1",
    reason: "Utsatt i prøvedataene.",
  });
  const stored = JSON.parse(storage.getItem(`bootdisk-curator-v1/v1/${sample.sampleDatasetId(manifest.id)}`));
  const generated = overviewSummary(sample.sampleRecord(manifest, Number(target.key.entry.slice(1)) - 1));
  const overlaid = overviewApplyRecord(generated, stored.entries[target.key.entry]);
  const document = overviewSummaryFromEntry(await curator.getEntry({ key: target.key }), manifest.label);
  assert.equal(overlaid.queue_state, "deferred");
  assert.deepEqual(overlaid, document, "the stored overlay says what the adapter says");
  console.log("ok");
""")

    def test_sample_data_is_deterministic_and_marked_synthetic(self):
        """The scale set is reproducible and never passes for a catalogue finding."""
        self.run_behaviour("""
  const first = sample.sampleSummaries(overviewSummary, { manifests: sample.OVERVIEW_SAMPLE_MANIFESTS.slice(0, 4) });
  const second = sample.sampleSummaries(overviewSummary, { manifests: sample.OVERVIEW_SAMPLE_MANIFESTS.slice(0, 4) });
  assert.deepEqual(first, second, "two generations are identical");
  assert.ok(sample.OVERVIEW_SAMPLE_TOTAL >= 5000, `the scale set is ${sample.OVERVIEW_SAMPLE_TOTAL} entries`);
  assert.ok(sample.OVERVIEW_SAMPLE_MANIFESTS.length > 1, "the sample spans several manifests");

  const bundle = sample.createSampleBundle(sample.OVERVIEW_SAMPLE_MANIFESTS[0].id);
  assert.equal(bundle.fixture_only, true);
  assert.equal(bundle.synthetic, true);
  assert.match(bundle.note, /[Ss]yntetisk/);
  for (const manifest of sample.OVERVIEW_SAMPLE_MANIFESTS.slice(0, 5)) {
    assert.match(manifest.label, /Syntetisk/, "every source manifest is labelled synthetic");
    assert.match(manifest.id, /^sha256:[0-9a-f]{64}$/, "and still carries a contract-shaped digest");
  }

  /* Mixed name lengths, so the table is measured against real column pressure. */
  const lengths = first.map(row => row.title.length);
  assert.ok(Math.min(...lengths) < 16 && Math.max(...lengths) > 40, "short and long names both occur");
  console.log("ok");
""")

    def test_the_prototype_adapter_exposes_no_write_operation(self):
        """Search and filter cannot write, because there is nothing to call."""
        self.run_behaviour("""
  const harness = overviewHarness({ manifests: 2 });
  for (const method of ["saveDraft", "approve", "defer", "undo", "setResume"]) {
    assert.equal(harness.adapter[method], undefined, `${method} is not on the overview adapter`);
  }
  assert.equal(harness.adapter.prototype, true, "the read layer marks itself a prototype");
  const result = await harness.adapter.listEntries({ page_size: 5 });
  assert.equal(result.schema, OVERVIEW_CONTRACT, "and answers on its own proposed contract, not v1");
  assert.notEqual(result.schema, "bootdisk-curator-v1");
  console.log("ok");
""")


class OverviewReleaseTests(unittest.TestCase):
    def test_public_release_excludes_the_overview_and_its_sample_data(self):
        """Work order case 8: the prototype never reaches the public release allowlist."""
        builder = (ROOT / "scripts" / "build-release.py").read_text(encoding="utf-8")
        allowlist = builder.split("STATIC_FILES = (")[1].split(")")[0]
        for forbidden in ("overview", "sample", "curator-labels", "curator-navigation"):
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
            for name in ("overview.html", "overview.js", "overview-core.js", "overview-adapter.js",
                         "overview-sample.js", "overview.css", "curator-labels.js", "curator-navigation.js"):
                self.assertNotIn(name, published, f"{name} must not be published")
            self.assertIn("archive.html", published, "the existing public archive still builds")

    def test_the_overview_page_is_marked_local_and_accessible(self):
        page = (ROOT / "overview.html").read_text(encoding="utf-8")
        self.assertIn('name="robots" content="noindex"', page, "the overview is not a public page")
        self.assertIn('class="skip-link" href="#main-content"', page)
        self.assertIn('id="main-content"', page)
        self.assertIn("<noscript>", page)
        self.assertIn('href="accessibility.css"', page)
        self.assertIn('role="alert"', page)
        self.assertIn('aria-live="polite"', page)
        self.assertIn("Syntetiske prøvedata – ikke katalogfunn.", page)
        for header in ("Program", "Kildepost", "Versjon", "Innholdstype", "Utgave", "Vurderingsstatus", "Avklaring"):
            self.assertIn(f'<th scope="col">{header}</th>', page, f"the table keeps a {header} header")

    def test_overview_rendering_builds_nodes_instead_of_markup(self):
        for name in ("overview.js", "overview-core.js", "overview-adapter.js", "overview-sample.js"):
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("innerHTML", source, f"{name} must not write markup")
            self.assertNotIn("outerHTML", source)
            self.assertNotIn("insertAdjacentHTML", source)
            self.assertNotIn("document.write", source)


if __name__ == "__main__":
    unittest.main()
