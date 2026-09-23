/* Deterministic synthetic dataset for the curator overview prototype.
 *
 * Every program here is invented for the scale test. These records are not catalogue
 * findings and must never be mixed with real curation. Nothing is stored on disk: the
 * whole dataset is regenerated from a fixed seed, so two runs produce identical rows.
 *
 * The archive grows one CD at a time, so the sample models many small manifests rather
 * than one huge one. A K-id repeats in every manifest, which is exactly why the overview
 * must treat manifest plus entry as the identity of a row.
 */
const OVERVIEW_SAMPLE_SCHEMA = "bootdisk-curator-v1";
const OVERVIEW_SAMPLE_DATASET = "overview-sample-v1";
const OVERVIEW_SAMPLE_STORAGE_VERSION = 1;
const OVERVIEW_SAMPLE_MANIFEST_COUNT = 125;

const SAMPLE_PREFIX = ["Kvasar", "Fjordvox", "Nimbus", "Tindra", "Bolverk", "Ravnsky", "Glimt", "Torden", "Vardø", "Skjærgård", "Solvind", "Myrull"];
const SAMPLE_STEM = ["skriv", "kalkyle", "tegn", "arkiv", "lyd", "spill", "kart", "font", "bilde", "leksikon", "plan", "verktøy"];
const SAMPLE_SUFFIX = ["", "", " Pro", " Lite", " 2000", " Deluxe", " for Windows", " Norsk utgave", " Komplett samling for hjem, skole og kontor"];
const SAMPLE_CONTENT_KINDS = ["application", "game", "course", "image_collection", "font_collection", "reference"];
const SAMPLE_DISTRIBUTION_KINDS = ["full", "demo", "trial", "update"];
const SAMPLE_VERSIONS = ["1.0", "1.2", "1.4.1", "2.0", "2.5b", "3.11", "97", "2000"];
const SAMPLE_LICENSES = ["Freeware", "Shareware", "Demo", "Fullversjon"];

/* A small, fixed pool that deliberately repeats: the overview has to keep rows with the
 * same program name apart and paginate them without losing or duplicating any. */
const SAMPLE_REPEATED_NAMES = ["Kvasarskriv", "Nimbuskart", "Tindraspill"];

function sampleRandom(seed) {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
}

function sampleHex(random, length) {
  let out = "";
  while (out.length < length) out += Math.floor(random() * 16).toString(16);
  return out.slice(0, length);
}

function samplePick(random, values) {
  return values[Math.floor(random() * values.length)];
}

