# Besøksteller på bootdisk.no

**Status: ikke produksjonsklar. Aktivering er blokkert.** Frontend, adapter og en foreslått
backend er ferdige og testet lokalt, men repositoryet dokumenterer ikke at hostingen kan kjøre
dem. Den offentlige pakken inneholder telleren i avslått tilstand: `visit-counter-config.js`
har `endpoint: null`, siden gjør ingen forespørsel, og feltet i bunnteksten er skjult.

## Hva som mangler før aktivering

Repositoryets eneste hostingdokumentasjon er [`domeneshop-deploy.md`](domeneshop-deploy.md):
statisk opplasting med passiv FTP til `/www` hos Domeneshop, der filer som ikke er i den nye
releasen fjernes. Den sier ingenting om serverkjøring eller lagring. Disse opplysningene
mangler, og alle tre må bekreftes for bootdisk.no-kontoen:

1. **PHP på webhotellet:** kjører `bootdisk.no` PHP 8.1 eller nyere for filer under `/www`, med
   utvidelsen `pdo_sqlite` (SQLite 3.24 eller nyere, for `ON CONFLICT … DO UPDATE`)?
2. **Skrivbar mappe utenfor webroten:** finnes en mappe ved siden av `/www` (forslaget bruker
   `/bootdisk-besok/`) som PHP-prosessen kan skrive i, som ikke serveres over HTTP, og som
   deploy-steg 5 («fjern filer som ikke er i releasen») ikke rører? SQLite skriver en
   journalfil ved siden av databasen, så *mappen* må være skrivbar, ikke bare filen.
3. **Hvem kan lese serverlogger:** webhotellets vanlige tilgangslogg registrerer IP-adresser
   for alle forespørsler, også sidene. Telleren legger ikke til noen logg, men den nye
   adressen havner i samme logg. Det bør være akseptert før aktivering.

Punkt 1 og 2 står normalt i webhotellets kontrollpanel. Jeg har ikke tilgang til kontoen og
har ikke antatt svaret. Ingen konto er opprettet, og ingen ekstern eller betalt tjeneste er
tatt i bruk.

## Arkitekturbeslutning

**Kontekst.** Bootdisk er en statisk pakke som lastes opp. En felles total krever vedvarende
lagring utenfor pakken, og hver deploy sletter alt i `/www` som ikke er i releasen.

**Beslutning.** Telleren deles i tre:

| Del | Filer | Ansvar |
| --- | --- | --- |
| Visning | `visit-counter.js`, `visit-counter.css` | Bunntekstfeltet, tilstandene og tilgjengelighet |
| Kjerne | `visit-counter-core.js` | Besøksavgrensning, svarkontroll og formatering, uten DOM |
| Adapter | `visit-counter-adapter.js` | `read()` og `record(key)` over HTTP; eneste sted som kjenner transporten |
| Aktivering | `visit-counter-config.js` | Produksjonsadresse og endepunkt; `null` = av |
| Tjeneste (forslag) | `counter/besok.php`, `counter/schema.sql` | Atomisk telling i SQLite |
| Drift | `scripts/visit-counter-db.py` | `init`, `status`, `backup` |

Et annet lager (en annen host, en database, en tjeneste) krever bare en ny adapter med samme
to metoder; visningen og kjernen endres ikke.

**Hvorfor dette passer dagens hosting.** Hvis punkt 1 og 2 over bekreftes, trengs bare én
PHP-fil i `/www/api/` og én SQLite-fil ved siden av `/www`: ingen databaseserver, ingen
prosess som må holdes i gang, ingen nøkler, og ingen tredjepart. Deploy blir som i dag.
Alternativer som ble valgt bort: tredjeparts teller eller analyseverktøy (sporing hos en
annen part), en JSON-fil med fillås (vanskeligere å gjøre atomisk og å kontrollere), og
serverless eller egen server (ikke dokumentert, krever konto, kanskje betalt).

### Besøksdefinisjon

Et **besøk** er en rekke sidevisninger på bootdisk.no i samme nettleser uten mer enn **30
minutters pause** mellom to sidevisninger. Første sidevisning i et besøk øker totalen med én.
Navigering mellom forside, samling, arkiv og detaljsider og vanlig omlasting i samme besøk gjør
det ikke. Pausen måles fra forrige sidevisning, ikke fra besøkets start: akkurat 30 minutter
er samme besøk, 30 minutter og ett millisekund er et nytt.

