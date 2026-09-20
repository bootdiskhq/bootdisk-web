# Lokal kurateringsflyt — frontend v1

Første frontend-leveranse for kuratering i 1.2. Skjermen kjører lokalt mot en
utskiftbar asynkron adapter. I denne leveransen er adapteren en **fixture-adapter**
som leser det uendrede prøvedatadokumentet fra Catalog og lagrer simulert
gjennomgangstilstand i nettleseren. Ingen katalogdata skrives.

| | |
| --- | --- |
| Kontraktversjon | `bootdisk-curator-v1` |
| Catalog-commit | `09bd0dbccac4e9ee39f1d2593558f96543449116` |
| Dokumenter | ADR-004, ADR-005, `curator-contract-v1.md`, `curator-fixtures-v1.json` |

## Start prøvevisningen

Serveres fra reporoten, fordi prøvedataene ligger under `tests/fixtures/`:

```sh
python -m http.server 8000
```

Åpne `http://localhost:8000/curate.html`.

Skjermen er merket «Prøvedata – endrer ikke katalogen» så lenge fixture-adapteren er
i bruk. Panelet «Simuleringer» armerer lagringsfeil, tjenestebrudd, tidsavbrudd etter
utført skriving, revisjonskonflikt og manglende/uleselig kilde, og tilbakestiller
prøvedataene. Simulerte tilstander er merket som simulerte.

## Filer

| Fil | Ansvar |
| --- | --- |
| `curate.html` | Siden. Ikke i den offentlige release-allowlisten. |
| `curate.css` | Stil, bygget på eksisterende visuell identitet. |
| `curate-adapter.js` | Fixture-adapter: alle sju kontraktmetodene, validering, revisjoner, operasjons-ID-er, historikk, simuleringer. |
| `curate-core.js` | Beslutningslogikk uten DOM: kladd, serialiserte skrivinger, konflikt, gjenopptakelse, hurtigtastregler. |
| `curate.js` | Binding mot siden. Tekst rendres alltid som tekst. |
| `tests/fixtures/` | Uendret prøvedatadokument fra Catalog, med opphav i egen README. |

UI-koden kjenner ikke lagringsformatet. Å bytte til den virkelige adapteren er å bytte
ut objektet som sendes inn i `createCuratorController`.

## Hurtigtaster

`G` godkjenn/lagre og neste · `H` hopp over · `Z` angre · `E` første felt ·
`←`/`→` forrige/neste · `?` vis hurtigtastene.

Tastene er av i `input`, `textarea`, `select` og `contenteditable`, ved
tekstkomposisjon (IME) og på gjentatte keydown-hendelser, og overstyrer ikke
nettleserens egne snarveier. Knapper og taster bruker samme handlingskode.

## Varighet og feilhåndtering

Fixture-adapteren lagrer i nettleseren. En lagring som blir avvist — full kvote, blokkert
opprinnelse — er en **mislykket skriving**: adapteren ruller tilbake den interne
tilstanden og svarer `write_failed`. Kladden beholdes lokalt på skjermen, men ingenting
påstås lagret. Er nettleserlagring utilgjengelig i det hele tatt, sier siden det med en
synlig advarsel i prøvedatabanneret; en flyktig økt lover aldri at en kladd overlever en
omlasting.

Skrivinger er serialisert per oppføring, og hver forespørsel er bundet til kildeposten den
gjelder. Et svar som kommer tilbake etter at kuratoren har åpnet en annen oppføring
oppdaterer aldri den nye oppføringens tilstand. Å bytte oppføring venter ut en pågående
skriving, også når den lokale kladden ser ren ut.

Et gjenforsøk sender den opprinnelige forespørselen på nytt — samme operasjons-ID og
samme innhold — for `saveDraft`, `approve`, `defer` og `undo`. Det er dette som gjør et
tidsavbrudd etter en utført skriving trygt: tjenesten svarer med den opprinnelige
kvitteringen i stedet for å beslutte to ganger.

## Skjemaet og kladden

Skjemakontrollene bygges om bare når kladden byttes ut i sin helhet — ny oppføring,
løst konflikt — slik at markøren ikke flyttes mens noen skriver. Alle andre
oppdateringer avstemmer hver kontroll mot kladden, uten å røre den kontrollen som har
fokus. Det gjelder også endringer som skjer i kode: trykker kuratoren «Bruk forslaget»,
viser feltet og avkryssingen for kildebelegg straks det som faktisk ville blitt
godkjent. Vurderingen er fortsatt et eget, eksplisitt valg; et forslag godkjenner
ingenting av seg selv.

## Kontraktobservasjoner

Ingenting av dette er løst ved å endre Catalog-dokumentene. Punktene er forslag til
en samordnet avklaring.

1. **Historikk mangler i entry-dokumentet.** ADR-005 krever en append-only
   beslutningshistorikk, og akseptansekravet sier at historikken skal være
   tilgjengelig etter angring. Kontraktens liste over påkrevde felt har ingen
   historikk. Fixture-adapteren returnerer `history` som et additivt felt.
   *Forslag:* ta inn `history` (eller `decisions`) som et definert additivt felt i v1.

2. **Innholdstype har ingen uavklart verdi.** `content_kind` har seks verdier og
   ingen `unknown`. ADR-005 sier at grensesnittet ikke skal presse fram en gjetning,
   men et genuint uavklart innhold må likevel bære en av de seks verdiene.
   Implementasjonen beholder gjeldende verdi og merker påstanden `unresolved` med
   begrunnelse. *Forslag:* avklar om `unresolved` uten meningsbærende verdi skal
   være lovlig for dette feltet.

3. **Prøvedataene knytter alt kildebelegg til alle påstandene.** Begge oppføringene
   lister samtlige `evidence_ids` på hver av de fem påstandene. Kontrakten sier at
   «backend validerer det påberopte kildebelegget, ikke bare at det finnes». Når den
   virkelige tjenesten validerer relevans, kan en uendret prøvedatakladd bli avvist
   med `validation_failed`. *Forslag:* avklar hvor streng relevanskontrollen er, eller
   stram inn prøvedataene.

4. **Ingen operasjon angrer en utsettelse.** `undo` gjelder den siste reversible
   semantiske beslutningen. En utsettelse er ikke en semantisk beslutning, så en
   oppføring tas ut av «utsatt» bare ved å behandle den på nytt. Det er brukbart via
   køfilteret, men verdt å bekrefte som villet.

5. **Køen oppgir ingen samlede tellinger.** `getQueue` returnerer elementene for ett
   filter. For å vise forskjellen på gjennomgått og avklart laster skjermen køen to
   ganger (aktivt filter og `all`). Uten paginering i v1 går det greit, men et
   additivt `summary`-felt ville spart en runde.

## Hva som fortsatt venter på den virkelige tjenesten

- Ekte kataloglagring, semantisk skriver, identitetsvalidering og semantiske ID-er.
- Inspeksjon/utpakking av kildefiler; observasjonene her kommer fra prøvedataene.
- Historikk på disk, sikkerhetskopi/gjenoppretting av gjennomgangsområdet.
- Opprinnelseskontroll og sesjonstoken for skriving mot loopback.
- Integrasjon og Stians selvstendige prøve av ti ulike oppføringer.
