/* Deterministic synthetic first-pass snapshots for the automatic curation queue.
 *
 * PRØVEDATA. Nothing here is a catalogue finding or a result of Catalog's first pass. The
 * snapshots follow docs/automation-queue-v1.md so the page can be tried at scale: by default
 * 125 manifests of 40 entries each (5 000 entries), every manifest numbering its entries
 * K1–K40, so every K-ID exists 125 times. needs_review and protected appear here only as
 * future scenarios; the first real producer emits neither.
 *
 * The page loads this file only when synthetic data is chosen explicitly (?kilde=syntetisk).
 */
const AUTOMATION_SAMPLE_WORDS = [
  ["Kvasar", "Nordlys", "Fjord", "Piksel", "Turbo", "Lynne", "Polar", "Krystall", "Vinter", "Magnet"],
  ["skriv", "tegn", "regn", "kart", "spill", "lyd", "pakk", "tabell", "post", "sjakk"],
];
const AUTOMATION_SAMPLE_RULES = "director-first-pass-1 (prøvedata)";

/* A stable 64-digit hex string for a number; it only has to look like and act like a digest. */
function automationSampleHex(seed) {
  let state = (seed * 2654435761) >>> 0;
  let out = "";
  while (out.length < 64) {
    state = (state * 1103515245 + 12345) >>> 0;
    out += state.toString(16).padStart(8, "0");
  }
  return out.slice(0, 64);
}

function automationSampleManifest(ordinal) {
  return `sha256:${automationSampleHex(ordinal)}`;
}

function sampleEvidence(label, value, manifest, entry, pointer) {
  return { label, value, source_ref: { manifest, entry, pointer } };
}

/* A CD blurb as the menu stored it: leading spaces, CRLF line breaks, and now and then text
 * that looks like markup and must be shown as it is written. */
function sampleDescription(index, title) {
  const lines = [`  ${title} er med på denne CD-en.`, "Krever Windows 95 og 8 MB RAM."];
  if (index % 11 === 0) lines.push('<b>Nyhet!</b> Se "LESMEG.TXT" & <script>alert(1)</script> før installasjon.');
  if (index % 50 === 0) lines.push("Lang omtale. ".repeat(120).trim());
  return `${lines.join("\r\n")}\r\n`;
}

