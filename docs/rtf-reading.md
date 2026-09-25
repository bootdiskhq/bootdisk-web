# Lesbar RTF-omtale på detaljsiden

Status: utkast, 25. september 2026. Bygger på Birks `feat/rtf-documents` (PR #46),
head `021fc35`. Ingen merge, publisering eller versjonsøkning. Arbeidsordre:
«Lesbar RTF-omtale i Bootdisk» (Stian, 25.09.2026).

Omfang: `renderSourceDocuments` og feilvisningen i `app.js`, stilreglene for
`#source-documents` i `styles.css`, og testene. `index.html` er uendret fra Birks head
(`#source-documents` var allerede riktig plassert). Byggeskript, releasefiler,
genererte data, kontrakt og kuratering er ikke rørt.

## Prøv selv

```sh
python3 tests/rtf_reading_fixtures.py /tmp/rtf-testside
python3 -m http.server 8814 --bind 127.0.0.1 --directory /tmp/rtf-testside
```

| Adresse | Tilfelle |
| --- | --- |
| `index.html?entry=K37` | Ekte: WinAmp, kort menyomtale og lengre RTF |
| `index.html?entry=kcd-1-2001--K1` | Ekte: Asterix, menyomtalen er RTF-teksten |
| `index.html?entry=kcd-8-2001--K5` | Ekte: Freesaver MP3, `text: null` |
| `index.html?entry=K901` | TESTDATA: lang tekst, norske tegn, HTML-lignende tekst, langt filnavn |
| `index.html?entry=K902` | TESTDATA: samme tekst med ulik whitespace |
| `index.html?entry=K903` | TESTDATA: `text: null` |
| `index.html?entry=K904`, `K905` | TESTDATA: ingen dokumenter / tom liste |
| `index.html?entry=K906` | TESTDATA: seks utrygge eller ugyldige nedlastingsadresser |
| `index.html?entry=K907`, `K908` | TESTDATA: dokument fra annen kildepost / utrygg adresse uten tekst |

Testsiden er merket TESTDATA og ligger bare under `tests/`. Den kommer ikke med i en
release: `build-release.py` kopierer bare sin egen liste over statiske filer, og en test
sjekker det.

## Før og etter

**Før (`021fc35`):** RTF-teksten lå i en åpne/lukk-boks uten egen stil, med «Kilde:
WinAmp/No.rtf» som egen linje og «Last ned originalfil (RTF, 1 kB)» inne i boksen. Når
teksten var den samme som menyomtalen, fikk leseren en boks som het «Original omtale som
RTF» og som bare inneholdt en lenke. Ved `text: null` måtte leseren åpne en boks for å
få vite at teksten ikke kunne vises. Lange filnavn ble ikke brutt: siden ble 1142 px bred
på en 320 px skjerm ([14](rtf-reading/14-for-testdata-lang-320px.png)). En feil på siden
etter at dokumentene var tegnet (for eksempel en post som mangler i indeksen) lot
RTF-boksen stå synlig ved siden av feilmeldingen.

**Etter:** Menyomtalen står som før. Under den kommer én av tre visninger, og alltid en
nedlastingslinje med kildefil, filtype og størrelse:

| Tilfelle | Visning |
| --- | --- |
| Annen tekst i RTF | Lukket `<details>`: «Les originaltekst fra CD-en (RTF)». Teksten vises med avsnitt og tegn uendret. |
| Samme tekst (bare whitespace skiller) | Ingen boks. «Samme tekst finnes i originalfilen fra CD-en.» |
| `text: null` | Ingen boks. «Originalteksten fra CD-en kan ikke vises her, men originalfilen kan lastes ned.» `warning` vises ikke. |

Nedlastingslinjen: **Last ned originalfil** `WinAmp/No.rtf · RTF · 613 byte`.
Størrelsen skrives med norsk desimalkomma (`6,9 kB`), ikke rundet opp til hele kB.
Er adressen ikke Publish sin egen butikkadresse, blir det ingen lenke, bare
«… · originalfilen er ikke tilgjengelig».

Skjermbilder i [`docs/rtf-reading/`](rtf-reading/):
01–02 K37 lukket og åpen, 03 Asterix (samme tekst), 04 Freesaver (`text: null`),
05–06 lang TESTDATA ved 320 og 375 px, 07 tastaturfokus, 08 utrygge adresser,
11–14 de samme tilfellene på Birks head.

## Regler i visningen

- Dokumentet vises bare når `key` er identisk med postens `source_context.key`.
- Lenke bare når `original.public_path` er nøyaktig
  `store/documents/sha256/<to første tegn>/<sha256>.rtf`, `original.sha256` er lik
  dokumentets `sha256` og `media_type` er `application/rtf`. Dette er strengere enn
  Birks første sjekk (som ikke så på `media_type` og dokumentets `sha256`), men
  samme regel som `frontend_contract.py` allerede håndhever ved bygging.
- Har dokumentet verken lesbar tekst eller trygg adresse, vises det ikke.
- Teksten settes med `textContent` og vises med `white-space: pre-wrap`. Ingen RTF eller
  HTML tolkes i nettleseren.
- Feilvisningen skjuler `#source-documents`.

## Kontrollmatrise

Kjørt 25.09.2026 i Chromium 1194 (Playwright 1.63) mot testsiden over HTTP. «Ekte» betyr
de tre eksemplene fra arbeidsordren; RTF-filene er de originale bytene.

| # | Krav | Test | Resultat |
| --- | --- | --- | --- |
| 1 | Kort menyomtale + lengre RTF, åpne og lukke | `test_short_menu_description_and_longer_real_rtf_can_be_opened_and_closed` (ekte K37) | Bestått |
| 2 | Samme tekst med ulik whitespace vises ikke to ganger, nedlasting finnes | `test_text_that_only_differs_in_whitespace_is_not_shown_twice` (K902 + ekte Asterix) | Bestått |
| 3 | `text: null`: forståelig merknad, fungerende nedlasting | `test_text_null_explains_briefly_and_still_offers_the_original` (K903 + ekte Freesaver) | Bestått |
| 4 | Ingen dokumenter: ingen tom boks | `test_entries_without_documents_get_no_section` (K904, K905, K907, K908) | Bestått |
| 5 | Lang tekst, avsnitt, norske tegn, lange filnavn, HTML-lignende tekst | `test_long_multiparagraph_html_like_text_is_rendered_literally_and_wraps` (1280, 375, 320 px) | Bestått |
| 6 | Tastatur, synlig fokus, tab-rekkefølge | `test_keyboard_opens_and_closes_with_visible_focus_in_reading_order` | Bestått |
| 7 | Ingen sideveis rulling ved 320/375 px, ingen overlapp | `test_narrow_screens_do_not_scroll_sideways_or_overlap_navigation` | Bestått for RTF-visningen; se funn 1 |
| 8 | Ugyldig ekstern/traverserende adresse gir ingen aktiv lenke | `test_unsafe_download_addresses_never_become_links` (K906: ekstern, `..`, `javascript:`, `//`, feil hash, feil type) | Bestått |
| 9 | Originalfilen lastes faktisk ned | Nedlasting i Chromium, SHA-256 og størrelse sammenlignet med originalen (K37, Asterix, Freesaver, K902, K903) | Bestått |
| 10 | Arkiv-, samlings- og detaljnavigasjon | `test_detail_navigation_breadcrumbs_and_arrow_keys_still_work`, `test_existing_error_view_hides_source_documents`, og hele `test_publication_browser` | Bestått |

Datatester som også kjører i CI: de ekte eksemplene er byte-identiske med leveransen
(SHA-256 låst), RTF-filene har riktig hash og størrelse, gyldige testdata består Birks
`validate_frontend_data`, og K906–K908 avvises av den (visningens egen sjekk er et
ekstra lag), ingen testfil er i releaselisten, og `renderSourceDocuments` bruker ingen
HTML-sink.

### Testresultater

Hele `python -m unittest discover -s tests` på `feat/rtf-reading`:

| Miljø | Kjørt | Bestått | Hoppet over | Feilet |
| --- | --- | --- | --- | --- |
| Lokalt med Chromium | 222 | 221 | 1 | 0 |
| Som CI (uten Playwright) | 222 | 145 | 77 | 0 |

Den ene som hoppes over lokalt, sammenligner Catalogs allowlist og trenger en
Catalog-checkout. Nye tester i `tests/test_rtf_reading.py`: 15 (5 datatester som også
kjører i CI, 10 nettlesertester). Birks head `021fc35` hadde 207 tester.

### Fanger testene reelle feil?

18 bevisste feil ble lagt inn én om gangen i `app.js` og `styles.css`, og
`tests.test_rtf_reading` ble kjørt for hver. Alle 18 ble fanget. To ble ikke fanget i
første runde (manglende `media_type`-sjekk og en tom seksjon som ikke var `hidden`);
testene ble utvidet før resultatet over.

| Feil | Fanget |
| --- | --- |
| `innerHTML` i stedet for `textContent` | ja |
| Ingen whitespace-normalisering | ja |
| Ingen `media_type`-sjekk | ja |
| Ingen adressesjekk | ja |
| Bare mønstersjekk, ikke hash | ja |
| Feilvisning skjuler ikke dokumentene | ja |
| Ingen nøkkelsjekk | ja |
| Uten `download` | ja |
| Dokument uten tekst og trygg adresse vises | ja |
| `text: null` skjuler hele dokumentet | ja |
| Annen tekst i åpne-knappen | ja |
| Tom seksjon vises | ja |
| Størrelse rundet opp til hele kB | ja |
| Uten kildefil, type og størrelse | ja |
| Uten `pre-wrap` og brytning av teksten | ja |
| Langt filnavn brytes ikke | ja |
| Fokusmarkering fjernet | ja |
| `hidden` overstyrt av CSS | ja |

## Funn og manglende opplysninger

1. **Lange titler flyter ut på smal skjerm (fantes før, ikke rettet her).** `h1` på
   detaljsiden brytes ikke inne i ord. Ved 320 px blir siden 455 px bred med
   «Digitalkameraskolen» og 392 px med «MechCommander 2», begge titler fra samlingen.
   Det ligger utenfor dette oppdraget. Forslag: `overflow-wrap: anywhere` (eller
   `hyphens: auto`) på `#software-name`. Testdataene bruker derfor korte titler.
2. **Språk mangler i dataene.** `source_documents` har ikke noe språkfelt. Teksten arver
   sidens `lang="no"`, så en skjermleser leser en engelsk RTF med norsk uttale. Visningen
   gjetter ikke; et felt som `language` fra Ingest ville løst det.
3. **MIME-type hos Domeneshop er ikke kontrollert.** Lokalt serverer Python `.rtf` som
   `application/rtf`, og testen krever det. Hva vertens server sender, er ikke kjent;
   `download`-attributtet gjør at nettleseren lagrer filen uansett.
4. **Flere dokumenter per post.** Kontrakten tillater en liste, men
   `attach-source-documents.py` setter alltid ett dokument. Visningen tåler flere
   (K906 har seks), men alle får samme knappetekst; kildefilen står under hver av dem.
   Blir flere dokumenter vanlig, bør knappen nevne filnavnet.
5. **Stians pilot er ikke åpnet.** `http://127.0.0.1:8810/index.html?entry=K37` er ikke
   nåbar herfra. Den ekte K37 er kontrollert med eksempelfilen fra arbeidsordren.
