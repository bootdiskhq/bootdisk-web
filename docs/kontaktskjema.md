# Om prosjektet og kontaktskjemaet

**Status: kode og tester er klare. Produksjonsoppsett og publisering er ikke gjort.** Siden
`om-prosjektet.html` og mottaket `api/kontakt.php` er med i releasepakken. Uten privat
konfigurasjon på serveren svarer mottaket `{"ready": false}`, siden sier at skjemaet ikke tar
imot meldinger, og ingenting sendes.

## Hva som er bygd

| Del | Filer | Ansvar |
| --- | --- | --- |
| Side | `om-prosjektet.html`, stiler i `catalog.css` | Teksten, «Kontakt oss» under teksten, retrodesignet |
| Meny | `index.html`, `archive.html`, `collection.html`, `updates.html`, `404.html` | «Om prosjektet» rett etter «Siste endringer». Kildepostene (`index.html?entry=…`) bruker samme topp |
| Kjerne | `contact-core.js` | Feltkontroll, svartolkning, norske feilmeldinger, fast liste over CAPTCHA-skript |
| Skjema | `contact.js` | Henter oppsett, laster CAPTCHA når skjemaet tas i bruk, sender, bevarer teksten |
| Mottak | `api/kontakt.php` | Oppsett → opphav → felter → hyppighetsgrense → CAPTCHA → sending |
| Eksempel | `docs/examples/kontakt-config.example.php` | Generisk konfig med plassholdere (`*.invalid`) |
| Kontroll | `scripts/check-private-config.py` | Leter etter private verdier i Git-område, katalog og ZIP |

### Oppførsel for leseren

- Skjemaet har e-postadresse og melding (inntil 4000 tegn), og en hjelpetekst om å lime inn
  lenken til en kildepost. Et skjult fellefelt fanger enkle roboter og nås ikke med tastaturet.
- Teksten tømmes bare etter en bekreftet sending. Ved alle feil står e-post og melding i
  feltene, og feilmeldingen sier det. Et utkast holdes i `sessionStorage`, så en omlasting i
  samme fane ikke mister teksten. Uten lagring virker skjemaet likevel.
- Feil blir lest opp (`role="alert"`), feltet får `aria-invalid` og fokus. Etter sending får
  kvitteringen fokus. På mobil er feltene 16 px (ingen automatisk zoom) og knappen 44 px høy.
- CAPTCHA-skriptet hentes fra leverandøren først når leseren går inn i skjemaet, og bare når
  serveren melder at oppsettet er klart. Siden laster ellers ingenting utenfra.

### Mottaket

- **Oppsett mangler** (fil borte, ufullstendig, ugyldige verdier, konfig eller tilstandsmappe i
  webroten, SMTP-pålogging uten kryptering): `GET` gir `{"ready": false}`, `POST` gir 503
  `not_configured`. Ingen CAPTCHA-kontroll og ingen sending.
- **Opphav:** bare `POST` med `Origin` lik `allowed_origin`, `Content-Type: application/json`
  og høyst 64 KB.
- **Svaradresse:** validert med `FILTER_VALIDATE_EMAIL`, høyst 254 tegn, uten linjeskift,
  komma, `<>` eller anførselstegn. Den brukes bare i `Reply-To`.
- **Fast mottaker og fast avsender** fra konfigen. `From` er alltid avsenderen; `-f` setter
  konvoluttavsenderen for `mail()`.
- **Hyppighetsgrense** før CAPTCHA: standard 3 forsøk per klient per 10 minutter og 40 per
  døgn totalt. Avviste forsøk teller også. Klienten lagres som HMAC av IP-adressen med
  `client_salt`; filen har aldri adresser eller tekst. 429 med `Retry-After`.
- **CAPTCHA** (Cloudflare Turnstile eller hCaptcha) kontrolleres mot leverandørens siteverify
  før noe sendes. Utløpt eller brukt token → `captcha_expired`, manglende → `captcha_missing`,
  avvist → `captcha_rejected`, leverandør nede eller feil hemmelighet → `captcha_unavailable`.
  Valgfritt krav om vertsnavn (`captcha.hostname`).
- **Sending:** PHPs `mail()` eller SMTP (STARTTLS/TLS med sertifikatkontroll, AUTH LOGIN).
  Feil gir 502 `send_failed`.
- **Logg:** bare hendelser som «sending feilet». Aldri adresser, meldingstekst, tokens eller nøkler.
  Meldingen lagres ikke på serveren.

Feilkoder: `not_configured`, `forbidden_origin`, `bad_request`, `method_not_allowed`,
`invalid_email`, `invalid_message`, `message_too_long`, `rate_limited`, `captcha_missing`,
`captcha_expired`, `captcha_rejected`, `captcha_unavailable`, `send_failed`.

## Privat konfigurasjon

Ekte mottaker, avsender, CAPTCHA-nøkler, salt og eventuell SMTP-pålogging står **bare** i én
PHP-fil på webhotellet, utenfor webroten:

```
/                         (FTP-roten for kontoen)
├── www/                  webroten; erstattes ved hver deploy
│   └── api/kontakt.php
└── bootdisk-privat/      aldri under www/, aldri i Git, aldri i pakken
    ├── kontakt-config.php
    └── kontakt-tilstand/ skrivbar for PHP
```

`api/kontakt.php` leser `../../bootdisk-privat/kontakt-config.php` regnet fra seg selv. Den
nekter å bruke en konfig eller tilstandsmappe som ligger under `DOCUMENT_ROOT`. Fordi mappen
ligger ved siden av `www/`, rører ikke deploy-steg 5 («fjern filer som ikke er i releasen») den.

