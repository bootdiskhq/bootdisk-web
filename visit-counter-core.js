/* Besøkstelleren: DOM-fri logikk for besøksavgrensning, svarkontroll og visning.
 *
 * Et besøk er en rekke sidevisninger i samme nettleser uten mer enn 30 minutters pause.
 * Første sidevisning i et besøk lager en tilfeldig besøksnøkkel og ber tjenesten telle den.
 * Senere sidevisninger og omlasting i samme besøk leser bare totalen. Nøkkelen sendes på nytt
 * (samme nøkkel) til tjenesten har bekreftet den, slik at et tidsavbrudd ikke gir dobbelttelling.
 * Se docs/visit-counter.md. */

const VISIT_IDLE_MS = 30 * 60 * 1000;
/* Så lenge prøver nettleseren en ubekreftet nøkkel på nytt. Tjenesten holder nøkler i 48 timer
 * (VISIT_KEY_TTL i counter/besok.php), så en ny innsending treffer alltid en kjent nøkkel. */
const VISIT_RETRY_WINDOW_MS = 12 * 60 * 60 * 1000;
const VISIT_STORAGE_KEY = "bootdisk.besok.v1";
const VISIT_KEY_PATTERN = /^[0-9a-f]{32}$/;
const VISIT_MIN_DIGITS = 6;
const VISIT_MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
  "september", "oktober", "november", "desember"];

function visitParseRecord(text) {
  if (typeof text !== "string") return null;
  let record;
  try {
    record = JSON.parse(text);
  } catch (error) {
    return null;
  }
  if (!record || typeof record !== "object" || !VISIT_KEY_PATTERN.test(record.key)) return null;
  if (!Number.isFinite(record.started) || !Number.isFinite(record.last) || typeof record.confirmed !== "boolean") return null;
  return { key: record.key, started: record.started, last: record.last, confirmed: record.confirmed };
}

/* Bestemmer om denne sidevisningen starter et besøk. `stored` er det som lå i nettleserlagringen
 * (tekst eller null), `now` er klokken i millisekunder og `newKey` lager en ny tilfeldig nøkkel.
 * Svarer med posten som skal lagres og om tjenesten skal telle (`record`) eller bare leses (`read`). */
function visitPlan(stored, now, newKey) {
  const previous = visitParseRecord(stored);
  /* En klokke som går bakover avslutter ikke besøket; det ville telt samme besøk to ganger. */
  if (previous && now - previous.last <= VISIT_IDLE_MS) {
    const record = { ...previous, last: Math.max(now, previous.last) };
    const retry = !record.confirmed && now - record.started <= VISIT_RETRY_WINDOW_MS;
    return { record, action: retry ? "record" : "read" };
  }
  const key = newKey();
  if (!VISIT_KEY_PATTERN.test(key)) throw new Error("Ugyldig besøksnøkkel");
  return { record: { key, started: now, last: now, confirmed: false }, action: "record" };
}

/* Markerer nøkkelen som bekreftet, men bare hvis lagringen fortsatt har samme besøk. En annen fane
 * kan ha startet et nytt besøk mens forespørselen var ute; det skal ikke overskrives. */
function visitConfirm(stored, key) {
  const current = visitParseRecord(stored);
  if (!current || current.key !== key) return null;
  return { ...current, confirmed: true };
}

function visitValidDate(text) {
  if (typeof text !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(text)) return false;
  const [year, month, day] = text.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
}

/* Tjenestens svar godtas bare når totalen er et helt, ikke-negativt tall og startdatoen er en
 * gyldig dato. Alt annet er «Teller utilgjengelig», aldri et gjettet tall. */
function visitParseResponse(body, expectCounted) {
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("Svaret er ikke et objekt");
  if (!Number.isSafeInteger(body.total) || body.total < 0) throw new Error("Ugyldig total");
  if (!visitValidDate(body.since)) throw new Error("Ugyldig startdato");
  if (expectCounted && typeof body.counted !== "boolean") throw new Error("Mangler counted");
  return { total: body.total, since: body.since, counted: expectCounted ? body.counted : undefined };
}

function visitDigits(total) {
  return String(total).padStart(VISIT_MIN_DIGITS, "0");
}

function visitSinceShort(since) {
  const [year, month, day] = since.split("-");
  return `${day}.${month}.${year}`;
}

function visitGrouped(total) {
  return String(total).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

/* Én sammenhengende etikett for skjermlesere, med tallet slik det leses vanlig. */
function visitLabel(total, since) {
  const [year, month, day] = since.split("-").map(Number);
  return `${visitGrouped(total)} besøk siden ${day}. ${VISIT_MONTHS[month - 1]} ${year}`;
}

function visitRandomKey(cryptoImpl) {
  const bytes = new Uint8Array(16);
  cryptoImpl.getRandomValues(bytes);
  return Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}

/* Hele forløpet for én sidevisning. Lagring og lås er injisert slik at testene kan styre klokke,
 * faner og blokkert lagring. Kan ikke besøket lagres, telles det ikke: da ville hver sidevisning
 * blitt et nytt besøk. Totalen leses likevel og vises. */
async function visitRun({ adapter, storage, now, newKey, withLock }) {
  let plan = null;
  try {
    plan = await withLock(() => {
      const planned = visitPlan(storage.getItem(VISIT_STORAGE_KEY), now(), newKey);
      storage.setItem(VISIT_STORAGE_KEY, JSON.stringify(planned.record));
      return planned;
    });
  } catch (error) {
    plan = null;
  }
  if (!plan || plan.action === "read") return { ...(await adapter.read()), recorded: false };
  const result = await adapter.record(plan.record.key);
  try {
    await withLock(() => {
      const confirmed = visitConfirm(storage.getItem(VISIT_STORAGE_KEY), plan.record.key);
      if (confirmed) storage.setItem(VISIT_STORAGE_KEY, JSON.stringify(confirmed));
    });
  } catch (error) {
    /* Neste sidevisning sender samme nøkkel igjen; tjenesten teller den ikke to ganger. */
  }
  return { ...result, recorded: true };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    VISIT_IDLE_MS, VISIT_RETRY_WINDOW_MS, VISIT_STORAGE_KEY, VISIT_MIN_DIGITS, VISIT_KEY_PATTERN,
    visitParseRecord, visitPlan, visitConfirm, visitParseResponse, visitValidDate,
    visitDigits, visitSinceShort, visitGrouped, visitLabel, visitRandomKey, visitRun,
  };
}
