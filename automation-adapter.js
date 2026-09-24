/* Read-only adapter for the automatic first-pass queue (contract: docs/automation-queue-v1.md).
 *
 * The adapter has exactly one method, loadQueue(), which resolves to one validated snapshot
 * (one manifest). There is no save, approve or undo here, and none is faked: the contract has
 * none. Where the document comes from is chosen explicitly by whoever builds the adapter; a
 * missing or broken document is an error and is never replaced with sample data.
 *
 * Future wiring (not done here, owned by Catalog): a local service answer can be passed in
 * as another `read` function returning the document text. This file invents no endpoint.
 */
function automationAdapterCore() {
  if (typeof automationValidate === "function") return { automationValidate, AutomationQueueError };
  // eslint-disable-next-line global-require
  return require("./automation-core.js");
}

/* Turns text into a validated document, telling "not JSON" apart from "JSON of the wrong
 * shape", so the page can say which one it is. */
function automationParse(text, sourceName) {
  const core = automationAdapterCore();
  let document;
  try {
    document = JSON.parse(text);
  } catch (error) {
    throw new core.AutomationQueueError("invalid_json", `${sourceName} er ikke gyldig JSON: ${error.message}`);
  }
  return core.automationValidate(document);
}

/* `read` resolves to the raw document text. It is called again on every loadQueue(), so a
 * retry reads the source anew rather than serving an earlier answer. */
function createAutomationQueueAdapter({ read, sourceName = "Køfilen" }) {
  if (typeof read !== "function") throw new TypeError("createAutomationQueueAdapter needs a read function");
  return Object.freeze({
    loadQueue() {
      return Promise.resolve().then(read).then(text => automationParse(text, sourceName));
    },
  });
}

/* Reads a file the local page itself serves, with a plain GET. A missing file and a network
 * failure are both "missing": neither has a document to show. */
function automationFetchText(url, fetchImpl) {
  const core = automationAdapterCore();
  const doFetch = fetchImpl ?? (typeof fetch === "function" ? (...args) => fetch(...args) : null);
  return () => Promise.resolve()
    .then(() => doFetch(url, { method: "GET", cache: "no-store", credentials: "same-origin" }))
    .catch(error => {
      throw new core.AutomationQueueError("missing", `Fant ikke køfilen ${url}: ${error?.message ?? "ingen forbindelse"}.`);
    })
    .then(response => {
      if (!response.ok) {
        throw new core.AutomationQueueError("missing", `Fant ikke køfilen ${url} (HTTP ${response.status}).`);
      }
      return response.text();
    });
}

function createAutomationFileAdapter(url, fetchImpl) {
  return createAutomationQueueAdapter({ read: automationFetchText(url, fetchImpl), sourceName: `Køfilen ${url}` });
}

/* A file the person picked on their own machine. Read-only: the page never writes it back. */
function createAutomationTextAdapter(text, name) {
  return createAutomationQueueAdapter({ read: () => text, sourceName: `Filen ${name}` });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    createAutomationQueueAdapter,
    createAutomationFileAdapter,
    createAutomationTextAdapter,
    automationFetchText,
    automationParse,
  };
}
