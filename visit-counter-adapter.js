/* Transport for besøkstelleren. Visningen kjenner bare `read()` og `record(key)`; hvor totalen
 * lagres er tjenestens sak. Kontrakten står i docs/visit-counter.md:
 *
 *   GET  endpoint                      -> {"total": 123, "since": "2026-09-25"}
 *   POST endpoint {"visit": "<32 hex>"} -> {"total": 124, "since": "2026-09-25", "counted": true}
 *
 * Alle feil blir en VisitCounterError med `kind` (network, timeout, http, invalid). */

class VisitCounterError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "VisitCounterError";
    this.kind = kind;
  }
}

function createHttpVisitCounterAdapter({ endpoint, fetchImpl, parse, timeoutMs = 5000 }) {
  if (typeof endpoint !== "string" || !endpoint) throw new Error("Besøkstelleren mangler adresse");

  async function call(options, expectCounted) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      if (controller) controller.abort();
    }, timeoutMs);
    let response;
    try {
      response = await fetchImpl(endpoint, {
        ...options,
        cache: "no-store",
        credentials: "omit",
        referrerPolicy: "no-referrer",
        signal: controller ? controller.signal : undefined,
      });
    } catch (error) {
      throw new VisitCounterError(timedOut ? "timeout" : "network", String(error && error.message || error));
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) throw new VisitCounterError("http", `HTTP ${response.status}`);
    let body;
    try {
      body = await response.json();
    } catch (error) {
      throw new VisitCounterError("invalid", "Svaret er ikke JSON");
    }
    try {
      return parse(body, expectCounted);
    } catch (error) {
      throw new VisitCounterError("invalid", error.message);
    }
  }

  return {
    read: () => call({ method: "GET" }, false),
    record: key => call({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visit: key }),
    }, true),
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { VisitCounterError, createHttpVisitCounterAdapter };
}
