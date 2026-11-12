# Originalmenyer fra K-CD

Fra 2012 hadde K-CD-ene en HTML-meny (`default.html` og sidene i `html/`). Bootdisk kan vise
en statisk, filtrert kopi av den menyen ved siden av arkivet. Hver kildepost lenker til sin
egen omtale i menyen («Åpne omtalen i CD-menyen»), og hver omtale lenker tilbake til
kildeposten. Artikler og videokurs som står sammen på én side, får hvert sitt anker.
CD-oversikten i arkivet har knappen «Bla i CD-menyen».

Visningen er et tillegg. Kildeposter, kurering, indeks og oppdateringshistorikk endres ikke,
og en CD uten godkjent meny ser ut som før.

## Hva som bygges

```
SITE/cd-meny/menus.json                 det eneste arkivsidene leser
SITE/cd-meny/<medium>/default.html      menyforsiden
SITE/cd-meny/<medium>/html/*.html       menysidene
SITE/cd-meny/<medium>/html/main.css     menyens stilark, renset
SITE/cd-meny/<medium>/<bilder>          bare bilder sidene viser, verifisert
SITE/cd-meny/<medium>/archive.css       arkivets eget felt og merknader
SITE/cd-meny/<medium>/index.html        «Om visningen»: hva som er slått av, poster uten lenke
SITE/cd-meny/<medium>/menu-index.json   rapport og filliste for mediet
```

`menus.json` (skjema `bootdisk-cd-menu-index-1`):

```json
{"schema": "bootdisk-cd-menu-index-1",
 "media": {"kcd-18-2013": {"manifest": "sha256:…",
                           "start": "cd-meny/kcd-18-2013/default.html",
                           "routes": {"kcd-18-2013--game01": "cd-meny/kcd-18-2013/html/game01.html",
                                      "kcd-18-2013--videos02": "cd-meny/kcd-18-2013/html/videos.html#post-videos02"}}}}
```

`build-release.py` legger alltid med en tom `menus.json`, så sidene får et svar og ingen 404.
`scripts/cd-menu-matrix.py` erstatter den med mediene som er godkjent.

Nettleseren (`collection-core.js`) tilbyr en lenke bare når

- mediet har en gyldig `manifest`-referanse i `menus.json`,
- kildepostens `source_manifest` er nøyaktig den samme referansen,
- nøkkelen starter med `<medium>--`, og
- målet ligger under `cd-meny/<medium>/` og bare inneholder trygge tegn.

Én CD kan derfor aldri åpne en annen CDs omtale, og en meny bygget fra et annet manifest
gir ingen lenker. En manglende eller ugyldig `menus.json` gir ingen lenker og ingen feil.

## Binding og kontroll

- Kildepost → side kommer fra manifestets `entries[].evidence.html_menu.page` og indeksens
  `source_entry` og `source_manifest`. Titler og mappenumre brukes bare som kontroll.
- En side med én post må vise postens tittel. På delte sider (`div.guide` og `div.video`)
  må nøyaktig én blokk ha tittelen i overskriften, ellers får posten ingen lenke.
- Hver byte som kopieres, må stemme med størrelse og SHA-256 i manifestets filinventar.
  Et avvik sperrer mediet.
- Stier dekodes før de kontrolleres. Absolutte stier, skråstreker bakover, NUL og
  kontrolltegn avvises, og det samme gjør `..` ut av CD-en og navn som bare skiller seg i
  store og små bokstaver. Symbolske lenker i kildeutvalget sperrer mediet.
- Sidene leses som Windows-1252, slik nettlesere leser ISO-8859-1. Udefinerte byte gjør
  siden «ødelagt». Den vises ikke, lenker til den får en merknad, og postene står på
  «Om visningen» med forklaring. Kildeposten beholdes.
- Ukjent menyformat i manifestet, eller en forside uten `#wrapper`, `#menu` og
  `#contentwrapper`, sperrer mediet.
- Et medium som sperres, skriver ingenting. Menyen som allerede ligger i `SITE`, beholdes.
  En ny meny bygges i en midlertidig mappe og byttes inn først når den er ferdig.

## Filtrering

Et element kommer bare med når det står på listen over tillatte elementer
(`KEPT_TAGS` i `scripts/cd_menu.py`). Skript, stiler i siden, rammer, objekter, skjema,
knapper, felt, `on*`-attributter og `style`-attributter fjernes. Trygge layoutverdier fra
`style` blir genererte klasser. Hver side har i tillegg en streng CSP: ingen skript,
ingen eksterne ressurser og ingen skjema. Stilarket mister `@import`, `expression()`,
`behavior` og eksterne `url()`.

Installasjon, PDF, video, søk, medlemskort, utskrift og eksterne lenker blir tekst med en
merknad i parentes, for eksempel «(videoavspilling er ikke tilgjengelig i arkivvisningen)».
Antallet står per medium i rapporten og på «Om visningen». Tekst og redaksjonelle feil
beholdes slik de står på CD-en. Forsiden på 18/2013 nevner for eksempel «CD 17, 2013».

