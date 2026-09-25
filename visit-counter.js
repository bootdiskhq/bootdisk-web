/* Viser besøkstelleren i den felles bunnteksten. Telleren er av når visit-counter-config.js ikke
 * har en adresse, eller når siden ikke kjører på den konfigurerte produksjonsadressen. Da gjøres
 * ingen forespørsel og feltet forblir skjult: lokal utvikling, tester og forhåndsvisninger teller
 * aldri mot produksjon. */
(function () {
  const root = document.getElementById("visit-counter");
  if (!root) return;
  const config = window.BOOTDISK_VISIT_COUNTER;
  if (!config || typeof config.endpoint !== "string" || !config.endpoint || config.origin !== window.location.origin) {
    root.hidden = true;
    return;
  }

  const digits = document.createElement("span");
  digits.className = "visit-counter-digits";
  digits.setAttribute("aria-hidden", "true");
  const caption = document.createElement("span");
  caption.className = "visit-counter-caption";
  caption.setAttribute("aria-hidden", "true");
  const text = document.createElement("span");
  text.className = "visit-counter-text";

  function cells(value) {
    digits.replaceChildren(...Array.from(value, character => {
      const cell = document.createElement("span");
      cell.className = "visit-counter-digit";
      cell.textContent = character;
      return cell;
    }));
  }

  function show(state) {
    root.dataset.state = state;
    root.hidden = false;
  }

  /* Tomme sifferfelt holder plassen mens totalen hentes, så bunnteksten ikke hopper. */
  cells(" ".repeat(VISIT_MIN_DIGITS));
  caption.textContent = "Besøk";
  text.textContent = "Besøkstelleren lastes";
  root.replaceChildren(digits, caption, text);
  show("pending");

  let storage = null;
  try {
    storage = window.localStorage;
  } catch (error) {
    storage = null;
  }
  const blocked = { getItem() { throw new Error("Lagring er blokkert"); }, setItem() { throw new Error("Lagring er blokkert"); } };
  const withLock = navigator.locks && typeof navigator.locks.request === "function"
    ? fn => navigator.locks.request("bootdisk-besok", fn)
    : fn => Promise.resolve().then(fn);

  visitRun({
    adapter: createHttpVisitCounterAdapter({ endpoint: config.endpoint, fetchImpl: window.fetch.bind(window), parse: visitParseResponse }),
    storage: storage || blocked,
    now: () => Date.now(),
    newKey: () => visitRandomKey(window.crypto),
    withLock,
  }).then(result => {
    cells(visitDigits(result.total));
    caption.textContent = `Besøk siden ${visitSinceShort(result.since)}`;
    text.textContent = visitLabel(result.total, result.since);
    show("ready");
  }).catch(() => {
    root.replaceChildren(Object.assign(document.createElement("span"), { className: "visit-counter-unavailable", textContent: "Teller utilgjengelig" }));
    show("unavailable");
  });
})();