Tallet er en praktisk nettleserbasert telling. Det er ikke antall personer eller unike
brukere, og siden kaller det bare «besøk». Visningen er «Besøk siden DD.MM.ÅÅÅÅ», der datoen er
startdatoen som ble skrevet i databasen da den ble opprettet. Ingen besøk før den datoen er
påstått.

Mekanikk: første sidevisning lager en tilfeldig nøkkel (128 bit, `crypto.getRandomValues`) og
lagrer `{key, started, last, confirmed}` i `localStorage` under `bootdisk.besok.v1`. Nøkkelen
sendes til tjenesten, som teller hver nøkkel én gang. Når tjenesten har svart, markeres
nøkkelen som bekreftet, og senere sidevisninger i besøket leser bare totalen.

### Kanttilfeller

| Situasjon | Hva skjer |
| --- | --- |
| Omlasting, navigering, tilbake-knapp | Samme besøk; bare lesing. |
| Flere faner åpnet samtidig | Faner deler `localStorage`. Valget av nøkkel skjer under en Web Lock (`navigator.locks`), så fanene får samme nøkkel og tjenesten teller den én gang. Uten Web Locks (eldre nettlesere) kan to faner som åpnes i samme øyeblikk i sjeldne tilfeller lage hver sin nøkkel og telle to besøk. |
| Faner åpne i mer enn 30 minutter uten ny sidevisning | Neste sidevisning starter et nytt besøk. Å bare ha en fane åpen er ikke aktivitet. |
| Slettet nettleserlagring, ny nettleser, annen enhet | Nytt besøk, telles. |
| Privat vindu | Egen lagring; telles som et eget besøk, og lagringen forsvinner når vinduet lukkes. |
| Blokkert eller full lagring | Sidevisningen telles ikke (ellers ville hver side blitt et nytt besøk); totalen leses og vises. |
| Tidsavbrudd (5 s) eller tapt svar | Feltet viser «Teller utilgjengelig». Nøkkelen er ubekreftet og sendes **på nytt med samme nøkkel** ved neste sidevisning; tjenesten har den allerede og teller ikke igjen. |
| Et ubekreftet besøk holdes i live i mer enn 12 timer | Nettleseren slutter å sende nøkkelen og leser bare. Tjenesten husker nøkler i 48 timer, så en ny innsending treffer alltid en kjent nøkkel (testet mot konstantene i begge filer). |
| Klokken i nettleseren går bakover | Samme besøk; ingen ny telling. |
| Roboter og søkemotorer uten JavaScript | Telles ikke. |
| Tjenesten nede, 503, ugyldig svar, manglende database | «Teller utilgjengelig». Aldri et nulltall, aldri et gammelt tall. Resten av siden virker som før. |
| Lokal utvikling, tester, forhåndsvisninger | Telleren er av med mindre sidens opprinnelse er nøyaktig `origin` i konfigurasjonen (`https://bootdisk.no`). Ingen forespørsel sendes. |
| Kurateringssider, kø- og oversiktsverktøy, 404 | Har ikke telleren. |

### Lagring og atomisk oppdatering

SQLite-filen har fire tabeller (`counter/schema.sql`): én rad med `total` og `since`, besøks-
nøkler med utløp (48 timer), et samlet døgntall (`counted`, `limited`), og et minutt-tall for
minuttgrensen (slettes etter fem minutter). Hver telling kjører i én `BEGIN IMMEDIATE`-
transaksjon med `busy_timeout` på 5 sekunder: slette utløpte nøkler, sjekke nøkkelen, sjekke
grensene, sette inn nøkkelen og øke totalen. Parallelle forespørsler venter på hverandre i
stedet for å overskrive hverandre.

Tjenesten lager **aldri** databasen selv. Mangler filen, svarer den 503. En borte eller
feilplassert fil blir dermed «Teller utilgjengelig», ikke en stille nullstilling med ny
startdato. Databasen opprettes bare med `scripts/visit-counter-db.py init`.

### Misbruksgrenser

CORS eller en skjult adresse stopper ikke et skript. Det som faktisk begrenser er:

- **Minuttgrense:** høyst 60 nye besøk per minutt (`BOOTDISK_COUNTER_MINUTE_LIMIT`).
- **Døgngrense:** høyst 3000 nye besøk per døgn, norsk tid (`BOOTDISK_COUNTER_DAY_LIMIT`).
- Besøk over grensen telles ikke, men telles som `limited` i døgntabellen, så et angrep synes
  i `status` og kan rettes ved å gjenopprette en sikkerhetskopi.
- Streng inndata: bare `POST` med `Content-Type: application/json`, høyst 256 byte, nøyaktig
  feltet `visit` med 32 små heksadesimale tegn. `Origin` må være produksjonsadressen og
  `Sec-Fetch-Site`, når den finnes, `same-origin`. Dette stopper forespørsler fra andre
  nettsteder i vanlige nettlesere; et skript kan forfalske dem.

Grensene gjør oppblåsing langsom og synlig, ikke umulig. Sterkere vern krever å kjenne igjen
avsendere (IP, fingeravtrykk, innlogging), som arbeidsordren utelukker. Grenseverdiene er
valgt høyt over forventet trafikk for et lite arkiv; juster dem etter faktisk bruk.

### Personvern

- Ingen IP-adresser, informasjonskapsler, fingeravtrykk eller nettleserdata lagres. Testen
  dumper hele databasen og kontrollerer det.
- Nettleseren lagrer bare nøkkelen og tre tidsfelt, og sender bare nøkkelen
  (`credentials: "omit"`, `referrerPolicy: "no-referrer"`).
- Tjenesten skriver ingen logg og sender ingen detaljer i feilsvar.
- Nøkler slettes etter 48 timer; minutt-tall etter fem minutter. Døgntall er aggregerte.
- Ingen hemmeligheter finnes, og ingen trengs, verken i JavaScript eller på serveren.

## HTTP-kontrakt

```text
GET  /api/besok.php
  200 {"total": 1234, "since": "2026-10-01"}

POST /api/besok.php   Content-Type: application/json   {"visit": "<32 små hex-tegn>"}
  200 {"total": 1235, "since": "2026-10-01", "counted": true,  "limited": false}
  200 {"total": 1235, "since": "2026-10-01", "counted": false, "limited": false}  (kjent nøkkel)
  200 {"total": 1235, "since": "2026-10-01", "counted": false, "limited": true}   (over grensen)

400 feil nøkkel · 403 feil opprinnelse · 405 annen metode · 413 for stor · 415 feil type
503 {"error": "unavailable"}  database mangler, feil skjemaversjon eller lagringsfeil
```

Alle svar har `Cache-Control: no-store`. Nettleseren godtar bare en `total` som er et helt,
ikke-negativt tall og en `since` som er en gyldig dato; alt annet vises som utilgjengelig.

## Offentlig pakke

`build-release.py` tar med `visit-counter.css`, `visit-counter-config.js`,
`visit-counter-core.js`, `visit-counter-adapter.js` og `visit-counter.js`. Forsiden,
detaljsiden (`index.html`), arkivet og samlingssiden laster dem. Pakken inneholder ingen
`.php`, `.sql` eller `.sqlite`, og konfigurasjonen er avslått. `verify-deployment.py` krever
404 for `counter/besok.php`, `counter/schema.sql` og `scripts/visit-counter-db.py`.

## Aktivering (når punkt 1–3 er bekreftet)

Dette er en egen, gjennomgått endring, ikke en del av denne leveransen:

1. Opprett databasen lokalt samme dag som telleren settes i drift:
   `python scripts/visit-counter-db.py init besok.sqlite`
2. Last den opp til `/bootdisk-besok/besok.sqlite` (utenfor `/www`).
3. Utvid releasebygget med `api/besok.php` (kopi av `counter/besok.php`), så deploy-steg 5
   ikke sletter tjenesten, og sett `endpoint: "api/besok.php"` i `visit-counter-config.js`.
4. Deploy som vanlig. Kontroller med `curl https://bootdisk.no/api/besok.php` (skal gi
   `{"total":0,…}` og ikke opprette noe), og at bunnteksten viser `000001` etter første besøk.
5. Utvid `verify-deployment.py` med en kontroll av at `GET api/besok.php` svarer med gyldig JSON.

## Sikkerhetskopi og gjenoppretting

- **Sikkerhetskopi med skalltilgang:** `python scripts/visit-counter-db.py backup besok.sqlite
  kopi.sqlite` bruker SQLites backup-API (konsistent under skriving) og kontrollerer kopien.