Vern mot lekkasje:

- `.gitignore` ignorerer `kontakt-config.php` og `bootdisk-privat/` overalt i repositoryet.
- `build-release.py` kopierer bare en fast liste, og `refuse_private_config` stopper bygget hvis
  pakken likevel inneholder `kontakt-config.php`, en `bootdisk-privat`-mappe eller en PHP-fil med
  `'recipient' =>` eller `'client_salt' =>`.
- `verify-deployment.py` krever 404 for eksempelkonfigen, denne veiledningen og kontrollskriptet.
- `scripts/check-private-config.py` søker etter de ekte verdiene, se under.

## Lekkasjekontroll før publisering

Legg de ekte verdiene i en fil **utenfor** repositoryet, én per linje (mottaker, avsender,
CAPTCHA-hemmelighet, salt, SMTP-bruker og -passord). Kontroller grenen og den ferdige pakken:

```sh
python3 scripts/check-private-config.py --values-file ~/privat/bootdisk-verdier.txt \
    --git origin/main..HEAD --tree dist/bootdisk-web --zip dist/bootdisk-web-<versjon>.zip
```

Skriptet skriver aldri ut en verdi, bare nummeret og hvor den ble funnet. «privat konfig: ingen
funn» og utgangskode 0 er bestått. Testene gjør det samme med oppdiktede verdier.

## Oppsett på webhotellet (gjøres i gjennomgangen, ikke av denne PR-en)

Forutsetninger som må bekreftes for kontoen: PHP 8.1 eller nyere for `/www`, at PHP kan lese
og skrive i en mappe ved siden av `/www` (ingen `open_basedir` som stenger den ute), og at
`mail()` eller SMTP er tillatt. Hvis `mail()` ikke leverer, bruk SMTP-varianten i eksempelet.

1. Lag `/bootdisk-privat/` og `/bootdisk-privat/kontakt-tilstand/` ved siden av `/www`.
   Tilstandsmappen må være skrivbar for PHP.
2. Opprett et nettsted hos CAPTCHA-leverandøren for `bootdisk.no` og noter offentlig nøkkel og
   hemmelig nøkkel.
3. Kopier `docs/examples/kontakt-config.example.php` lokalt, fyll inn de ekte verdiene, og
   last den opp som `/bootdisk-privat/kontakt-config.php`. Sett `allowed_origin` til
   `https://bootdisk.no` og `state_dir` til den fulle serverstien til tilstandsmappen. Lag
   salt med `php -r 'echo bin2hex(random_bytes(32));'`. Ikke legg kopien i repositoryet.
4. Deploy releasen som vanlig (`domeneshop-deploy.md`).
5. Kontroller: `python scripts/verify-deployment.py https://bootdisk.no/ --require-contact`.
   Den feiler hvis PHP ikke kjører (kildekoden serveres) eller oppsettet mangler.

## Oppskrift til Birk: én ekte prøve med mottak og svar

Gjøres etter at punktene over er på plass, med en e-postadresse du selv leser (ikke mottakeren).

1. Åpne `https://bootdisk.no/om-prosjektet.html` i et privat vindu. Sjekk at «Om prosjektet» står
   etter «Siste endringer», også når du åpner en kildepost.
2. Skriv din egen adresse i «E-postadressen din». Skriv en kort melding som begynner med
   «PRØVE fra Birk» og lim inn lenken til en kildepost.
3. Bekreft CAPTCHA og trykk «Send melding». Forventet: «Takk! Meldingen er sendt …», og
   meldingsfeltet tømmes.
4. **Mottak:** innen få minutter skal meldingen ligge i Bootdisks kontaktinnboks (ikke i søppel):
   avsender er den faste skjemaavsenderen, emnet er «Melding fra kontaktskjemaet på Bootdisk»,
   teksten og lenken er hele, og æøå er riktige.
5. **Svar:** trykk Svar i innboksen. Mottakerfeltet skal fylles med *din* adresse (Reply-To),
   ikke skjemaavsenderen. Send svaret og sjekk at det kommer fram hos deg.
6. Send tre meldinger til raskt etter hverandre (bekreft CAPTCHA hver gang). Den tredje skal få
   «Det er sendt mange meldinger …», og teksten skal stå igjen (grensen er 3 per 10 minutter).
7. Noter resultatet (tid, levert/søppel, svar OK) i PR-en. Slett prøvemeldingene.

Ved feil: se webhotellets PHP-feillogg etter linjer som begynner med `bootdisk-kontakt:`.
«oppsett mangler» eller «ligger i webroten» betyr feil sti; «captcha-oppsettet avvises» betyr
feil nøkkelpar; «sending feilet» eller «smtp: …» betyr at e-posten ikke ble levert.

## Tester

`tests/test_contact.py` (kjerne i Node, mottak i `php -S`, SMTP, pakke og lekkasjekontroll) og
`tests/test_contact_browser.py` (Chromium mot en ekte pakke i `php -S`).

Simulert, ikke ekte: CAPTCHA-widgeten (falskt Turnstile-skript), leverandørens siteverify
(lokal tjeneste med samme svarformat), e-postutsending (falsk `sendmail` for `mail()`, lokal
SMTP-server med selvsignert sertifikat) og webhotellet (`home/www` + `home/bootdisk-privat`).
Ingen test sender ekte e-post eller snakker med en ekte leverandør. Leveranse til en ekte
innboks, spamfiltrering og svar er bare dekket av Birks prøve over.