function sampleEntry(ordinal, number, globalIndex) {
  const manifest = automationSampleManifest(ordinal);
  const entry = `K${number}`;
  const first = AUTOMATION_SAMPLE_WORDS[0][globalIndex % 10];
  const second = AUTOMATION_SAMPLE_WORDS[1][Math.floor(globalIndex / 10) % 10];
  const menuName = `${first}${second} ${1 + (globalIndex % 7)}.${globalIndex % 10}`;
  const title = `Prøvepost ${first}${second} ${globalIndex + 1}`;
  const pointer = `/entries/${number - 1}`;
  const name = sampleEvidence("Navn i CD-menyen", menuName, manifest, entry, `${pointer}/normalized/title`);
  const category = sampleEvidence("Kategori i CD-menyen", [globalIndex % 3 ? "games" : "utilities"], manifest, entry,
    `${pointer}/normalized/categories`);
  const text = sampleDescription(globalIndex, menuName);
  const blurb = sampleEvidence("Omtale på CD-en", text, manifest, entry, `${pointer}/evidence/description_source/text/cp1252_view`);
  const kind = globalIndex % 3 ? "game" : "application";

  let stage = (globalIndex + Math.floor(globalIndex / 10)) % 2 ? "inspecting" : "proposals";
  if (globalIndex % 61 === 3) stage = "protected";
  if (globalIndex % 173 === 7) stage = "needs_review";
  const conflict = stage === "needs_review" || (stage === "inspecting" && globalIndex % 7 === 0);

  const field = (fieldName, status, proposed, rule, reason, evidence) => ({ field: fieldName, status, proposed, rule, reason, evidence });
  const versionEvidence = conflict
    ? [sampleEvidence("README – prøvebelegg", `Versjon ${1 + (globalIndex % 3)}.0`, manifest, entry, "/synthetic/readme"),
      sampleEvidence("Programmetadata – prøvebelegg", `Versjon ${2 + (globalIndex % 3)}.1`, manifest, entry, "/synthetic/product_version")]
    : [name];

  let fields;
  let tasks = [];
  if (stage === "protected") {
    const kept = "Prøvedata: eksisterende menneskelig vurdering skal bevares.";
    fields = [
      field("identity", "preserve", null, "identity-needs-package-context-1", kept, [name]),
      field("version", "preserve", null, "version-not-established-1", kept, [name]),
      field("content_kind", "preserve", null, "director-games-section-1", kept, [category]),
      field("distribution_kind", "preserve", null, "edition-not-established-1", kept, []),
      field("description", "preserve", null, "original-description-1", kept, [blurb]),
    ];
  } else {
    const inspecting = stage === "inspecting";
    fields = [
      field("identity", inspecting ? "inspect" : "retain_unknown", null, "identity-needs-package-context-1",
        "Menynavn og identiske installasjonsfiler fastslår ikke programidentitet.", [name]),
      conflict
        ? field("version", "conflict", null, "version-not-established-1", "Prøvedata: to kilder oppgir ulike versjoner.", versionEvidence)
        : field("version", "retain_unknown", null, "version-not-established-1",
          "Versjon er ikke fastslått. Tall i navn og en felles installatør er ikke tilstrekkelig belegg.", versionEvidence),
      field("content_kind", "candidate", kind, "director-games-section-1",
        "Seksjonen i CD-menyen støtter et forslag om innholdstype; det er ikke en godkjenning.", [category]),
      field("distribution_kind", "retain_unknown", null, "edition-not-established-1",
        "Utgaven er ikke fastslått. Freeware betyr ikke fullversjon.", []),
      field("description", "candidate", text, "original-description-1",
        "Bevar den valgte CD-omtalen ordrett, inkludert linjeskift.", [blurb]),
    ];
    if (inspecting) {
      tasks = [
        { code: "inspect_product_context", field: "identity",
          reason: "Undersøk programspesifikk README og installasjonsmetadata uten å kjøre programmet.", evidence: [name] },
        { code: conflict ? "resolve_source_conflict" : "inspect_product_version", field: "version",
          reason: conflict ? "Forsøk å avgjøre hvilken kilde som gjelder programmet før et menneske spørres."
            : "Let etter versjon med dokumentert tilknytning til programmet.", evidence: versionEvidence },
      ];
    }
  }
  return { key: { manifest, entry }, title, stage, requires_human: stage === "needs_review", fields, tasks };
}

/* Summary counts computed the way the contract defines them, so the sample passes the same
 * validation as a real snapshot. */
function automationSampleSummary(entries) {
  const statuses = ["candidate", "retain_unknown", "inspect", "conflict", "preserve"];
  const stages = ["proposals", "inspecting", "needs_review", "protected"];
  const summary = {
    entries: entries.length,
    field_status_counts: Object.fromEntries(statuses.map(status => [status, 0])),
    stage_counts: Object.fromEntries(stages.map(stage => [stage, 0])),
    machine_tasks: 0,
    human_exceptions: 0,
    automatic_decisions: 0,
    human_decisions: 0,
  };
  for (const entry of entries) {
    summary.stage_counts[entry.stage] += 1;
    for (const item of entry.fields) summary.field_status_counts[item.status] += 1;
    summary.machine_tasks += entry.tasks.length;
    if (entry.requires_human) summary.human_exceptions += 1;
  }
  return summary;
}

function createAutomationSampleSnapshots(options = {}) {
  const manifests = options.manifests ?? 125;
  const perManifest = options.perManifest ?? 40;
  const snapshots = [];
  for (let ordinal = 1; ordinal <= manifests; ordinal += 1) {
    const entries = [];
    for (let number = 1; number <= perManifest; number += 1) {
      entries.push(sampleEntry(ordinal, number, (ordinal - 1) * perManifest + (number - 1)));
    }
    snapshots.push({
      schema: "bootdisk-automation-queue-1",
      rules_version: AUTOMATION_SAMPLE_RULES,
      mode: "read_only",
      input: { manifest: automationSampleManifest(ordinal), candidates_sha256: automationSampleHex(10000 + ordinal) },
      entries,
      summary: automationSampleSummary(entries),
    });
  }
  return snapshots;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { createAutomationSampleSnapshots, automationSampleManifest, AUTOMATION_SAMPLE_RULES };
}
