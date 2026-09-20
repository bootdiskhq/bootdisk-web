# Kurateringsoversikt — prototype

Første frontend-prototype for å holde oversikt over flere tusen programoppføringer.
Detaljvisningen er uendret: oversikten leverer en rad til den eksisterende
kurateringsflyten i `curate.html`, og tar imot kuratoren tilbake på samme sted.

| | |
| --- | --- |
| Web-utgangspunkt | `4999251ec06968cc3c2df8129349d0b3d5cd2b70` (main) |
| Catalog-utgangspunkt | `2dacd311da561734875ead83f3e8f86a188708f0` (main) |
| Arbeidsordre | `docs/claude-curator-overview-work-order.md` |
| Dokumenter | ADR-004, ADR-005, ADR-006, `curator-contract-v1.md`, `local-curator-service.md` |

Arbeidsordren oppga `39965560…` som Web-utgangspunkt. Grenen ble bygget på `4999251…`
(arbeidsordren selv, #34) og har siden fått main flettet inn til og med `afa087a…` (#35).
`curator-labels.js` gjorde de norske etikettene til en avhengighet for `curate.js`, så
testen fra #35 laster dem nå i sin VM-kontekst slik siden gjør.

## Start prøvevisningen

Oversikten er statiske filer og trenger ingen tjeneste. Bruk en egen port, slik at
kurateringen din på 8772 ikke berøres:

```sh
cd /sti/til/din/checkout/bootdisk-web
python -m http.server 8791
```

Åpne `http://localhost:8791/overview.html`.

Siden er merket «Syntetiske prøvedata – ikke katalogfunn» så lenge prototypen er i bruk.
Den skriver ingenting: oversiktsadapteren har ingen skriveoperasjon i det hele tatt.
Klikk et programnavn for å åpne raden i den vanlige kurateringsflyten, og «← Tilbake til
oversikten» for å komme tilbake til samme søk, filtre, side og rad.

Den eksisterende kurateringen er uendret: `http://localhost:8791/curate.html` er fortsatt
Catalogs to ekte prøveoppføringer, og `?mode=local` er fortsatt den ekte tjenesten.

## Hva som virker, og hva som bare er prøvedata

**Virker mot adapteren:** søk på navn og kildepost, statusfilter, feltfilter, sortering,
paginering, åpning av en bestemt rad på `manifest` + `entry`, retur til samme visning med
tastaturfokus på raden, og oppfriskning av en rad fra adapterens faktiske svar etter en
beslutning. Beslutningene selv — godkjenn, utsett, angre, kladd, konflikt, gjenforsøk —
kjører i den uendrede detaljflyten mot den uendrede fixture-adapteren.

**Bare prøvedata:** selve radene. Oversiktslaget bygger sammendrag fra et deterministisk
syntetisk datasett, ikke fra Catalog. Det er *ikke* integrert med den lokale tjenesten, og
det skal ikke leses som at det er det.

**Backendavhengigheter før dette kan bli ekte:**

- Catalog må svare på en lesekontrakt for oversikt (forslaget står nedenfor). I dag
  finnes ingen slik operasjon, verken i `curator-contract-v1.md` eller i den lokale
  tjenesten.
- `getQueue` er per kildepost. En oversikt over hele arkivet har ingen definert kall i v1.
- Sammendragsfeltene (versjon, innholdstype, utgave, kladd kontra akseptert) må komme fra
  tjenestens eget register. Frontend skal ikke hente ett `getEntry` per rad.
- Søk, filtrering, stabil sortering og paginering må skje på tjenestesiden når datasettet
  vokser forbi det en nettleser kan holde i minnet.
- Ekte kataloglagring, identitetsvalidering, kildeinspeksjon, historikk på disk og
  opprinnelses-/sesjonskontroll står fortsatt på Codex, slik
  [frontend v1](curator-frontend-v1.md) lister.

## Filer

| Fil | Ansvar |
| --- | --- |
| `overview.html` | Siden. Ikke i den offentlige release-allowlisten. |
| `overview.css` | Stil, bygget på eksisterende visuell identitet. |
| `overview-core.js` | Oversiktslogikk uten DOM: søk, filtre, sider, kappløpsvern, retur. |
| `overview-adapter.js` | Prototypens leselag. Foreslått lesekontrakt, ingen skriveoperasjon. |
| `overview-sample.js` | Deterministisk syntetisk datasett. Genereres i minnet, ikke lagret. |
| `overview.js` | Binding mot siden. Tekst rendres alltid som tekst. |
| `curator-labels.js` | Norske etiketter delt av begge kuratorskjermene. |
| `curator-navigation.js` | Adressen til en oversiktsvisning, delt av begge skjermene. |

`curate.js` er utvidet med tre ting og ellers uendret: den kan åpnes på en bestemt rad
(`?dataset=sample&manifest=…&entry=…`), den viser en tilbakelenke når den er åpnet fra
oversikten, og etikettene er flyttet til `curator-labels.js`.

## Hvorfor paginering

Oversikten viser 50 rader om gangen i ordinær sidevisning.

Alternativet var virtuell rulling. Sidevisning ble valgt fordi antallet DOM-noder blir
konstant og forutsigbart, tabellen forblir en fullstendig tabell for skjermleser og
tastatur i stedet for et vindu som endrer seg under lesingen, og fordi posisjonen er
et tall som kan stå i adressen og dermed hentes tilbake etter en beslutning. Virtuell
rulling gir ingen av delene uten vesentlig mer maskineri.

## Kladd, godkjent og avklart

Tre ting som lett blandes, og som vises adskilt i hver rad:

- **Kladd kontra sist godkjent.** Raden viser den godkjente verdien. Er kladden endret,
  står den under som «Kladd: …» i egen farge *og* egen tekst. Har oppføringen ingen
  godkjent verdi ennå, står det «Ingen godkjent verdi ennå»; kladden presenteres aldri
  som katalogens godkjente verdi.
- **Gjennomgått kontra fullstendig avklart.** «Vurderingsstatus» er køtilstanden
  (venter, utsatt, gjennomgått). «Avklaring» er noe annet: en gjennomgått oppføring kan
  fortsatt ha uavklarte felt eller et felt som trenger ny kontroll, og da står den ikke
  som fullstendig avklart.
- **Ukjent verdi.** Lagret `unknown` vises som «Ikke oppgitt» for versjon og «Ukjent»
  for utgave, med samme ordlyd som detaljskjermen bruker.

Status er lesbar uten farge: hver tilstand har sitt eget merke (● ‖ ✓) og sin egen tekst.

## Prøvedataene

`overview-sample.js` genererer **5 230 oppføringer fordelt på 125 kildeposter** fra en
fast seed. Ingenting lagres på disk; to kjøringer gir identiske rader.

Arkivet vokser én CD om gangen, så datasettet er modellert som mange små kildeposter i
stedet for én stor. Det gir det som faktisk må testes: samme K-ID i alle 125 kildeposter
(`K1` finnes 125 ganger), gjentatte programnavn på tvers, korte og lange navn, ulike
køtilstander, oppføringer uten godkjent verdi, endrede kladder og felt som trenger ny
kontroll.

Programmene er oppdiktede. Kildepostene heter «Syntetisk CD 001» og oppover, hver rad
viser den etiketten, og siden har et fast banner. Ingenting av dette er katalogfunn, og
det må ikke blandes med ekte kuratering.

## Forslag til lesekontrakt

Dette er et forslag til Birk/Codex, ikke en ny godkjent produksjons-API. Catalogs
kontrakt er ikke endret. Prototypen svarer på sitt eget skjema
(`bootdisk-curator-overview-proposal-1`) nettopp for at ingen skal forveksle det med v1.

```
listEntries({ manifests, query, status, field, sort, page, page_size })
  → { schema, query, status, field, sort,
      total, matched, page, page_size, page_count, items }
```

- `manifests`: liste over kildeposter, eller utelatt for hele arkivet. **Dette er den
  viktigste utvidelsen:** v1 har ingen kall på tvers av kildeposter.
- `query`: fritekst mot programnavn og kildepost.
- `status`: `all`, `pending`, `deferred`, `reviewed`.
- `field`: `all`, `any_open`, `resolved`, `needs_review`, eller ett påstandsnavn.
- `sort`: `name` eller `source`. Sorteringen må være **total**: navn, deretter kildepost,
  deretter oppføringsnummer. Uten en total orden kan en side miste eller gjenta en rad når
  navn er like.
- `total` er hele datasettet, `matched` er treffene. Begge trengs for å si «39 treff av
  5 230 oppføringer».

Hvert element:

```
{ key: { manifest, entry },
  manifest_label,
  title,
  queue_state,
  identification_status,
  open_fields: [],
  review_required_fields: [],
  has_accepted: bool,
  fully_resolved: bool,
  values: { version:           { accepted, draft, differs },
            content_kind:      { accepted, draft, differs },
            distribution_kind: { accepted, draft, differs } } }
```

`accepted` og `draft` hver for seg er det minste som trengs for å slippe å presentere en
kladd som godkjent verdi. `fully_resolved` er ikke det samme som
`queue_state === "reviewed"` og må regnes ut der åpne felt og kontrollkrav faktisk er
kjent, altså på tjenestesiden.

## Nye kontraktobservasjoner

Ingenting av dette er løst ved å endre Catalog-dokumentene. Punktene er forslag til en
samordnet avklaring, og kommer i tillegg til de fem i
[frontend v1](curator-frontend-v1.md).

6. **Ingen lesing på tvers av kildeposter.** `getQueue` tar `{manifest, filter}`. En
   oversikt over hele arkivet finnes ikke i v1. *Forslag:* `manifests` som over, eller et
   eget arkivnivå.

7. **Køen mangler sammendragsfeltene.** `getQueue` gir nøkkel, tittel, køstatus,
   identifikasjonsstatus og åpne felt, men ikke versjon, innholdstype eller utgave.
   Arbeidsordren forbyr å dekke over det med ett `getEntry` per rad, og det er riktig:
   5 230 kall ved oppstart er ikke en løsning. *Forslag:* legg feltene i køelementet.

8. **Ingen paginering og ingen tellinger.** Kontrakten sier uttrykkelig «There is no
   pagination in v1», og tellingene beskriver bare det lastede filteret. For flere tusen
   oppføringer trengs `total`, `matched` og en side. *Forslag:* som over.

9. **Kladd kontra akseptert er ikke synlig i køen.** Køelementet har ingen kladdeverdier.
   Uten dem kan ikke en oversikt skille en endret kladd fra katalogens godkjente verdi
   uten å hente hele oppføringen.

10. **`classification_review_required` står ikke i kontraktens kodeliste.** Koden brukes
    av den lokale tjenesten og av detaljskjermen, men listen over `issues`-koder i
    `curator-contract-v1.md` nevner den ikke. Kontrakten sier riktignok at ukjente koder
    fortsatt skal vises; *forslag:* ta den inn i listen, siden oversikten filtrerer på den.

11. **Fixture-adapteren antar én kildepost per datasett.** `createFixtureAdapter` nøkler
    oppføringene på `entry` alene, så to kildeposter med samme K-ID kan ikke ligge i samme
    pakke. Prototypen bruker derfor én adapterinstans per kildepost, noe som stemmer med at
    v1-køen er per kildepost. Verdt å bekrefte som villet før den ekte adapteren bygges.

## Tester

```sh
python -m unittest discover -s tests -v
```

62 tester kjører uten Playwright; 78 med. Nytt i denne leveransen er 15 atferdstester i
`tests/test_overview.py` og 8 nettleserkontroller i `tests/test_overview_browser.py`.
Nettleserkontrollene hoppes over uten Playwright, som på CI. Kjør dem lokalt med:

```sh
pip install playwright && playwright install chromium
python -m unittest tests.test_overview_browser -v
```

Punktene fra arbeidsordren:

| Krav | Dekket av |
| --- | --- |
| 1. Kombinert søk og filter, null treff, tilbakestilling | `test_search_and_filters_combine_and_reset` |
| 2. Deterministisk paginering, like navn, delt K-ID | `test_pagination_is_stable_across_repeated_names_and_shared_entry_ids` |
| 3. Oversikt → detalj → tilbake med posisjon og fokus | `test_round_trip…`, `test_opening_a_row_and_coming_back…` |
| 4. Godkjenn, utsett, angre; gjennomgått ≠ avklart | `test_decisions_update_the_row_from_what_the_adapter_answers` |
| 5. Feilet lagring og konflikt beholder utkastet | `test_failed_write_and_conflict_keep_the_draft_and_block_navigation` |
| 6. Tregt gammelt søkeresultat | `test_a_slow_old_search_result_cannot_replace_a_newer_one` |
| 7. Ingen skriving, ingen detaljkall per rad, begrenset DOM | `test_reading_the_overview_never_writes…`, `test_thousands_of_entries_render_one_bounded_page_of_rows` |
| 8. Utenfor offentlig release | `test_public_release_excludes_the_overview_and_its_sample_data` |

Om punkt 6: prototypens søk er synkront i minnet. Testen kjører derfor den asynkrone
veien bevisst — to søk holdes åpne, det nyeste svares først, og det gamle slippes fram
etterpå. Kontrollen ligger i selve kontrolleren: hver lasting tar et nummer, og bare det
nyeste får nå tilstanden. Den virker like godt når svaret kommer fra en tjeneste.

Tidskrav i testene er bevisst rause, fordi CI-maskinvaren er ukjent. De målte tallene
står nedenfor i stedet.

## Manuelle forløp og målinger

Kjørt i Chromium 141.0.7390.37 (headless), Intel Xeon 2,10 GHz, 4 kjerner, 16 GB,
via `python -m http.server` på 127.0.0.1 uten kunstig nettverksforsinkelse.

| Måling | Resultat |
| --- | --- |
| Datamengde | 5 230 oppføringer, 125 kildeposter |
| Oppstart, fra navigering til første rader vist | 608 ms (DOM klar etter 151 ms) |
| Søk, fra tastetrykk til oppdatert liste | 163–170 ms, median 169 ms (8 målinger) |
| Søk uten den innebygde forsinkelsen på 150 ms | 13–20 ms |
| Gjengitte rader ved 5 230 oppføringer | 50 |
| Detaljkall ved oppstart | 0 |
| Vannrett overflyt på 390 px | 0 px |

Målet om at søket skal oppleves umiddelbart er nådd: under 200 ms fra tastetrykk til
oppdatert liste, hvorav mesteparten er den bevisste ventetiden som hindrer et søk per
bokstav.

Manuelt kjørt i tillegg til de automatiske kontrollene: tastaturnavigasjon gjennom søk,
filtre, tabellrader og sidevisning; åpning av en rad og retur med fokus på samme rad;
godkjenning fra oversikten med retur til en rad som deretter faller utenfor filteret; og
smal visning på 390 px.

**Ikke kjørt:** ekte kataloglagring, den lokale tjenesten, ekte kildeinspeksjon, og
oversikt over ekte kuratering. Prototypen er ikke integrert.

## Skjermbilder

| | |
| --- | --- |
| Oversikt | [`curator/overview-01-oversikt.png`](curator/overview-01-oversikt.png) |
| Feltfilter og søk | [`curator/overview-02-feltfilter.png`](curator/overview-02-feltfilter.png) |
| Smal visning | [`curator/overview-03-smal.png`](curator/overview-03-smal.png) |
| Rad åpnet i detaljflyten | [`curator/overview-04-detalj.png`](curator/overview-04-detalj.png) |

## Kjente avvik

- **Ikke integrert.** Radene kommer fra syntetiske prøvedata gjennom prototypens eget
  leselag. Oversikten er ikke koblet til den lokale tjenesten, og den ekte adapteren
  prøver ingen oppdiktede endepunkter.
- **Oversikten leser detaljskjermens nettleserlagring.** For at en beslutning tatt i
  detaljflyten skal være synlig når kuratoren kommer tilbake, leser oversikten den
  lagrede gjennomgangstilstanden for de syntetiske kildepostene. Koblingen er
  prototype-bare og forsvinner når tjenesten svarer på lesekontrakten. Raden kuratoren
  kom fra friskes uansett opp med et ekte `getEntry` gjennom v1-adapteren.
- **`curate.html` laster prototypens datasettgenerator.** Skjermen trenger
  `overview-sample.js` for å kunne åpnes på en syntetisk rad, så filen lastes på begge
  sider. Den kjører ingenting uten `?dataset=sample`, men den er en avhengighet å fjerne
  sammen med prototypen.
- **Søket treffer også oppføringsnummeret.** Alle numre begynner på `K`, så et søk på
  bare «k» treffer alt. Det er villet — «K23» skal finne raden — men verdt å vite.
- **«Neste» i detaljflyten følger kildepostens kø, ikke oversiktens filter.** Oversikten
  overleverer én rad; deretter er det den eksisterende flyten som gjelder. Å la
  «godkjenn og neste» følge et oversiktsfilter ville endret detaljflyten, og det ligger
  utenfor denne ordren.
- **Navnesorteringen bruker `Intl.Collator("nb-NO")`.** Rekkefølgen på navn kan variere
  litt med nettleserens språkdata. Pagineringen gjør det ikke: sorteringen brytes alltid
  opp av kildepost og oppføringsnummer, så ingen rad kan forsvinne eller dukke opp to
  ganger uansett hvordan navn sammenliknes.
- **Utsatt.** Massegodkjenning, automatisk klassifisering, lagrede filtre, kø på tvers av
  kildeposter i detaljflyten og import av ny CD er ikke bygget, i tråd med ordren.

Dette er en prototype. Den er ikke merget, ikke deployet og ikke en release.
