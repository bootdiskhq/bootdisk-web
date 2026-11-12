# Arkivet: vis bare en type eller et CD-år, og sorter

`archive.html` har to nye filtre og tre nye sorteringer. Filtrene («Innholdstype», «CD-år»)
bestemmer *hvilke* poster som vises; «Sorter etter» bestemmer bare *rekkefølgen* og endrer
aldri treffmengden. Alt kombineres med søk, status og valgt CD.

## Innholdstype i arkivet

Én regel (`archiveKind` i `archive.js`, speilet i `scripts/archive_index.py`) gir hver post én
arkivtype, og den samme typen brukes i filter, sortering og rad:

1. Kjent `content_kind` fra Catalog brukes først (Program, Spill, Kurs / veiledning,
   Bildesamling, Skriftpakke, Oppslagsverk). Den vinner også over en motstridende menygruppe.
2. Ellers brukes CD-ens egne menygrupper (`source_context.menu_groups.value`), bare disse
   eksakte kildeverdiene:

   | Menygruppe på CD-en | Arkivtype |
   |---|---|
   | `Spill`, `Spil`, `games` | Spill |
   | `Videokurs` | Kurs / veiledning |
   | `KProgram`, `programs`, `Software` | Program |
   | `Artikler` | Artikkel |

   Flere grupper som peker til samme type er greit. Grupper som peker til ulike typer gir
   «Ikke oppgitt». Alle andre grupper (`Demoer`, `Barn`, `Bonus`, `Aktuelt`, `Tilbehør`, …)
   sier ingenting om typen alene. Raden viser grunnlaget: «Spill (CD-meny)».
3. Ellers «Ikke oppgitt».

Tittel, filnavn, omtale og AI brukes aldri. Originalgruppen og identifikasjonsstatusen er
uendret; detaljsiden er ikke endret (den viser fortsatt bare Catalogs `content_kind`).
«Demo» (`distribution_kind`) er utgave, ikke type: en demo uten annen type er «Ikke oppgitt».

## CD-år og sortering

CD-året er utgivelsesåret til CD-en, lest fra CD-etiketten med `parseIssue` («K-CD 10/2001»
→ 2001, utgave 10). Ikke programversjon, ikke publiseringsdato. En etikett uten år gir
«Ikke oppgitt».

| `sort=` | Etikett | Rekkefølge |
|---|---|---|
| (ingen) | Kilderekkefølge | Standard, som før |
| `name` | Navn A–Å | Synlig tittel, norsk alfabet (… Z Æ Ø Å), så kildeorden |
| `type` | Innholdstype A–Å | Typenavn A–Å, ukjent sist; lik type på synlig tittel, så kildeorden/ID |
| `year-desc` | CD-år: nyeste først | År, så utgavenummer som tall (10 før 2), så kildeorden på CD-en; ukjent år sist |
| `year-asc` | CD-år: eldste først | Samme, motsatt retning (2 før 10); ukjent år fortsatt sist |

Filtervalgene utledes fra data: alle år og typer som finnes, pluss «Ikke oppgitt» når noe
mangler. Program, Spill og Kurs / veiledning vises alltid, slik at «Spill» er et eget valg.

## URL-parametre

Alle eksisterende parametre virker som før (`q`, `medium`, `status`, `sort=name`).

| Parameter | Verdier |
|---|---|
| `type` | `application`, `game`, `course`, `article`, `image_collection`, `font_collection`, `reference`, `unknown` |
| `year` | firesifret CD-år som finnes i arkivet, eller `unknown` |
| `sort` | `name`, `type`, `year-desc`, `year-asc` (utelatt = kilderekkefølge) |

Eksempler: `archive.html?type=game&sort=year-desc`, `archive.html?type=course&year=2001`.
Siden skriver valgene tilbake i adressen (`replaceState`), så oppfrisking og tilbakeknappen
etter en post gir samme valg, rekkefølge og treffantall. Hver parameter leses for seg: en ukjent
`type` eller `year` gir en melding og «alle» for akkurat den, mens de andre valgene står. En
gyldig kombinasjon uten treff viser «Ingen poster passer med filtrene» med knappen «Nullstill
filtrene». Nullstill går tilbake til standardvisningen.

## Arkivindeksen: `menu_groups` ved bygging

Nettleseren leser bare `data/index.json`; den henter aldri detaljposter for å filtrere. Derfor
får hver indeksrad et valgfritt felt `menu_groups`, en uendret kopi av postens egen
`source_context.menu_groups.value`. Feltet mangler når kilden ikke har observasjonen.

- `scripts/build-collection.py` og `scripts/append-source-posts.py` setter feltet. Ved
  tillegg av poster får også de tidligere radene feltet fra sine (uendrede) detaljposter.
- `scripts/frontend_contract.py` avviser en rad der `menu_groups` ikke er lik postens egen
  observasjon. En indeks uten feltet er fortsatt gyldig.
- Eldre indeks uten feltet: arkivet virker, men bare kjent `content_kind` gir type; resten er
  «Ikke oppgitt».
