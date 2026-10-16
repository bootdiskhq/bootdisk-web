# Lesbar RTF-tekst på detaljsiden

Status: levert som PR mot `main`, 16. oktober 2026. Ikke merget, ikke publisert, ingen
versjonsøkning (`VERSION` er fortsatt `1.2.0-rc19`). Arbeidsordre: «Konsekvent RTF-lesing
direkte i Bootdisk» (Birk, på Stians oppdrag, 16.10.2026). Base: `main` `00eb217`
(Web PR #68, rc19, 730 poster på elleve CD-er).

Erstatter utkastet fra 25.09.2026 (PR #46 / `feat/rtf-reading`). Den viktigste endringen
er at **tekst som er lik menyomtalen også kan utvides**; tidligere ble boksen skjult da.

Omfang: `renderSourceDocuments` i `app.js` (samme løsning, ingen ny RTF-viser), én
CSS-regel i `styles.css` (brytning av lange filnavn i åpne-knappen), cacheversjonen for
`app.js` i `index.html` (`?v=rtf-expand1`), testene og testdataene. Menyomtale,
identifikasjon, kontrakt, genererte kildedata, historikk, kuratering, teller og
serveroppsett er ikke rørt.

## Oppførsel

Menyomtalen står som før. For hvert kildebundet RTF-dokument kommer én blokk, og under den
alltid en egen nedlastingslinje: **Last ned originalfil** `WinAmp/No.rtf · RTF · 613 byte`.

| Tilfelle | Visning |
| --- | --- |
| Lesbar tekst, ulik menyomtalen | Lukket `<details>`: «Les tekstfilen fra CD-en (RTF)». |
| Lesbar tekst, lik menyomtalen (bare whitespace skiller) | Merknad «Teksten i filen er den samme som menyomtalen over.» og samme lukkede boks. |
| `text` er `null`, `""` eller bare whitespace | Ingen boks. «Teksten i filen kan foreløpig ikke vises her, men originalfilen kan lastes ned.» |
| Flere dokumenter | Én blokk per fil. Knappen sier hvilken fil: «Les tekstfilen fra CD-en (RTF): Spill/No.rtf». Boksene åpnes hver for seg. |
| Ingen dokumenter / bare dokumenter som ikke hører til posten | Ingen seksjon (`#source-documents` er `hidden`). |

- Boksen er native `details`/`summary`: lukket som standard, åpnes og lukkes med klikk,
  Enter og mellomrom, uten skript, navigasjon, nettverksforespørsel eller nedlasting.
  Skjermlesere får åpnet/lukket-tilstanden fra elementet selv; trekanten roterer.
- Teksten settes med `textContent` og vises med `white-space: pre-wrap`: avsnitt,
  linjeskift og norske tegn står som Ingest dekodet dem. Ingen omskriving, ingen
  formatering, ingen RTF- eller HTML-tolkning i nettleseren. Det er tekstvisning, ikke
  Word-layout.
- Nedlastingslenken ligger utenfor `details` og er synlig også når boksen er lukket.
  Filnavn, filtype og størrelse beholdes.
- Merknaden ved manglende tekst sier at teksten ikke kan vises *her*; den påstår ikke at
  originalfilen mangler tekst.

## Regler som er beholdt

- Dokumentet vises bare når `key` er identisk med postens `source_context.key`.
- Lenke bare når `original.public_path` er nøyaktig
  `store/documents/sha256/<to første tegn>/<sha256>.rtf`, `original.sha256` er lik
  dokumentets `sha256` og `media_type` er `application/rtf`. Ellers står det
  «… · originalfilen er ikke tilgjengelig», uten lenke.
- Har dokumentet verken lesbar tekst eller trygg adresse, vises det ikke.
- Feilvisningen skjuler `#source-documents`. Hver detaljside bygger seksjonen på nytt;
  navigasjon til neste post viser aldri forrige posts tekst.

## Prøv selv

```sh
python3 tests/rtf_reading_fixtures.py /tmp/rtf-testside
python3 -m http.server 8814 --bind 127.0.0.1 --directory /tmp/rtf-testside
```

| Adresse | Tilfelle |
| --- | --- |
| `index.html?entry=K37` | Ekte utviklingseksempel: WinAmp, kort menyomtale og lengre RTF |
| `index.html?entry=kcd-1-2001--K1` | Ekte: Asterix, RTF-teksten er identisk med menyomtalen |
| `index.html?entry=kcd-8-2001--K5` | Ekte: Freesaver MP3, `text: null` |
| `K901` | TESTDATA: lang tekst, norske tegn, HTML-lignende tekst, langt filnavn |
| `K902` | TESTDATA: samme tekst med ulik whitespace |
| `K903`, `K909`, `K910` | TESTDATA: `text` er `null`, `""`, bare whitespace |
| `K904`, `K905` | TESTDATA: ingen dokumenter / tom liste |
| `K906` | TESTDATA: seks utrygge eller ugyldige nedlastingsadresser |
| `K907`, `K908` | TESTDATA: dokument fra annen kildepost / utrygg adresse uten tekst |
| `K911` | TESTDATA: to lesbare tekstfiler på samme post |

Testsiden er merket TESTDATA, ligger bare under `tests/` og kommer ikke med i en release
(testen `test_test_data_never_reaches_the_release_allowlist`).

## Er eksemplene fortsatt representative?

`bootdisk.no` er ikke nåbar fra skymiljøet der dette ble laget (proxyen avviser
tilkoblingen). Offentlige data ble derfor lest indirekte via et nettleserverktøy som
oppsummerer sider, 16.10.2026:

| Post | Offentlig rc19 | Fixture |
| --- | --- | --- |
| `kcd-1-2001--K1` (Asterix) | `Asterix/No.rtf`, sha256 `04bcfed6…`, 7037 byte, tekst lik menyomtalen | Samme nøkkel, hash og størrelse; testen bekrefter lik tekst |
| `kcd-8-2001--K5` (Freesaver) | `Freesaver/No.rtf`, sha256 `3efe0a16…`, 4405 byte, `text: null`, `unsupported RTF font charset` | Samme |
| `kcd-12-2001--K1` (3D Dragon Castle) | `Dragon/No.rtf`, sha256 `5f3d8362…`, 2072 byte, lesbar norsk avsnittstekst ulik menyomtalen | Ikke i testdataene; teksten kunne ikke hentes ordrett herfra |

Sammenligningen er gjort mot verktøyets gjengivelse, ikke mot byte i responsen. **Birk må
gjøre reell akseptanse** på `https://bootdisk.no/index.html?entry=kcd-12-2001--K1` og
K37 etter publisering, eller lokalt mot en rc19-forhåndsvisning med denne grenen.

### Reell `text: null`: oppfølging for Ingest/Catalog

`kcd-8-2001--K5`, `Freesaver/No.rtf` (sha256
`3efe0a16c9313b45cb66177787002df81f39c8e170a39c29c204d7601f060a45`, 4405 byte):
Ingest-metoden `rtf-ansi-text-terminal-nul-1` gir `text: null` med
`unsupported RTF font charset`. Frontend viser forklaring og originalnedlasting; den
løser ikke dekodingen og finner ikke på tekst. Ellers er ikke hele rc19 gjennomgått for
`text: null` herfra (dataene er ikke tilgjengelige i skymiljøet). En full liste bør tas
fra Publish-pakken.

## Før og etter

Skjermbilder i [`docs/rtf-reading/`](rtf-reading/), tatt i Chromium 1194 mot testsiden.
`for-*` er `main` `00eb217`, `etter-*` er denne grenen. Samme nummer er samme tilfelle:

| Nr. | Tilfelle | Før | Etter |
| --- | --- | --- | --- |
| 01 | K37 lukket | «Les originaltekst …» | «Les tekstfilen …», lenke synlig under |
| 02 | K37 åpen | Tekst | Tekst, uendret innhold |
| 03 | Asterix (identisk) lukket | Bare «Samme tekst finnes i originalfilen», ingen boks | Merknad + lukket boks |
| 04 | Freesaver `text: null` | Merknad + lenke | Ny merknad + lenke |
| 05 | To filer (K911), begge åpne | To like knappetekster | Filnavn i hver knapp |
| 06 | Blank tekst (K910) | Merknad | Ny merknad |
| 07 | Lang TESTDATA 320 px åpen | Ingen sideveis rulling | Ingen sideveis rulling |
| 08 | Lang TESTDATA 375 px lukket | | |
| 09 | K37 320 px åpen | | |

## Tester

Nye eller endrede i `tests/test_rtf_reading.py` (16 tester: 5 datatester som også kjører i
CI, 11 nettlesertester):

| Krav i arbeidsordren | Test |
| --- | --- |
| 1, 4: lukket boks, åpne/lukke uten navigasjon, forespørsel eller nedlasting; separat lenke med riktig mål | `test_short_menu_description_and_longer_real_rtf_can_be_opened_and_closed` |
| 3: identisk tekst er utvidbar, lukket som standard | `test_text_identical_to_the_menu_description_can_still_be_expanded` (K902 + ekte Asterix) |
| 5: `null`, `""`, blank | `test_null_empty_and_blank_text_explain_briefly_and_still_offer_the_original` (K903, K909, K910, ekte Freesaver) |
| 6: ingen dokumenter, feil kildebinding | `test_entries_without_documents_get_no_section` (K904, K905, K907, K908) |
| 6: flere dokumenter | `test_several_documents_have_their_own_file_identity_and_box` (K911) |
| 2, 8: avsnitt, norske tegn, HTML-lignende tekst bokstavelig, lange filnavn | `test_long_multiparagraph_html_like_text_is_rendered_literally_and_wraps` (1280, 375, 320 px) |
| 1, 8: Enter og mellomrom, synlig fokus, tab-rekkefølge | `test_keyboard_opens_and_closes_with_visible_focus_in_reading_order` |
| 8: 320/375 px uten sideveis rulling, også identisk tekst og to filer | `test_narrow_screens_do_not_scroll_sideways_or_overlap_navigation` |
| 7: ugyldige adresser blir aldri lenker | `test_unsafe_download_addresses_never_become_links` (K906, uendret) |
| Originalfilen lastes faktisk ned (SHA-256 og størrelse) | `assert_download` i testene over |
| Navigasjon uten gammel tekst | `test_detail_navigation_breadcrumbs_and_arrow_keys_still_work` |
| Ingen HTML-sink i `renderSourceDocuments` | `test_source_text_is_never_parsed_as_markup` (uendret) |

Ingen sikkerhetstest er svekket. `test_unsafe_download_addresses_never_become_links`,
`test_source_text_is_never_parsed_as_markup` og kontraktstesten for K906–K908 er
uendret.

**Den nye identisk-tekst-testen feiler på gammel head.** Med `app.js`, `index.html` og
`styles.css` fra `00eb217` og de nye testene:

```
FAIL: test_text_identical_to_the_menu_description_can_still_be_expanded [K902]
AssertionError: 0 != 1
FAIL: test_text_identical_to_the_menu_description_can_still_be_expanded [kcd-1-2001--K1]
AssertionError: 0 != 1
```

(0 `details`-elementer der testen krever 1.) Hele `tests.test_rtf_reading` på gammel head:
16 kjørt, 8 feil, 1 error (navigasjonstesten finner ingen boks hos Asterix).

### Fiks i testsiden

Testsiden kopierte ikke filene `index.html` laster etter RTF-arbeidet i september
(`updates*`, `visit-counter*`). Chromium lot de 404-forespørslene henge ved neste
navigasjon, så `test_detail_navigation_breadcrumbs_and_arrow_keys_still_work` feilet med
tidsavbrudd allerede på `main` i dette miljøet (Playwright 1.63, Chromium 1194). Filene er
lagt til i `SITE_FILES`. Telleren er av (`endpoint: null`) og gjør ingen forespørsel.

### Resultater

`python -m unittest discover -s tests` på grenen:

| Miljø | Kjørt | Bestått | Hoppet over | Feilet |
| --- | --- | --- | --- | --- |
| `main` `00eb217`, Python 3.13, Playwright 1.63, Chromium 1194 | 327 | 325 | 1 | 1 (navigasjonstesten over) |
| Grenen, Python 3.13, Playwright 1.63, Chromium 1194 | 328 | 327 | 1 | 0 |
| Grenen som CI (Python 3.12, uten Playwright) | 328 | 226 | 102 | 0 |

Den ene som hoppes over med Chromium, sammenligner Catalogs allowlist og trenger en
Catalog-checkout (`BOOTDISK_CATALOG_ROOT`).

## Avvik og åpne punkter

1. **Ingen reell akseptanse mot bootdisk.no herfra.** Se over; Birk må kontrollere
   `kcd-12-2001--K1` og K37 i nettleser.
2. **`styles.css` har ingen cacheversjon.** Konvensjonen versjonerer bare enkelte skript.
   `app.js` er versjonert (`rtf-expand1`). Den eneste CSS-endringen (brytning av lange
   filnavn i knappen) gjelder bare poster med flere dokumenter; en gammel hurtigbufret
   `styles.css` gir ellers samme visning.
3. **Språk mangler i dataene.** `source_documents` har ikke noe språkfelt; teksten arver
   `lang="no"`.
4. **MIME-type hos Domeneshop er ikke kontrollert.** `download`-attributtet gjør at
   nettleseren lagrer filen uansett.
5. Frontend-endringen løser ikke manglende RTF-koblinger eller uleselige varianter; det er
   Ingest/Catalog-arbeid.
