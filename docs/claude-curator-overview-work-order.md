# Arbeidsordre til Claude: skalerbar kurateringsoversikt

## Oppdrag og ferdigkriterium

Bygg første frontend-prototype for effektiv oversikt over flere tusen
programoppføringer. Stian har godkjent dagens kurateringsflyt for én oppføring.
Behold den som detaljvisning. Lever en separat oversikt med søk, feltfiltre,
status og navigasjon til/fra detaljvisningen, med tester og én PR til
`bootdiskhq/bootdisk-web`. Ikke merge eller publiser selv.

Dette er neste utviklingstrinn etter dagens lokale 1.2-arbeid. Prototypen skal
kunne vurderes uten å endre Stians aktive kuratering. Massegodkjenning er utsatt.

## Arbeidssted og gren

Endre kun `bootdisk-web`. Bruk en separat checkout/worktree fra oppdatert `main`,
for eksempel grenen `feat/curator-overview`. Ikke bytt gren i Stians aktive
arbeidsmappe `/Users/stian/Bootdisk/bootdisk-web`: den serverer kurateringen hans.
Ikke endre eller kopier brukerdata inn i repoet, og ikke skriv til
`/Users/stian/Bootdisk/local-results/review-1.2-dev`. Ikke bruk eller stopp
port 8772, Stians nettleserfane eller hans lokale tjeneste. Bruk en ledig separat
port og isolerte, tydelig merkede prøvedata. Ikke ta over port 8773 uten å sjekke
om den er i bruk. Egen checkout er obligatorisk mens Stian kuraterer.

Utgangspunkt da ordren ble skrevet:

- Web main: `39965560eecf3476c825f67da98369137b2a9bd0`.
- Catalog main: `2dacd311da561734875ead83f3e8f86a188708f0`.

Hent siste main og noter faktiske commit-er i PR-en; ikke tilbakestill nyere arbeid.

## Les først

I Web: `README.md`, `curate.js`, `curate-core.js`, `curate-adapter.js`,
`curate-live-adapter.js`, `scripts/build-release.py` og relevante tester.

I Catalog: `docs/adr-004-local-curator-boundary.md`,
`docs/adr-005-review-state-and-decisions.md`, `docs/adr-006-hosted-curator-access.md`,
`docs/curator-contract-v1.md`, `docs/local-curator-service.md` og
`docs/curation-next-step.md`. Naborepoet finnes på
https://github.com/bootdiskhq/bootdisk-catalog/tree/main/docs dersom det ikke
finnes lokalt.

Merk at innledningen i v1-kontrakten fremdeles beskriver tiden før lokal tjeneste.
Tjenesten og live-adapteren er nå implementert. Bruk dagens kode og servicedokument
for leverte tillegg; rapporter kontraktavvik i stedet for å finne på API-er.
Den gamle `claude-curator-work-order.md` dokumenterer allerede levert arbeid og
skal ikke brukes som ordre for å bygge detaljskjermen på nytt.

## Første leveranse

Lag en separat lokal oversikt i eksisterende HTML/CSS/JavaScript-stil:

- Tabell med programnavn, kildepost, versjon, innholdstype, utgave og
  vurderingsstatus. «Utgave» viser eksisterende `distribution_kind`; lisens som
  Freeware er et annet begrep. Ikke endre lagrede verdier eller datakontrakten.
- Søk etter navn og kildepost, filter på ventende/utsatt/gjennomgått/alle og på
  hvilke felt som er uavklarte eller trenger kontroll. Kombiner søk og filtre.
- Vis gjennomgått og fullstendig avklart som forskjellige ting. En gjennomgått
  oppføring kan fortsatt ha åpne felt eller krav om ny kontroll.
- Vis tydelig om en verdi er kladd eller sist godkjent. Ikke presenter en endret
  kladd som katalogens godkjente verdi. Vis ukjent verdi forståelig på norsk.
- Åpne en bestemt rad i eksisterende detaljflyt på dens stabile kildeidentitet,
  og gå tilbake til samme søk, filtre, side og rad med forutsigbart tastaturfokus.
  Bruk både manifest og entry som identitet; K23 alene er ikke globalt unik.
- Etter en beslutning oppdateres raden fra adapterens faktiske svar. Hvis raden
  faller utenfor filteret, forklar det kort og behold et fornuftig sted i listen.
- Vis totalantall, treffantall og tydelige laste-, tom- og feiltilstander.
  Søk og filtrering må ikke skrive, godkjenne eller endre kurateringsdata.

Bruk norsk bokmål og eksisterende visuell stil. Ingen rammeverksmigrering eller
større redesign. Bruk ordinær paginering eller en annen enkel begrensning av antall
rader i DOM; begrunn valget. Ikke lag tusenvis av interaktive rader på én gang.
Tabellen skal ha overskrifter, tydelig fokus og lesbare statuser uten å være
avhengig av farge. Smal skjerm skal gi tilgang til samme informasjon.

## Data og adaptergrense