- **Sikkerhetskopi med bare FTP:** last ned `besok.sqlite`. Kjør
  `python scripts/visit-counter-db.py status besok.sqlite` på kopien. Står det ikke
  `integritet: ok`, ble filen tatt midt i en skriving: last ned på nytt. En eventuell
  `besok.sqlite-journal` ved siden av betyr det samme.
- **Gjenoppretting:** last opp en kontrollert kopi over `besok.sqlite` og slett en eventuell
  `-journal`-fil. Besøk mellom kopien og gjenopprettingen går tapt; nøkler i kopien som er
  eldre enn 48 timer slettes ved neste telling.
- **Oppblåst tall:** `status` viser døgntall og avviste forsøk. Gjenopprett siste kopi fra før
  toppen. Rediger ikke totalen for hånd uten å notere hvorfor.
- Deploy og rollback av nettstedet rører ikke databasen, fordi den ligger utenfor `/www`.

## Lokal demonstrasjon

Bare for å se telleren virke mot den foreslåtte tjenesten. Dette er ikke produksjonstall og
ikke en ferdig besøksteller.

```sh
python tests/synthetic_collection.py /tmp/besok-release
python scripts/visit-counter-db.py init /tmp/besok.sqlite
printf 'window.BOOTDISK_VISIT_COUNTER = Object.freeze({ origin: "http://127.0.0.1:8812", endpoint: "api/besok.php" });\n' \
  > /tmp/besok-release/visit-counter-config.js
BOOTDISK_COUNTER_SCRIPT="$PWD/counter/besok.php" BOOTDISK_COUNTER_DB=/tmp/besok.sqlite \
BOOTDISK_COUNTER_ORIGIN=http://127.0.0.1:8812 \
  php -S 127.0.0.1:8812 -t /tmp/besok-release tests/visit_counter_router.php
```

Åpne `http://127.0.0.1:8812/`. Konfigurasjonen endres bare i den midlertidige kopien.

## Kontrollmatrise

Faktiske resultater på grenen `feat/visit-counter`. Testene i `tests/test_visit_counter.py`
(Node og PHP) og `tests/test_visit_counter_browser.py` (Chromium og PHP).

| Krav | Kode | Test | Resultat |
| --- | --- | --- | --- |
| Første besøk øker én gang; navigering og omlasting gjør det ikke | `visitPlan`, `visitRun` | `test_first_view_counts…`, `test_one_visit_counts_once_across_front_collection_archive_detail_and_reload` | Bestått: fire sider og omlasting gir `000001` og én POST |
| Nytt besøk etter 30 min inaktivitet, styrt klokke | `VISIT_IDLE_MS` | `test_idle_limit_is_thirty_minutes…`, `test_a_new_visit_counts_only_after_thirty_idle_minutes` | Bestått: 30:00 samme besøk, 30:00,001 nytt |
| Parallelle forespørsler mister ingen oppdateringer | `BEGIN IMMEDIATE` i `besok.php` | `test_parallel_requests_lose_no_updates…` (120 forespørsler, 8 PHP-arbeidere) | Bestått: total 40 av 40 nøkler |
| Ny innsending etter tidsavbrudd dobbeltteller ikke | `visitConfirm`, nøkkeltabell | `test_lost_response_is_resent…`, `test_lost_response_shows_unavailable_and_the_reload_resends_the_same_key` | Bestått: tjenesten teller, svaret tapes, omlasting sender samme nøkkel, total 1 |
| Parallelle faner | Web Lock i `visit-counter.js` | `test_two_tabs_sharing_storage…`, `test_parallel_tabs_opened_together_count_one_visit` | Bestått: én nøkkel, total 1 |
| Omstart og ny opplasting nullstiller ikke | database utenfor `/www` | `test_restart_keeps_the_total…`, `test_redeploying_the_static_site…` | Bestått |
| Manglende database er utilgjengelig, ikke null | `open_counter` | `test_missing_database_is_unavailable_not_zero` (begge filer) | Bestått: 503, ingen ny fil |
| Nettverksfeil, 503, ugyldig svar | adapter, `visitParseResponse` | `test_failures_show_unavailable_while_the_archive_keeps_working` (6 feiltyper) | Bestått: «Teller utilgjengelig», ingen sifre, arkivet virker |
| Blokkert lagring | `visitRun` | `test_blocked_storage…` (begge filer) | Bestått: total vises, ingen POST |
| Ingen forespørsler til produksjon fra lokal kjøring og tester | `origin`-sjekk, `endpoint: null` | alle nettlesertester avbryter og feiler på andre verter; `test_an_activated_production_config_stays_silent_outside_bootdisk_no` | Bestått: 0 forespørsler utenfor testserveren |
| Grenser mot misbruk | minutt- og døgngrense | `test_minute_and_day_limits…`, `test_malformed_foreign_or_oversized_requests_change_nothing` | Bestått |
| Ingen IP eller nettleserdata lagret | skjema, `besok.php` | `test_storage_holds_no_address_or_browser_data` | Bestått |
| Minst seks felt, ingen avkutting | `visitDigits`, CSS | `test_display_pads…`, `test_large_totals_grow…` (320, 360, 1280 px, 9 sifre) | Bestått: ingen overlapp, ingen horisontal rulling |
| Skjermleser: én etikett, vanlig tall | `aria-hidden` på sifre, `.visit-counter-text` | `test_screen_readers_get_one_label…` | Bestått: «1 234 besøk siden 25. september 2026»; ingen live-region, ingen fokuserbare elementer, ingen animasjon |
| Ingen layoutforskyvning | tomme felt under lasting, `min-height` | `test_counter_reserves_its_space…` | Bestått: samme posisjon og høyde før og etter svar, og ved feil |
| Pakken har nøyaktig tellerfilene, avslått, uten backend | `STATIC_FILES`, `NOT_PUBLIC` | `CounterReleaseTests` | Bestått |