function sampleSlug(name) {
  return name.toLocaleLowerCase("nb-NO").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function sampleManifestAt(index) {
  const number = String(index + 1).padStart(3, "0");
  return {
    index,
    slug: `cd${number}`,
    label: `Syntetisk CD ${number}`,
    id: `sha256:${sampleHex(sampleRandom(0x51de0000 + index * 40961), 64)}`,
    /* 36–48 entries per disc, the order of magnitude of a real K-CD. */
    entries: 36 + (index % 13),
  };
}

const OVERVIEW_SAMPLE_MANIFESTS = Array.from({ length: OVERVIEW_SAMPLE_MANIFEST_COUNT }, (_, index) => sampleManifestAt(index));
const OVERVIEW_SAMPLE_TOTAL = OVERVIEW_SAMPLE_MANIFESTS.reduce((sum, manifest) => sum + manifest.entries, 0);

function sampleManifest(reference) {
  const found = OVERVIEW_SAMPLE_MANIFESTS.find(item => item.id === reference || item.slug === reference);
  if (!found) throw new Error(`Ukjent syntetisk kildepost: ${reference}`);
  return found;
}

/* Browser storage key the fixture adapter uses for one synthetic manifest. The overview
 * reads it so decisions already taken in the detail screen are visible; it never writes
 * it. This coupling is prototype-only and disappears once Catalog serves the real read
 * contract. */
function sampleDatasetId(reference) {
  return `${OVERVIEW_SAMPLE_DATASET}/${sampleManifest(reference).slug}`;
}

function sampleStorageKey(reference) {
  return `${OVERVIEW_SAMPLE_SCHEMA}/v${OVERVIEW_SAMPLE_STORAGE_VERSION}/${sampleDatasetId(reference)}`;
}

/* One entry's deterministic decisions. The full document and the overview summary are both
 * derived from this, so the two views of the same entry cannot drift apart. */
function sampleProfile(manifest, index) {
  const random = sampleRandom(0x5eed0000 + manifest.index * 100003 + index * 7919);
  const repeated = index % 37 === 0;
  const name = repeated
    ? SAMPLE_REPEATED_NAMES[(manifest.index + index) % SAMPLE_REPEATED_NAMES.length]
    : `${samplePick(random, SAMPLE_PREFIX)}${samplePick(random, SAMPLE_STEM)}${samplePick(random, SAMPLE_SUFFIX)}`;

  const versionKnown = random() < 0.6;
  const distributionKnown = random() < 0.55;
  const contentSupported = random() < 0.8;
  const identityKnown = random() < 0.72;
  const roll = random();
  const queueState = roll < 0.55 ? "pending" : roll < 0.65 ? "deferred" : "reviewed";
  const hasAccepted = queueState === "reviewed" || random() < 0.85;
  const draftEdited = random() < 0.2;
  const reviewRoll = random();
  const proposalRoll = random();

  return {
    entry: `K${index + 1}`,
    name,
    /* Every fourth entry carries a verbatim CD description, so the prototype exercises the
     * read-only original text the catalogue restores rather than only editable ones. */
    originalDescription: index % 4 === 0,
    slug: sampleSlug(name),
    license: samplePick(random, SAMPLE_LICENSES),
    version: versionKnown ? samplePick(random, SAMPLE_VERSIONS) : "unknown",
    versionKnown,
    draftVersion: samplePick(random, SAMPLE_VERSIONS),
    draftEdited,
    contentKind: samplePick(random, SAMPLE_CONTENT_KINDS),
    contentSupported,
    distributionKind: distributionKnown ? samplePick(random, SAMPLE_DISTRIBUTION_KINDS) : "unknown",
    distributionKnown,
    identityKnown,
    queueState,
    hasAccepted,
    reviewRequiredField: reviewRoll < 0.08 ? (reviewRoll < 0.04 ? "content_kind" : "distribution_kind") : null,
    proposalVersion: proposalRoll < 0.15 ? SAMPLE_VERSIONS[Math.floor(proposalRoll * 100) % SAMPLE_VERSIONS.length] : null,
  };
}

/* The CD's own words about the program, which is what the source document carries. */
function sampleSourceDescription(profile) {
  return `Syntetisk omtale av ${profile.name}. Oppdiktet tekst for skalatesten.`;
}

/* Some entries have had that text restored verbatim by the catalogue. For those, the
 * description claim is exactly the source text and the detail screen keeps it read-only,
 * the same rule the local service enforces. */
function sampleOriginalDescription(profile) {
  return profile.originalDescription ? sampleSourceDescription(profile) : null;
}

function sampleClaim(value, assessment, evidenceIds, reason) {
  return { value, assessment, evidence_ids: evidenceIds, reason };
}

function sampleClaims(profile, evidenceIds) {
  return {
    identity: profile.identityKnown
      ? sampleClaim({ software_id: `software:${profile.slug}`, name: profile.name }, "accepted", evidenceIds, "")
      : sampleClaim({ software_id: null, name: profile.name }, "unresolved", evidenceIds, "Identiteten er ikke fastslått i prøvedataene."),
    /* «unknown» version and distribution must stay unresolved: neither can be approved as a
     * supported claim, and a licence label does not establish an edition. */
    version: profile.versionKnown
      ? sampleClaim(profile.version, "accepted", evidenceIds, "")
      : sampleClaim("unknown", "unresolved", evidenceIds, "Versjonen er ikke oppgitt i prøvedataene."),
    content_kind: profile.contentSupported
      ? sampleClaim(profile.contentKind, "accepted", evidenceIds, "")
      : sampleClaim(profile.contentKind, "unresolved", evidenceIds, "Innholdstypen trenger en kilde som faktisk støtter den."),
    distribution_kind: profile.distributionKnown
      ? sampleClaim(profile.distributionKind, "accepted", evidenceIds, "")
      : sampleClaim("unknown", "unresolved", evidenceIds, "Lisensen alene fastslår ikke utgaven."),
    description: sampleClaim(
      {
        language: "nb-NO",
        text: sampleOriginalDescription(profile)
          ?? `Syntetisk oppføring for ${profile.name}, laget for å måle oversikten.`,
      },
      "accepted", evidenceIds, "",
    ),
  };
}

function sampleIssues(profile) {
  if (!profile.reviewRequiredField) return [];
  return [{
    code: "classification_review_required",
    field: profile.reviewRequiredField,
    message: "Tidligere klassifisering mangler en kilde som støtter den. Kontroller den på nytt.",
  }];
}

function sampleEntry(manifest, index) {
  const profile = sampleProfile(manifest, index);
  /* A separate stream for cosmetic digests, so changing them can never shift the decisions
   * above. */
  const random = sampleRandom(0x0d1e0000 + manifest.index * 65537 + index * 271);
  const evidence = [
    {
      id: `${profile.entry}-e1`,
      source_ref: { manifest: manifest.id, entry: profile.entry, path: `${profile.slug}/omtale.txt` },
      field: "normalized.description",
      observation: sampleSourceDescription(profile),
    },
    {
      id: `${profile.entry}-e2`,
      source_ref: { manifest: manifest.id, entry: profile.entry },
      field: "raw.Licens",
      observation: profile.license,
    },
  ];
  const evidenceIds = [evidence[0].id];
  const claims = sampleClaims(profile, evidenceIds);
  const draft = { claims: JSON.parse(JSON.stringify(claims)) };
  /* A fifth of the entries carry an edited draft, so the overview has to keep a draft
   * apart from the last approved value. */
  if (profile.draftEdited) {
    draft.claims.version = sampleClaim(profile.draftVersion, "accepted", evidenceIds, "Rettet i kladden, ikke godkjent.");
  }

  return {
    schema: OVERVIEW_SAMPLE_SCHEMA,
    /* A flag, exactly as the local service reports it; the protected text is the source
     * description below. */
    ...(profile.originalDescription ? { original_description_v1: true } : {}),
    key: { manifest: manifest.id, entry: profile.entry },
    revision: `sample-${manifest.slug}-${profile.entry}-0`,
    queue_state: profile.queueState,
    source: {
      title: profile.name,
      description: sampleSourceDescription(profile),
      target: { kind: "package", id: `package:sha256:${sampleHex(random, 64)}` },
      members: [{ path: `${profile.slug}/setup.exe`, size: 100000 + Math.floor(random() * 900000), sha256: sampleHex(random, 64) }],
    },
    accepted: profile.hasAccepted
      ? { identification_status: profile.identityKnown ? "curated" : "interpreted", claims }
      : null,
    draft,
    proposals: profile.proposalVersion
      ? [{ field: "version", value: profile.proposalVersion, evidence_ids: evidenceIds, reason: "Syntetisk forslag fra prøvedataene." }]
      : [],
    evidence,
    issues: sampleIssues(profile),
  };
}

/* One manifest's bundle, in the same shape the fixture adapter already consumes, so the
 * detail screen keeps its existing decision semantics unchanged. */
function createSampleBundle(reference, options = {}) {
  const manifest = sampleManifest(reference);
  const count = options.count ?? manifest.entries;
  const entries = [];
  for (let index = 0; index < count; index += 1) entries.push(sampleEntry(manifest, index));
  return {
    schema: OVERVIEW_SAMPLE_SCHEMA,
    fixture_only: true,
    synthetic: true,
    manifest_label: manifest.label,
    note: "Syntetiske prøvedata for skalatesten. Oppdiktede programmer, ikke katalogfunn.",
    entries,
  };
}

/* The prototype summary layer: one record per entry, without building a full entry
 * document for any of them. `summarise` is applied as each record is produced, so only the
 * lean overview rows are retained. The real service is expected to answer this from its
 * own index instead. */
function sampleSummaries(summarise, options = {}) {
  const manifests = options.manifests ?? OVERVIEW_SAMPLE_MANIFESTS;
  const rows = [];
  for (const manifest of manifests) {
    const count = options.entriesPerManifest ?? manifest.entries;
    for (let index = 0; index < count; index += 1) {
      rows.push(summarise(sampleRecord(manifest, index)));
    }
  }
  return rows;
}

/* The review state of one entry, in the same shape the entry document carries it. */
function sampleRecord(manifest, index) {
  const profile = sampleProfile(manifest, index);
  return {
    key: { manifest: manifest.id, entry: profile.entry },
    manifest_label: manifest.label,
    title: profile.name,
    queue_state: profile.queueState,
    accepted: profile.hasAccepted
      ? { identification_status: profile.identityKnown ? "curated" : "interpreted", claims: sampleClaims(profile, [`${profile.entry}-e1`]) }
      : null,
    draft: { claims: sampleDraftClaims(profile) },
    issues: sampleIssues(profile),
  };
}

function sampleDraftClaims(profile) {
  const evidenceIds = [`${profile.entry}-e1`];
  const claims = sampleClaims(profile, evidenceIds);
  if (profile.draftEdited) {
    claims.version = sampleClaim(profile.draftVersion, "accepted", evidenceIds, "Rettet i kladden, ikke godkjent.");
  }
  return claims;
}

function sampleManifestLabels() {
  return new Map(OVERVIEW_SAMPLE_MANIFESTS.map(manifest => [manifest.id, manifest.label]));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    createSampleBundle,
    sampleSummaries,
    sampleRecord,
    sampleManifestLabels,
    sampleDatasetId,
    sampleStorageKey,
    sampleManifest,
    sampleProfile,
    OVERVIEW_SAMPLE_MANIFESTS,
    OVERVIEW_SAMPLE_TOTAL,
    OVERVIEW_SAMPLE_DATASET,
    OVERVIEW_SAMPLE_SCHEMA,
  };
}