Arkivets felt øverst («Bootdisk · K-CD 18/2013 · original CD-meny» og lenkene til
kildeposten, menyforsiden, CD-oversikten og «Om visningen») har egen stil og ligger utenfor
originalen. På smal skjerm ruller originalen sidelengs i sin egen boks, og feltet forteller
det.

## Status per medium

| Status | Betyr |
|---|---|
| `ready` (klar til gjennomgang) | Hver kildepost har en verifisert rute og hver fil stemte med manifestet. Det er ikke en godkjenning. |
| `review` (bygget med avvik) | Bygget, men noe er listet: poster uten rute, ødelagte sider, bilder som mangler på menysidene, eller avviste bildeadresser. |
| `blocked` (sperret) | Ingenting skrevet. Årsaken står i rapporten. |
| `dry_run` (tørrkjørt) | Bare manifestet er lest. Inngangssidene som ligger i manifestet, er bundet og kontrollert. Forside, stilark og bilder er ikke kontrollert. |

Bilder som mangler på CD-en og bare brukes av stilarket, er originalfeil og gjør ikke et
medium til `review`. En plate blir aldri `ready` bare fordi `default.html` finnes.

## Kommandoer

Alle stier under er eksempler. Bruk ferdige ISO-filer, aldri CD-spilleren, ISO-køen eller
filer som fortsatt kopieres.

1. Finn manifestet hver publisert CD er bygget fra. Treff gjøres på SHA-256, ikke på navn,
   fordi to kjøringer av samme plate kan ha like store manifester med ulike byte:

   ```sh
   python3 scripts/find-cd-menu-manifests.py --index RELEASE/data/index.json \
       --root ~/Bootdisk/local-results --sources MENYKILDER --out matrise.json
   ```

2. Kopier menyutvalget fra hver ISO (bare HTML, stilark og bilder, kontrollert mot manifestet):

   ```sh
   python3 scripts/extract-cd-menu-source.py --matrix matrise.json \
       --intake INTAKE-KONFIG-1.json --intake INTAKE-KONFIG-2.json --dest-root MENYKILDER
   python3 scripts/find-cd-menu-manifests.py … --out matrise.json   # på nytt, nå med kilder
   ```

3. Tørrkjør, og bygg deretter en lokal forhåndsvisning med alle byggede menyer:

   ```sh
   python3 scripts/cd-menu-matrix.py --config matrise.json --index RELEASE/data/index.json \
       --report-dir rapport-tørr --dry-run
   python3 scripts/cd-menu-matrix.py --config matrise.json --index RELEASE/data/index.json \
       --site RELEASE --report-dir rapport --preview-all
   (cd RELEASE && python3 -m http.server 8791)   # http://127.0.0.1:8791/archive.html
   ```

4. For publiseringspakken gir du bare godkjente medier: `--approve kcd-18-2013,kcd-5-2012`
   i stedet for `--preview-all`. Da skrives bare de godkjente menyene under `cd-meny/`.
   De andre bygges og kontrolleres i minnet og står i rapporten med `published: false`.
   Menyer fra en tidligere forhåndsvisning i samme mappe fjernes. Ligger det noe annet i
   `cd-meny/` enn menyer og midlertidige mapper fra dette verktøyet, stopper kjøringen
   før bygging, og ingenting endres. Bruk helst en egen kopi av release-mappen for
   forhåndsvisning.

`RELEASE` er mappen fra `build-release.py`. Menyene bygges etter release-bygget, fordi
`build-release.py` erstatter hele utdatamappen. `rapport/RAPPORT.md` har én linje per
medium (kilder, ruter, ankre, delte sider, sider, bilder, manglende ressurser, deaktiverte
funksjoner og merknad) og en avviksliste under tabellen.

## Tester

`tests/test_cd_menu.py` bruker oppdiktede menyer fra `tests/synthetic_cd_menu.py`
(PRØVEDATA, ingenting fra en ekte CD). Testene dekker ruter og ankre, filtrering,
stikontroll, sperring uten overskriving, matrisen, manifestsøket, uttrekket (med en
tar-fil som avbildning), lenkefilteret i nettleseren og nettlesertester med Playwright:
rundturer, direkte bokmerke, tastatur, døde lenker, mobil, ingen eksterne forespørsler og
ingen aktive originalkontroller.

```sh
python -m unittest tests.test_cd_menu -v
```

## Utenfor denne PR-en

- **Publish:** `cd-meny/**` må lastes opp sammen med resten av mappen. Hvis Publish har en
  egen liste over tillatte stier eller en opplastingskontroll, trengs `cd-meny/` der. Det
  hører hjemme i en egen PR i Publish.
- **Ingest:** observe-manifestet bygger bare inn sidene som har kildeposter. Forsiden, stilarket og bildene har bare størrelse og SHA-256 i inventaret, så de
  kontrolleres først når kildeutvalget fra ISO-en finnes. Dette er en observasjon, ikke et ønske om endring.
