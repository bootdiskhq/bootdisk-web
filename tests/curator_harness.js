/* Shared harness for the curator behaviour tests. Each test appends its own body and
 * runs against the unchanged fixture bundle through the real adapter and controller. */
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

const ROOT = process.env.CURATOR_WEB_ROOT;
const { createFixtureAdapter, validateDraft } = require(path.join(ROOT, "curate-adapter.js"));
const {
  createCuratorController,
  curatorActionForEvent,
  curatorShortcutAllowed,
  CURATOR_SHORTCUT_HINTS,
  CURATOR_ACTIONS,
} = require(path.join(ROOT, "curate-core.js"));

const fixture = JSON.parse(fs.readFileSync(path.join(ROOT, "tests/fixtures/curator-fixtures-v1.json"), "utf8"));
const MANIFEST = fixture.entries[0].key.manifest;

function key(entry) {
  return { manifest: MANIFEST, entry };
}

function memoryStorage() {
  const store = new Map();
  return {
    getItem: name => (store.has(name) ? store.get(name) : null),
    setItem: (name, value) => store.set(name, value),
    removeItem: name => store.delete(name),
    size: () => store.size,
  };
}

/* Timers are driven by the test so autosave ordering is deterministic. */
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

function harness(options = {}) {
  const storage = options.storage ?? memoryStorage();
  const adapter = options.adapter ?? createFixtureAdapter({
    fixture,
    storage,
    now: () => "2026-09-20T12:00:00Z",
  });
  const scheduler = manualScheduler();
  let counter = 0;
  const controller = createCuratorController({
    adapter,
    scheduler,
    autosaveDelay: 0,
    operationId: () => `${options.prefix ?? "op"}-${++counter}`,
  });
  return { adapter, controller, scheduler, storage };
}

module.exports = {
  assert,
  fixture,
  MANIFEST,
  key,
  harness,
  memoryStorage,
  manualScheduler,
  createFixtureAdapter,
  createCuratorController,
  validateDraft,
  curatorActionForEvent,
  curatorShortcutAllowed,
  CURATOR_SHORTCUT_HINTS,
  CURATOR_ACTIONS,
};
