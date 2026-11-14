/* Kontaktskjemaet: DOM-fri kontroll av felter, svar og feilmeldinger.
 *
 * Nettleseren sjekker det samme som api/kontakt.php før den sender, slik at leseren får
 * beskjed med en gang. Serveren kontrollerer alt på nytt; denne filen er bare en hjelp.
 * Se docs/kontaktskjema.md. */

const CONTACT_MAX_MESSAGE = 4000;
const CONTACT_MAX_EMAIL = 254;
const CONTACT_DRAFT_KEY = "bootdisk.kontakt.utkast.v1";
/* Bare disse leverandørene kan lastes. Adressen kommer aldri fra serveren eller konfigurasjonen. */
const CONTACT_CAPTCHA_SCRIPTS = {
  turnstile: "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=bootdiskCaptchaReady",
  hcaptcha: "https://js.hcaptcha.com/1/api.js?render=explicit&onload=bootdiskCaptchaReady",
};
const CONTACT_KEPT = "Meldingen er ikke sendt. Teksten din står fortsatt i skjemaet.";
const CONTACT_MESSAGES = {
  invalid_email: "Skriv inn en e-postadresse vi kan svare til, for eksempel navn@eksempel.no.",
  invalid_message: "Skriv en melding før du sender.",
  message_too_long: `Meldingen er lengre enn ${CONTACT_MAX_MESSAGE} tegn. Kort den ned, eller del den i to meldinger.`,
  captcha_missing: "Bekreft i kontrollen over knappen at du ikke er en robot, og send på nytt.",
  captcha_expired: "Kontrollen ble for gammel før meldingen ble sendt. Bekreft på nytt og send igjen.",
  captcha_rejected: "Kontrollen godtok ikke innsendingen. Bekreft på nytt og send igjen.",
  captcha_unavailable: "Vi fikk ikke sjekket kontrollen mot automatiske innsendinger akkurat nå. Prøv igjen om litt.",
  captcha_load: "Kontrollen mot automatiske innsendinger lastet ikke. Sjekk nettforbindelsen, eller om en innholdsblokkering stopper den, og last siden på nytt.",
  rate_limited: "Det er sendt mange meldinger herfra på kort tid. Vent noen minutter og prøv igjen.",
  not_configured: "Skjemaet kan ikke sende meldinger akkurat nå. Prøv igjen senere.",
  send_failed: "Meldingen kom ikke fram på grunn av en feil hos oss. Prøv igjen senere.",
  forbidden_origin: "Skjemaet kan bare sendes fra bootdisk.no.",
  bad_request: "Skjemaet sendte noe serveren ikke forsto. Last siden på nytt og prøv igjen.",
  method_not_allowed: "Skjemaet sendte noe serveren ikke forsto. Last siden på nytt og prøv igjen.",
  network: "Vi fikk ikke kontakt med serveren. Sjekk nettforbindelsen og prøv igjen.",
  unknown: "Noe gikk galt under sendingen. Prøv igjen senere.",
};
/* Feltene feilen gjelder, så skjermleseren kan knytte meldingen til riktig felt. */
const CONTACT_FIELD_FOR = {
  invalid_email: "email", invalid_message: "message", message_too_long: "message",
  captcha_missing: "captcha", captcha_expired: "captcha", captcha_rejected: "captcha",
};
/* Etter disse må leseren bekrefte på nytt; et brukt token gjelder ikke igjen. */
const CONTACT_RESET_CAPTCHA = new Set(["captcha_expired", "captcha_rejected", "captcha_unavailable", "send_failed", "unknown", "network"]);

function contactValidEmail(value) {
  if (typeof value !== "string") return false;
  const email = value.trim();
  if (!email || email.length > CONTACT_MAX_EMAIL || /[\s,;<>"\\]/.test(email)) return false;
  const at = email.lastIndexOf("@");
  if (at < 1 || at === email.length - 1) return false;
  const domain = email.slice(at + 1);
  return /^[^@.]+(\.[^@.]+)+$/.test(domain) && !/^\.|\.\.|\.$/.test(email.slice(0, at));
}

/** Returnerer en feilkode, eller null når feltene kan sendes. */
function contactCheck(fields) {
  if (!contactValidEmail(fields.email)) return "invalid_email";
  const message = typeof fields.message === "string" ? fields.message.trim() : "";
  if (!message) return "invalid_message";
  if ([...message].length > CONTACT_MAX_MESSAGE) return "message_too_long";
  if (!fields.captcha) return "captcha_missing";
  return null;
}

function contactPayload(fields) {
  return { email: fields.email.trim(), message: fields.message.trim(), captcha: fields.captcha, website: fields.website || "" };
}

/** Tolker svaret fra api/kontakt.php. Alt som ikke er et uttrykkelig ja, er en feil. */
function contactResult(status, body) {
  if (status === 200 && body && body.ok === true) return { ok: true };
  const code = body && typeof body.error === "string" && Object.prototype.hasOwnProperty.call(CONTACT_MESSAGES, body.error) ? body.error : "unknown";
  return { ok: false, error: code };
}

function contactSetup(body) {
  if (!body || body.ready !== true) return { ready: false };
  if (!Object.prototype.hasOwnProperty.call(CONTACT_CAPTCHA_SCRIPTS, body.provider)) return { ready: false };
  if (typeof body.site_key !== "string" || !body.site_key) return { ready: false };
  return { ready: true, provider: body.provider, siteKey: body.site_key, script: CONTACT_CAPTCHA_SCRIPTS[body.provider] };
}

function contactText(code) {
  const text = CONTACT_MESSAGES[code] || CONTACT_MESSAGES.unknown;
  return `${text} ${CONTACT_KEPT}`;
}

function contactParseDraft(text) {
  try {
    const draft = JSON.parse(text);
    if (!draft || typeof draft !== "object") return null;
    return { email: typeof draft.email === "string" ? draft.email : "", message: typeof draft.message === "string" ? draft.message : "" };
  } catch (error) {
    return null;
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    CONTACT_MAX_MESSAGE, CONTACT_DRAFT_KEY, CONTACT_CAPTCHA_SCRIPTS, CONTACT_MESSAGES, CONTACT_FIELD_FOR,
    CONTACT_RESET_CAPTCHA, CONTACT_KEPT, contactValidEmail, contactCheck, contactPayload, contactResult,
    contactSetup, contactText, contactParseDraft,
  };
}
