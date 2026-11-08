# Retro-katalog: Bootdisk som en oversiktlig program-/CD-katalog

Arbeidsordre fra Birk på Stians oppdrag, 8. november 2026. Stian: «Den er for moderne og må
være mer retro og oversiktlig.» Denne retningen erstatter Windows 95/DOS-forslaget i PR #74,
som fortsatt er åpen og ikke er bygget videre på.

## Problem

Den forrige presentasjonen var en mørk terminal med store plakatoverskrifter, mye luft, kort
i rutenett og et falskt programvindu med vindusknapper. Hver side hadde lite innhold på første
skjerm. Samlingssiden viste bakgrunnsteksten før CD-ene, så ingen CD var synlig uten å rulle
(`for-02-samling-desktop.png`). Arkivet var kort med avkuttede titler og uten kolonner, så
poster kunne ikke sammenlignes på samme skjerm (`for-03-arkiv-sok-desktop.png`).

## Endelig designretning

En ryddig norsk program-/CD-katalog fra ca. 1998–2002: lys papirbakgrunn, mørk tekst,
blå understrekede lenker med egen farge for besøkte lenker, og en mørk blå topplinje og
seksjonslinjer. Knapper og felt er lyse, lett opphøyde og uten avrunding. Brødtekst bruker
Arial, menyer og overskrifter Verdana. Logoen er vanlig tekst; understreken etter BOOTDISK
står stille. Ingen pixelfonter, gradienter som dekor, vindusknapper, blink, marquee eller tekst
som bilde. Ingen nye fonter, CDN-er, bilder, skript eller sporing.

Alt nytt utseende ligger i `catalog.css`, som lastes sist og bare på de offentlige sidene
(`index.html`, `collection.html`, `archive.html`, `updates.html`, `404.html`). Den overstyrer
fargevariablene fra `styles.css`, slik at de eksisterende offentlige stilarkene følger med.
Kuratorverktøyene (`curate.html`, `overview.html`, `automation.html`) laster ikke filen og
er uendret; `styles.css` er ikke rørt.

## Berørte sider

| Side | Endring |
| --- | --- |
| Alle offentlige | Felles toppfelt: BOOTDISK, søk (vanlig `GET archive.html?q=`, virker uten skript) og meny Forside · Samlinger · Alle kildeposter · Siste endringer. Gjeldende side har `aria-current`. Arkivet har ikke toppsøket, fordi siden har sitt eget. |
| Forside | Kort forklaring, «Samlinger» med Komputer for alle som kompakt boks med tall fra indeksen, siste endringer som tette rader, og om-teksten i en sidespalte. Ingen samlinger er funnet på; boksene kommer fortsatt fra `collections.json`. |
| Samling | CD-oversikten kommer rett etter innledningen. Hvert år har en egen linje med antall CD-er og kildeposter, regnet fra de samme indeksradene som CD-ene under. CD-ene er tette ruter med etikett og antall. Den godkjente teksten om bladet, merknaden og kildene står uendret under. |
| Arkiv | Tett tabell: ikon, menneskelig tittel (med versjon og CD-ens egen tittel når den skiller seg), CD, år, innhold og status. Status har både tekst og et formtegn (✔ ◐ ▣ ○), så farge alene sier ingenting. Manglende innhold står som «Ikke oppgitt». På mobil blir hver rad en blokk med feltene under tittelen. Søk, filtre, sortering, telling, nulltreff og URL-parametrene er uendret. |
| Kildepost | Tittel og CD øverst. Venstre spalte: omtalen, de lesbare RTF-filene (lukket som før, åpnes med mus og tastatur) og kildemerknader, nå merket «Merknad om kilden». Høyre spalte: originalbilde og faktaboksen (navn, innhold, utgave, versjon, kildepost, medium, status). Det falske vinduet med knapper er borte. |
| Oppdateringer | Samme v4-historikk, gruppering og forklaringer, vist som kompakte rader. |
| 404 | Nytt toppfelt, samme tekst. |

Kode: `archive.js` lager tabellen (statusregelen er samlet i `archiveStatus`, uendret
logikk), `collection.js` lager årslinjene. `app.js`, `landing.js`, `updates*.js` og
besøkstelleren er ikke endret. `scripts/build-release.py` tar med `catalog.css`, og
`scripts/verify-deployment.py` godtar `collection.js` med cacheversjon.

Cacheversjon: `catalog.css?v=retro-catalog1`, `archive.js?v=retro-catalog1` og
`collection.js?v=retro-catalog1`. Øvrige filer er uendret og beholder adressene sine.

## Testdata

Birks lokale kilde (`/Users/stian/Bootdisk/local-results/intake-next-2026-11-08/...`, 1705
poster på 29 CD-er, nå publisert som en del av rc24 med 1917 poster på 33 CD-er) ligger på Stians maskin og var ikke tilgjengelig fra skyen. Den
offentlige siden kunne heller ikke nås derfra. **Reell akseptanse er ikke kjørt.**

