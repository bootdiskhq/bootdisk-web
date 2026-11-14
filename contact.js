/* Kontaktskjemaet på om-prosjektet.html. Logikken står i contact-core.js; her er bare siden.
 *
 * - Oppsettet hentes fra api/kontakt.php. Er det ikke klart, kan leseren skrive, men ikke sende.
 * - CAPTCHA-skriptet lastes først når leseren begynner å bruke skjemaet, og bare fra
 *   leverandørene i CONTACT_CAPTCHA_SCRIPTS.
 * - Teksten tømmes bare etter en bekreftet sending. Et utkast holdes i sessionStorage, så
 *   en omlasting eller en feil ikke mister meldingen. Se docs/kontaktskjema.md. */
(function () {
  const ENDPOINT = "api/kontakt.php";
  const SEND_TIMEOUT_MS = 20000;
  const SETUP_TIMEOUT_MS = 8000;
  const CAPTCHA_TIMEOUT_MS = 15000;

  const form = document.getElementById("contact-form");
  if (!form) return;
  const email = document.getElementById("contact-email");
  const message = document.getElementById("contact-message");
  const website = document.getElementById("contact-website");
  const captchaBox = document.getElementById("contact-captcha");
  const captchaNote = document.getElementById("contact-captcha-note");
  const submit = document.getElementById("contact-submit");
  const feedback = document.getElementById("contact-feedback");
  const counter = document.getElementById("contact-count");

  let setup = null;
  let setupRequest = null;
  let token = "";
  let widget = null;
  let captchaState = "idle";
  let sending = false;

  function storage() {
    try {
      return window.sessionStorage;
    } catch (error) {
      return null;
    }
  }

  function saveDraft() {
    const store = storage();
    if (!store) return;
    try {
      if (!email.value && !message.value) store.removeItem(CONTACT_DRAFT_KEY);
      else store.setItem(CONTACT_DRAFT_KEY, JSON.stringify({ email: email.value, message: message.value }));
    } catch (error) {
      /* Uten lagring står teksten fortsatt i feltene så lenge siden er åpen. */
    }
  }

  function restoreDraft() {
    const store = storage();
    if (!store) return;
    let draft = null;
    try {
      draft = contactParseDraft(store.getItem(CONTACT_DRAFT_KEY));
    } catch (error) {
      draft = null;
    }
    if (!draft) return;
    if (!email.value) email.value = draft.email;
    if (!message.value) message.value = draft.message;
  }

  function clearDraft() {
    const store = storage();
    try {
      if (store) store.removeItem(CONTACT_DRAFT_KEY);
    } catch (error) {
      /* ingenting å rydde */
    }
  }

  function updateCount() {
    const used = [...message.value].length;
    counter.textContent = `${used} av ${CONTACT_MAX_MESSAGE} tegn`;
    counter.dataset.over = used > CONTACT_MAX_MESSAGE ? "true" : "false";
  }

  function markField(field) {
    for (const input of [email, message]) input.removeAttribute("aria-invalid");
    captchaBox.removeAttribute("data-invalid");
    if (field === "email") email.setAttribute("aria-invalid", "true");
    if (field === "message") message.setAttribute("aria-invalid", "true");
    if (field === "captcha") captchaBox.setAttribute("data-invalid", "true");
  }

  function show(state, text) {
    feedback.hidden = false;
    feedback.dataset.state = state;
    feedback.setAttribute("role", state === "error" ? "alert" : "status");
    feedback.textContent = text;
  }

  function showError(code) {
    const field = CONTACT_FIELD_FOR[code] || null;
    markField(field);
    show("error", contactText(code));
    if (field === "email") email.focus();
    else if (field === "message") message.focus();
    else feedback.focus();
  }

  function setCaptchaNote(state, text) {
    captchaState = state;
    captchaBox.dataset.state = state;
    captchaNote.textContent = text;
  }

  function withTimeout(ms, run) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timer = setTimeout(() => controller && controller.abort(), ms);
    return run(controller ? controller.signal : undefined).finally(() => clearTimeout(timer));
  }

  function loadSetup() {
    if (setupRequest) return setupRequest;
    setupRequest = withTimeout(SETUP_TIMEOUT_MS, signal => fetch(ENDPOINT, { headers: { Accept: "application/json" }, cache: "no-store", signal })
      .then(response => (response.ok ? response.json() : null)))
      .then(body => contactSetup(body))
      .catch(() => ({ ready: false }))
      .then(result => {
        setup = result;
        if (!result.ready) {
          setCaptchaNote("unavailable", "Skjemaet tar ikke imot meldinger akkurat nå. Du kan skrive meldingen, men den kan ikke sendes før skjemaet er i drift igjen.");
          setupRequest = null; // neste forsøk spør serveren på nytt
        } else if (captchaState === "idle") {
          setCaptchaNote("idle", "Før sending ber vi deg bekrefte at du ikke er en robot. Kontrollen lastes fra en ekstern leverandør når du begynner å fylle ut skjemaet.");
        }
        return result;
      });
    return setupRequest;
  }

  function captchaApi() {
    return setup && setup.ready ? window[setup.provider] : null;
  }

  function renderCaptcha() {
    const api = captchaApi();
    if (!api || typeof api.render !== "function" || widget !== null) return;
    captchaBox.querySelector(".contact-captcha-widget").replaceChildren();
    widget = api.render(captchaBox.querySelector(".contact-captcha-widget"), {
      sitekey: setup.siteKey,
      callback(value) {
        token = typeof value === "string" ? value : "";
        markField(null);
        setCaptchaNote("ready", "Bekreftet. Du kan sende meldingen.");
      },
      "expired-callback"() {
        token = "";
        setCaptchaNote("expired", "Bekreftelsen er utløpt. Bekreft på nytt før du sender.");
      },
      "error-callback"() {
        token = "";
        setCaptchaNote("error", CONTACT_MESSAGES.captcha_load);
      },
    });
    setCaptchaNote("waiting", "Bekreft at du ikke er en robot.");
  }

  function loadCaptcha() {
    return loadSetup().then(result => {
      if (!result.ready || captchaState === "loading" || widget !== null) return;
      if (captchaApi()) {
        renderCaptcha();
        return;
      }
      setCaptchaNote("loading", "Laster kontrollen mot automatiske innsendinger …");
      window.bootdiskCaptchaReady = renderCaptcha;
      const script = document.createElement("script");
      script.src = result.script;
      script.async = true;
      script.defer = true;
      const timer = setTimeout(() => {
        if (widget === null) setCaptchaNote("error", CONTACT_MESSAGES.captcha_load);
      }, CAPTCHA_TIMEOUT_MS);
      script.addEventListener("load", () => {
        clearTimeout(timer);
        if (widget === null && captchaApi()) renderCaptcha();
      });
      script.addEventListener("error", () => {
        clearTimeout(timer);
        setCaptchaNote("error", CONTACT_MESSAGES.captcha_load);
        script.remove();
      });
      document.head.appendChild(script);
    });
  }

  function resetCaptcha() {
    token = "";
    const api = captchaApi();
    if (api && widget !== null && typeof api.reset === "function") {
      try {
        api.reset(widget);
      } catch (error) {
        /* et nytt forsøk lager kontrollen på nytt */
      }
      setCaptchaNote("waiting", "Bekreft på nytt at du ikke er en robot.");
    }
  }

  function setSending(on) {
    sending = on;
    submit.disabled = on;
    form.setAttribute("aria-busy", on ? "true" : "false");
    submit.textContent = on ? "Sender …" : "Send melding";
  }

  async function send(event) {
    event.preventDefault();
    if (sending) return;
    const fields = { email: email.value, message: message.value, captcha: token, website: website.value };
    const fieldProblem = contactCheck({ ...fields, captcha: "-" });
    if (fieldProblem) {
      showError(fieldProblem);
      return;
    }
    const current = await loadSetup();
    if (!current.ready) {
      showError("not_configured");
      return;
    }
    if (!token) {
      loadCaptcha();
      showError(captchaState === "error" ? "captcha_load" : "captcha_missing");
      return;
    }
    setSending(true);
    show("sending", "Sender meldingen …");
    let result;
    try {
      result = await withTimeout(SEND_TIMEOUT_MS, signal => fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(contactPayload(fields)),
        cache: "no-store",
        signal,
      }).then(async response => contactResult(response.status, await response.json().catch(() => null))));
    } catch (error) {
      result = { ok: false, error: "network" };
    }
    setSending(false);
    if (result.ok) {
      const replyTo = email.value.trim();
      message.value = "";
      updateCount();
      clearDraft();
      saveDraft();
      markField(null);
      resetCaptcha();
      show("sent", `Takk! Meldingen er sendt. Vi svarer til ${replyTo} når vi har sett på den.`);
      feedback.focus();
      return;
    }
    if (CONTACT_RESET_CAPTCHA.has(result.error)) resetCaptcha();
    if (result.error === "not_configured") setupRequest = null;
    showError(result.error);
  }

  restoreDraft();
  updateCount();
  form.addEventListener("input", () => {
    saveDraft();
    updateCount();
  });
  form.addEventListener("focusin", () => loadCaptcha(), { once: true });
  form.addEventListener("submit", send);
  form.dataset.ready = "true";
  loadSetup();
})();
