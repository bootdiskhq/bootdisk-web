/* Same adapter interface as fixtures, backed by the loopback Catalog service.
 * No browser persistence and no fallback to fixtures on network failure. */
async function createLiveAdapter({ fetcher = (...args) => fetch(...args), timeoutMs = 15000 } = {}) {
  const schema = 'bootdisk-curator-v1';
  function unavailable(message) {
    return { code: 'service_unavailable', message, retryable: true, field_errors: {}, current_entry: null };
  }
  async function request(path, payload, token) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const headers = { 'X-Bootdisk-Client': schema };
      const options = { headers, cache: 'no-store', credentials: 'same-origin', signal: controller.signal };
      if (payload !== undefined) {
        options.method = 'POST';
        headers['Content-Type'] = 'application/json';
        headers['X-Bootdisk-Token'] = token;
        options.body = JSON.stringify(payload);
      }
      let response;
      try { response = await fetcher(path, options); }
      catch (_) { throw unavailable('Den lokale tjenesten svarte ikke. Behold kladden og prøv samme handling igjen.'); }
      let result;
      try { result = await response.json(); }
      catch (_) { throw unavailable('Tjenesten returnerte et uleselig svar.'); }
      if (!response.ok) {
        if (result && typeof result.code === 'string' && typeof result.message === 'string') throw result;
        throw unavailable('Den lokale tjenesten avviste forespørselen.');
      }
      if (result?.schema !== schema) throw unavailable('Tjenesten bruker en annen datakontrakt.');
      return result;
    } finally { clearTimeout(timer); }
  }
  const session = await request('/api/session');
  if (!session.token || !session.manifest) throw unavailable('Den lokale økten mangler nødvendige data.');
  const adapter = { schema, fixtureMode: false, durable: true, manifest: session.manifest };
  for (const method of ['getQueue', 'getEntry', 'saveDraft', 'defer', 'approve', 'undo', 'setResume']) {
    adapter[method] = payload => request('/api/' + method, payload, session.token);
  }
  return adapter;
}
if (typeof module !== 'undefined' && module.exports) module.exports = { createLiveAdapter };