I stedet bygger `tests/synthetic_catalog.py` merkede PRØVEDATA i samme størrelse: 1705
oppdiktede kildeposter på 29 oppdiktede CD-er, bygget gjennom de ekte portene
(`frontend_contract`, `build-release.py`, `public_updates.py`) med to releaser og 153
oppdateringshendelser. Dataene har lange titler med æøå, et svært langt ord, HTML-lignende
titler, alle fire statuser, ukjent versjon, manglende ikon/bilde/omtale, RTF som er lik
menyomtalen, lang, uleselig eller to filer, kildeavvik og en avsluttet kildeundersøkelse.
Titlene begynner med «Prøvepost», og omtalene sier at de er oppdiktet.

## Kontrollmatrise

Grenen startet fra `f4055e2` (PR #75, 1.2.0-rc23). Mens arbeidet pågikk ble rc24 slått sammen
(`cfba070`, PR #76: sju nye CD-er, 1917 poster på 33 CD-er, bare `VERSION` og
valideringsnotat endret i repoet). Grenen er rebaset på `cfba070`, og testene er kjørt på nytt
der. Catalog-checkout `a4ba2c7` (bootdisk-catalog main). Chromium 153 via Playwright 1.63.

| # | Krav | Resultat | Bevis |
| --- | --- | --- | --- |
| 1 | Forside → samling → CD → post → tilbake | Bestått på PRØVEDATA og på syntetiske sju CD-er. Ikke kjørt på reelle data. | `test_front_collection_cd_entry_and_back_keep_the_filter`, `test_publication_browser.test_front_page_collection_cd_entry_and_back` |
| 2 | Alle CD-er og tellinger samsvarer med inngangsdata | Bestått for 29 CD-er og 1705 poster: hver CD-telling, hver årslinje, sammendraget og forsidetallene er lik tellingen i indeksen. Også kontrollert manuelt med PRØVEDATA i rc24-størrelse (33 CD-er, 1917 poster): 33 CD-er, alle tellinger like indeksen, 1917 arkivrader. Ikke kjørt på reelle data. | `test_scale_every_cd_and_count_comes_from_the_index` |
| 3 | Søk, kombinerte filtre, sortering, nulltreff, direkte URL; samme status i arkiv og detalj | Bestått. Alle 1705 rader har riktig tittel, CD, år og status; én post av hver status har samme statustekst på detaljsiden. Toppsøket gir `archive.html?q=…`. | `test_archive_rows_show_human_titles_cd_year_content_and_the_detail_status`, `test_header_search_and_menu_lead_into_the_archive`, `test_contract`, `test_collection` |
| 4 | Lange titler, æøå, manglende ikon/omslag, bilder, ukjent versjon | Bestått. Ingen tabellcelle flyter over ved 1280, 768, 375 og 320 px; manglende ikon gir «?» og ingen knekt bilde; ukjent versjon viser «Ikke oppgitt». CD-er har ikke omslagsbilder i datakontrakten, se avvik. | `test_long_titles_and_html_like_titles_stay_inside_their_cells_as_text`, `test_missing_images_leave_no_broken_pictures`, `test_unknown_version_reads_ikke_oppgitt` |
| 5 | RTF: mus og tastatur, identisk, lang, ingen tekst, flere filer, nedlasting, HTML bokstavelig | Bestått, de eksisterende RTF-testene kjører uendret mot ny layout. Tastaturtesten går gjennom flere Tab-trykk, fordi toppfeltet nå står foran posten. | `test_rtf_reading` (alle), skjermbilde `etter-05-detalj-rtf-*` |
| 6 | Historikk: nye/endrede poster, avvik, tom historikk etter v4 | Bestått, uendret logikk og eksisterende tester. | `test_public_updates`, `test_public_updates_browser` |
| 7 | 320, 375, 768, 1280 px; 200 % zoom; fokus; ikke bare farge | Bestått. Ingen horisontal rulling eller overlapp mellom toppfelt og innhold på seks sider ved 320, 375, 640 (= 1280 px ved 200 %), 768 og 1280 px. Synlig fokus på alle stopp fra toppfelt til tabellrad. Status har tekst og tegn. | `test_no_horizontal_scroll_at_common_widths_and_200_percent_zoom`, `test_keyboard_focus_is_visible_through_header_menu_and_rows`, `test_publication_browser.test_keyboard_reaches_every_card_with_visible_focus` |
| 8 | Ingen knekte filer, konsollfeil eller eksterne avhengigheter; kald lasting og oppgradering | Bestått: alle nettlesertestene i den nye modulen krever null konsollfeil, null 4xx/5xx og null eksterne forespørsler. Kald lasting gir ny stil. Oppgradering, se under. | `RetroCatalogBrowserTests`, `CatalogMarkupTests` |
| 9 | Offentlig release uten kurateringsverktøy; kontrakt- og sikkerhetstester | Bestått. Kuratorsidene laster ikke `catalog.css`. | `test_publication`, `test_contract`, `test_local_tools_do_not_load_the_public_catalog_style` |
| 10 | Ingen kurateringsdata eller kildedata endret | Bestått. Diffen rører ingen datafiler, fikstur eller kurateringskode. | `git diff --stat f4055e2` |

Hele testsuiten: `PYTHONPATH=<bootdisk-catalog> python -m unittest discover -s tests` kjørte
**343 tester: 343 bestått, 0 hoppet over, 0 feilet** (før endringen: 328 bestått, 0 hoppet
over). 15 tester er nye i `tests/test_retro_catalog_browser.py`.

To eksisterende tester er endret, og ingen er svekket:

- `test_publication_browser.test_heading_order_and_reading_order` krever nå den nye rekkefølgen
  (CD-er før bakgrunnsteksten). Den kontrollerer like mange overskrifter som før.
- `test_rtf_reading.test_keyboard_opens_and_closes_with_visible_focus_in_reading_order` får 24
  Tab-trykk i stedet for 12 for å komme forbi den nye menyen. Alle påstandene er de samme.

### Kald lasting og oppgradering fra tidligere cacheversjon

Kontrollert i Chromium med en vedvarende profil mot en lokal server: først arkivet fra den
gamle pakken, så ble serveren byttet til den nye pakken på samme adresse.

- Kald lasting av ny pakke: ny stil, tabell og `catalog.css?v=retro-catalog1`.
- Vanlig navigering rett etter byttet: nettleseren brukte sin bufrede gamle `archive.html`
  (gammel stil, gammel `archive.js?v=source-catalog2`). Siden fungerte, bare med det gamle
  utseendet.
- Etter «last på nytt»: ny HTML, `catalog.css?v=retro-catalog1` og
  `archive.js?v=retro-catalog1`, ny stil og tabell.

Cacheversjonene hindrer at ny HTML møter gammel CSS eller JS. Hvor lenge selve HTML-filen
bufres, bestemmes av serverens hoder på Domeneshop, og det gjelder alle releaser. Birk bør
kontrollere dette etter opplasting.

## Er det enklere å finne en CD og sammenligne poster?

Ja, målt på skjermbildene i 1280 × 900:

- **Finne en CD:** før var ingen CD synlig på første skjerm av samlingssiden. Nå er 24 av 29
  CD-er synlige, gruppert etter år med antall per år, og resten ligger ett skjermtrykk ned.
  På 375 px står CD-ene i to kolonner.
- **Sammenligne poster:** før viste søkeresultatet omtrent ti kort med avkuttede titler og uten
  felles kolonner. Nå viser det tolv rader med hele titler og CD, år, innhold og status i faste
  kolonner, så posters status og type kan leses nedover en kolonne.

## Skjermbilder

I `docs/retro-catalog/`, tatt med PRØVEDATA i 1280 × 900 og 375 × 760 px. `for-*` er main
(`f4055e2`) og `etter-*` er denne grenen.

| Visning | Før | Etter |
| --- | --- | --- |
| Forside | `for-01-forside-{desktop,mobil}.png` | `etter-01-forside-{desktop,mobil}.png` |
| CD-oversikt | `for-02-samling-…` | `etter-02-samling-…` |
| Tett søkeresultat (`?q=skrive`) | `for-03-arkiv-sok-…` | `etter-03-arkiv-sok-…` |
| Én CD | `for-04-arkiv-cd-…` | `etter-04-arkiv-cd-…` |
| Kildepost med åpen RTF | `for-05-detalj-rtf-…` | `etter-05-detalj-rtf-…` |
| Siste endringer | `for-06-oppdateringer-…` | `etter-06-oppdateringer-…` |

## Kjente avvik

- **Reell akseptanse er ikke kjørt.** Alle resultater over gjelder PRØVEDATA.
- **CD-omslag:** datakontrakten har ingen omslagsbilder for medier. CD-ene vises med en
  typografisk etikett, som før, og ingen programbilder brukes som omslag. Omslag krever et nytt
  felt fra Publish; kontrakten er ikke endret.
- På detaljsiden står kildepost-ID-en (for eksempel K2) fortsatt i den lille kildelinjen og i
  faktaboksen. Den er aldri tittel eller kolonne.
- Toppfeltet har ikke søk på arkivsiden, fordi arkivet har sitt eget søkefelt.
- HTML-bufring etter opplasting avhenger av serveren, se over.

## Dette må Birk kontrollere på reelle data

1. Bygg rc24-pakken (1917 poster, 33 CD-er) med denne grenens frontend og åpne `collection.html?collection=komputer-for-alle`: 33 CD-er, riktig antall per CD og år, også årene 2009 og 2012.
2. Les noen reelle lange titler og originalomtaler i arkivtabellen og på detaljsiden ved 1280 og 375 px.
3. Åpne en reell post med RTF, for eksempel K37, med mus og tastatur.
4. Kontroller ekte ikoner og skjermbilder i arkivtabellen og på detaljsiden, og de nye 2012-postene med HTML-omtale (artikler og video) i tabell og detaljvisning.
5. Etter opplasting: last siden på nytt og se at `catalog.css?v=retro-catalog1` lastes.