- Detaljposter, historikk (`public-updates.json`) og fingeravtrykket i `public_updates.py`
  er uendret, så endringen gir ingen publiseringshendelser.

**Komplett indeks for allerede bygde data (også rc27), uten ny ISO-innlesing:**

```sh
python3 scripts/archive_index.py /sti/til/data --output /sti/til/ny-data --groups
```

Skriptet kopierer alle filer byte for byte, skriver bare `index.json` på nytt, validerer med
kontraktporten og skriver typefordelingen før og etter, med alle menygruppeverdier og hvor
ofte de forekommer. Uten `--output` rapporterer det bare. Den nye datamappen bygges deretter
til release som før (`scripts/build-release.py`). Ingen annen komponent trengs: menygruppene
finnes allerede i Webs detaljposter fra Catalog/Ingest. Ingen endring i Catalog-kontrakten.

## Måling på rc27 (Birks lokale pakke, 2026-11-11)

Ekte `index.json` fra `bootdisk-web-1.2.0-rc27/data`: 3533 poster på 73 CD-er.

| Type (gammel indeks, bare `content_kind`) | Antall |
|---|---|
| Program | 15 |
| Spill | 13 |
| Kurs / veiledning | 7 |
| Bildesamling | 2 |
| Skriftpakke | 1 |
| Oppslagsverk | 1 |
| Ikke oppgitt | 3494 |

CD-år i rc27: 2000: 229, 2001: 959, 2002: 339, 2008: 246, 2009: 137, 2012: 212, 2013: 534,
2014: 686, 2015: 191. Ingen ukjente år.

Fordelingen *etter* utvidelse er ikke målt på hele rc27: Macen hadde for lite ledig plass til
at skallmiljøet startet, så detaljpostene kunne bare hentes enkeltvis. Utvidelsen er prøvd på
37 ekte detaljposter (stikkprøve over CD-ene): 4 Spill og 4 Program fra Catalog, 1 Skriftpakke,
3 Spill, 2 Kurs, 2 Program og 1 Artikkel fra CD-menyen, 20 «Ikke oppgitt». Funn i stikkprøven:

- «Skole» beskriver menyplassering og vises som «På CD-en: Skole». Det gir ikke kurs alene. En dokumentert type eller en entydig gruppe som «Videokurs» avgjør typen.
- CD-ene fra 2008 har tomme menygrupper, så de blir «Ikke oppgitt» uansett.
- Hyppige grupper uten type: `Tilbehør`, `Internet`, `Galleri`, `Værksted`, `tools`,
  `Verktøykassa`, `Sikkerhetssenteret`, `Demoer`, `Aktuelt`.

## Tester

- `tests/test_archive_sort_filter.py`: typeregelen (28 tilfeller, samme svar i JS og Python),
  sortering (2 vs 10, Æ/Ø/Å, lik tittel på ulike CD-er, ukjent sist, stabil, aldri endret
  mengde), kombinerte filtre, parametre, byggesteg, kontrakt, gammel indeks, historikk og
  nettleser på PRØVEDATA (`tests/synthetic_archive.py`): spillakseptanse, A–Å med samme treff,
  kurs uten `content_kind`, direkte URL → post → tilbake → oppfrisk → nullstill, nulltreff,
  320 og 375 px, tastaturrekkefølge og fokus, ingen detaljforespørsler.
- `RealArchiveAcceptance` i samme fil kjører bare med ekte data (se under).

## Reell akseptanse for Birk

```sh
cd bootdisk-web   # denne grenen
pip install playwright && playwright install chromium   # om nødvendig
BOOTDISK_ARCHIVE_DATA=/Users/stian/Bootdisk/local-results/releases/bootdisk-web-1.2.0-rc27/data \
  python3 -m unittest tests.test_archive_sort_filter.RealArchiveAcceptance -v
```

Den leser bare rc27-mappen, utvider en kopi i en midlertidig mappe, skriver typefordelingen
før og etter, og kontrollerer: kildefilene er byte-identiske etterpå, samme poster og
fingeravtrykk, `?type=game&sort=year-desc` har både registrert spill og spill fra CD-menyen og
ingen rene «Demoer»-poster, A–Å gir samme treff, og Acrobat Reader under «Skole» utelates fra kursfilteret. For å se siden selv: kjør `scripts/archive_index.py` som over, legg den nye
datamappen i en kopi av rc27-pakken med denne grenens sider, og åpn `archive.html?type=game&sort=year-desc`.

## Skjermbilder

I `docs/archive-sort-filter/`. Ikonene er fjernet i bildene fra rc27 (butikken var ikke hentet).

1. rc27, gammel indeks: Spill, nyeste CD først (13 treff, bare Catalog-typer).
2. rc27 med menygrupper for de 37 stikkprøvene: Spill, nyeste først (16 treff, tre fra CD-menyen).
3. Samme, 375 px: Kurs / veiledning + 2001 (sju treff; Acrobat Reader under «Skole» er ikke med).
4. Samme, 320 px: Spill, Navn A–Å.
5. PRØVEDATA: Spill, nyeste først.
6. PRØVEDATA, 375 px: gyldig kombinasjon uten treff.