Dagens `getQueue` gir nøkkel, tittel, køstatus, identifikasjonsstatus og åpne felt.
Den gir **ikke** versjon, innholdstype og utgave for hver rad. Ikke skjul dette
ved å sende ett `getEntry`-kall for hver av flere tusen oppføringer ved oppstart.

Første PR kan derfor være en tydelig fixture-prototype. Gjenbruk den eksisterende
fixture-adapterens detalj- og beslutningssemantikk. Et separat, testlokalt
oversiktslag kan bygge sammendrag fra prøvedata, men skal merkes som prototype.
Dokumenter det minste nødvendige forslaget til Catalogs fremtidige lesekontrakt:
sammendragsfelt, kladd kontra akseptert verdi, søk/filtrering, stabil sortering og
paginering. Dette er et forslag til Birk/Codex, ikke en ny godkjent produksjons-API.

Ekte adapter skal ikke forsøke oppdiktede endepunkter. Ingen automatisk overgang
fra ekte modus til prøvedata ved feil. Ikke påstå at oversikten er ferdig integrert
med tjenesten før Catalog har levert og vi har testet kontrakten sammen.

Lag deterministiske prøvedata med minst 5 000 oppføringer, flere manifest-ID-er,
gjentatte K-ID-er og programnavn, åpne felt, ulike vurderingsstatuser og en blanding
av korte/lange navn. Bruk tydelig fiktive programmer til skalatesten. Ikke bruk
syntetiske poster som katalogfunn eller bland dem med ekte kuratering.

## Bevar dagens regler

- Beskrivelse er original CD-omtale og skrivebeskyttet når
  `original_description_v1` gjelder. Egne vurderinger hører hjemme i begrunnelsen.
- Belegg vises som originaltekst, aldri som kjørbar HTML. Hasher hører hjemme
  i tekniske detaljer. Ikke endre kildedata, semantiske ID-er eller påstander.
- `classification_review_required` betyr at tidligere klassifisering trenger
  kontroll. Belagt krever kildevalg og begrunnelse; lisens alene fastslår ikke utgave.
- Behold sikker autosave, revisjonskontroll, idempotente gjenforsøk og eksplisitt
  godkjenning. Navigasjon må ikke miste ulagret tekst, heller ikke ved feil.
- Ikke endre Catalog, Ingest, Publish, originalmedia eller den aktive tjenesten.
- Ikke bygg masseendringer, massegodkjenning, automatisk klassifisering, innlogging,
  nettbasert drift, import av ny CD eller ny publiseringsflyt i denne oppgaven.
- Alle prototypefiler og prøvedata skal holdes utenfor offentlig release-allowlist.

## Tester og akseptanse

Kjør eksisterende tester med Python 3.10+ og Node, og legg til meningsfulle
atferdstester for:

1. Kombinert søk og felt-/statusfilter, null treff og tilbakestilling.
2. Deterministisk paginering uten tapte/dupliserte rader, også med like navn og
   samme K-ID i forskjellige manifest.
3. Oversikt → valgt detalj → tilbake beholder posisjon, filtre og fokus.
4. Godkjenning, utsettelse og angre oppdaterer oversikten korrekt via adapteren;
   en gjennomgått rad med åpne felt blir ikke merket fullstendig avklart.
5. Feilet lagring og konflikt beholder utkastet og hindrer usikker navigasjon.
6. Tregt gammelt søkeresultat kan ikke erstatte et nyere resultat. Dersom søket
   er helt synkront, dokumenter det og test tilsvarende race ved asynkron lasting.
7. Ingen kall til skriveoperasjoner ved søk/filter, ingen detaljkall per rad ved
   oppstart og begrenset antall gjengitte rader ved 5 000 oppføringer.
8. Prototypen og prøvedata kommer ikke med i offentlig release.

Gjør også manuell tastaturprøve, smal visning og måling med 5 000 oppføringer.
Rapporter datamengde, nettleser/maskin, oppstartstid, søketid og antall gjengitte
rader. Mål: søket skal oppleves umiddelbart (sikt mot under 200 ms etter inntasting
uten kunstig nettverksforsinkelse). Oppgi måleresultater, ikke bare «raskt».
Testene skal ikke være skjøre tidskrav på ukjent CI-maskinvare.

## Levering

Lever én PR mot `bootdisk-web/main`, med:

- Konkret hva som fungerer, hva som kun er fixture, og backendavhengighetene.
- Eksakt oppstartskommando og lokal URL på separat port.
- Skjermbilder av oversikt, feltfilter og smal visning.
- Kjørte tester, manuelle forløp og ytelsesmålinger; merk det som ikke ble kjørt.
- Forslag til nødvendig lesekontrakt, uten å endre Catalogs kontrakt på egen hånd.
- Kjente avvik og faktisk Web/Catalog-utgangspunkt.

Ikke merge, deploy eller kall dette ferdig release. Stian prøver prototypen og
Birk/Codex gjennomgår PR-en før eventuell integrasjon.