### Feil testene faktisk fanger

Hver feil under ble lagt inn i koden, testene kjørt, og koden satt tilbake.

| Innlagt feil | Fanget av |
| --- | --- |
| Inaktivitetsgrensen `<` i stedet for `<=` | kjernetest og nettlesertest |
| Bekreftet besøk sendes likevel | 7 tester |
| Ny nøkkel ved ny innsending (dobbelttelling etter tidsavbrudd) | 5 tester, også nettleseren |
| Blokkert lagring teller hver side | kjernetest og nettlesertest |
| Bekreftelse overskriver et besøk en annen fane startet | kjernetest |
| Svarkontrollen godtar `"12"` som total | 4 tester |
| Feil vises som `000000` | nettlesertest, alle 6 feiltyper |
| `.visit-counter { display: inline-flex }` overstyrer `hidden` | nettlesertest (**fant en ekte feil under utviklingen**: den avslåtte telleren viste en tom boks) |
| Sifrene leses opp ett og ett (uten `aria-hidden`) | nettlesertest |
| Fem sifferfelt | 6 tester |
| Telleren aktiv på en annen opprinnelse enn produksjon | nettlesertest |
| PHP les-endre-skriv uten transaksjon | parallelltesten |
| PHP uten duplikatsjekk | 6 tester |
| PHP uten opprinnelsessjekk | tjenestetest |
| PHP oppretter manglende database | tjenestetest og nettlesertest |
| PHP uten grenser | tjenestetest |
| PHP husker nøkler i 1 time | 2 tester, også konstantsammenligningen |
| PHP-fil med i releasen | releasetestene |
| Aktivert konfigurasjon i pakken | releasetest (**fant et hull i testen**: den sjekket teksten `endpoint: null`, som også står i kommentaren) |
| Adapteren uten tidsavbrudd | adaptertest (**fant et hull i testoppsettet**: et løfte som aldri ble avgjort lot Node avslutte med kode 0; testene krever nå en ferdig-markør) |
| Uten Web Locks | **Ikke pålitelig fanget.** Parallellfanetesten feilet i 1 av 5 kjøringer uten låsen. Lesing og skriving av `localStorage` skjer i én synkron blokk, så kappløpet er smalt. Testen er en sannsynlighetssjekk, ikke et bevis. |

## Kjente begrensninger

- Produksjonsaktivering er blokkert til punkt 1–3 er bekreftet.
- PHP-tjenesten er testet med PHP 8.4 og SQLite i en Linux-container, ikke på Domeneshop.
- Grensene begrenser oppblåsing, men hindrer den ikke.
- Nettlesere uten Web Locks kan i sjeldne tilfeller telle to faner som åpnes i samme øyeblikk.
