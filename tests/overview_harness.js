/* Shared harness for the curator overview tests. Each test drives the real prototype
 * overview adapter and controller over the deterministic sample data, and the real fixture
 * adapter for the detail and decision semantics. */
const path = require("node:path");
const assert = require("node:assert/strict");

const ROOT = process.env.CURATOR_WEB_ROOT;
const { createFixtureAdapter } = require(path.join(ROOT, "curate-adapter.js"));
const { createCuratorController } = require(path.join(ROOT, "curate-core.js"));
const {
  createOverviewAdapter,
  overviewSummary,
  overviewSummaryFromEntry,
  OVERVIEW_CONTRACT,
  OVERVIEW_PAGE_SIZE,
} = require(path.join(ROOT, "overview-adapter.js"));
const { createOverviewController } = require(path.join(ROOT, "overview-core.js"));
const {
  overviewStateFromQuery,
  overviewStateToQuery,
  overviewSafeReturnQuery,
} = require(path.join(ROOT, "curator-navigation.js"));
const sample = require(path.join(ROOT, "overview-sample.js"));

function memoryStorage() {
  const store = new Map();
  return {
    getItem: name => (store.has(name) ? store.get(name) : null),
    setItem: (name, value) => store.set(name, value),
    removeItem: name => store.delete(name),
  };
}

/* Timers are driven by the test so the search debounce is deterministic. */
function manualScheduler() {
  const jobs = [];
  return {
    set: callback => jobs.push(callback) - 1,
    clear: id => { jobs[id] = null; },
    run() {
      const due = jobs.splice(0, jobs.length);
      for (const job of due) if (job) job();
    },
  };
}

/* Holds every adapter answer until a test releases it, so an old result can be delivered
 * after a newer one on purpose. */
function heldSettle() {
  const queue = [];
  return {
    settle: value => new Promise(resolve => queue.push({ resolve, value })),
    pending: () => queue.length,
    release(index) {
      const [job] = queue.splice(index, 1);
      job.resolve(job.value);
      return Promise.resolve();
    },
    releaseAll() {
      const due = queue.splice(0, queue.length);
      for (const job of due) job.resolve(job.value);
      return Promise.resolve();
    },
  };
}

function overviewHarness(options = {}) {
  const manifests = sample.OVERVIEW_SAMPLE_MANIFESTS.slice(0, options.manifests ?? 3);
  const entriesPerManifest = options.entriesPerManifest;
  const calls = { getQueue: 0, getEntry: 0, saveDraft: 0, defer: 0, approve: 0, undo: 0, setResume: 0 };
  const curators = new Map();
  const storage = options.storage ?? memoryStorage();

  /* One v1 adapter per manifest, because the queue in the contract is per manifest. Each is
   * built the first time that manifest is read, never at startup. */
  function curatorFor(manifestId) {
    if (!curators.has(manifestId)) {
      const manifest = sample.sampleManifest(manifestId);
      const inner = createFixtureAdapter({
        fixture: sample.createSampleBundle(manifestId, entriesPerManifest ? { count: entriesPerManifest } : {}),
        datasetId: sample.sampleDatasetId(manifestId),
        storage,
        now: () => "2026-09-20T12:00:00Z",
      });
      const counted = Object.create(inner);
      for (const method of Object.keys(calls)) {
        counted[method] = request => { calls[method] += 1; return inner[method](request); };
      }
      counted.label = manifest.label;
      curators.set(manifestId, counted);
    }
    return curators.get(manifestId);
  }

  const rows = sample.sampleSummaries(overviewSummary, { manifests, entriesPerManifest });
  const adapter = createOverviewAdapter({
    rows,
    curatorFor,
    manifestLabels: new Map(manifests.map(manifest => [manifest.id, manifest.label])),
    settle: options.settle,
  });
  const scheduler = manualScheduler();
  const controller = createOverviewController({
    adapter,
    scheduler,
    searchDelay: 0,
    pageSize: options.pageSize ?? OVERVIEW_PAGE_SIZE,
  });
  return { adapter, controller, scheduler, calls, curators, curatorFor, manifests, rows, storage };
}

/* The detail screen the overview hands a row to, built the way curate.js builds it. */
function detailHarness(curator, options = {}) {
  const scheduler = manualScheduler();
  let counter = 0;
  const controller = createCuratorController({
    adapter: curator,
    scheduler,
    autosaveDelay: 0,
    operationId: () => `overview-op-${++counter}`,
  });
  return { controller, scheduler, manifest: options.manifest };
}

module.exports = {
  assert,
  sample,
  overviewHarness,
  detailHarness,
  memoryStorage,
  manualScheduler,
  heldSettle,
  createOverviewAdapter,
  createOverviewController,
  overviewSummary,
  overviewSummaryFromEntry,
  overviewStateFromQuery,
  overviewStateToQuery,
  overviewSafeReturnQuery,
  createFixtureAdapter,
  OVERVIEW_CONTRACT,
  OVERVIEW_PAGE_SIZE,
};
