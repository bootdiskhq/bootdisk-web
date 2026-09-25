# Bootdisk Web: 0.2 til 1.0

Bootdisk Web forblir et lett, statisk og fullt regenererbart presentasjonslag. Catalog eier identitet og evidens; Publish eier webfilene. Nye versjoner skal ikke flytte dette ansvaret inn i nettleseren.

## 0.2 — Navigasjon

- Delbart søk, statusfilter og sortering.
- Kildekorrekt forrige/neste-navigasjon.
- Produksjonsbygg mot alle 39 K-CD 15/2001-poster.

## 0.3 — Semantikk og tilgjengelighet

- Bedre dokumentmetadata for deling og søkemotorer.
- Tydelige tom-, feil- og lastetilstander.
- Tastatur- og skjermleserkontroll av arkiv og detaljsider.

## 0.4 — Release og drift

- Én kontrollert kommando for full data- og webbygging.
- Maskinlesbar release-rapport med input- og output-hasher.
- Dokumentert, repeterbar Domeneshop-deploy og rollback.

## 1.0 — Stabil offentlig kontrakt

- [x] Produksjonsverifisert på `bootdisk.no` på mobil og desktop.
- [x] Stabile URL-er og dokumentert frontend-datakontrakt.
- [x] Ingen blokkerende tilgjengelighets-, integritets- eller deployfeil.
- [x] Nye medier kan bygges uten håndredigering av frontend-kode.

Rammeverksbytte og større visuell redesign er ikke et 1.0-krav. Bred kuratering kan fortsette uavhengig av webplattformens stabilitet.

## Public archive update — 1.2.0-rc1

Multi-medium publication and CD filtering are implemented, with original wording,
source-conflict notes and compatibility for existing K-number links. See
[release preparation and limitations](release-1.2.0-rc1.md).

The real multi-medium curator adapter, automatic field proposals and reversible
machine decisions remain open. They do not block publishing explicitly pending
source entries, and are not counted as delivered by this public archive update.

## Etter fem-CD-prøven i 1.2

Se [prøverapporten](five-disc-trial.md). Neste trinn er en gjenopptakbar innlesing
av flere medier med trinnstatus per CD, kontroll av bilde- og omtaledekning og én
avvikskø. Innlesingsavvik skal behandles samlet; automatisk kildeimport må fortsatt
skilles fra godkjent programidentitet, versjon og distribusjon.

## Prioritering avtalt 25. september 2026

Stian ønsker å begrense kostnadene ved AI-arbeid. Prioriter små, avgrensede
leveranser med synlig nytte. Ingen videre undersøkelse av eldre menyformater nå.
Dette erstatter rekkefølgen «fullstendighet først» fra den siste CD-kontrollen.

### 1. Originale RTF-omtaler på nett

Neste utviklingssteg. Behold CD-menyens omtale ordrett og tilgjengeliggjør
utfyllende RTF-tekst som en separat kilde med avsnitt, filnavn og originalnedlasting.
Ingest må registrere teksten også når menyomtalen finnes; Catalog beholder separate
kildeobservasjoner; Publish lager verifiserte webfiler. Identisk tekst vises ikke
dobbelt. Ikke oversett eller omskriv automatisk. Start med noen representative
oppføringer før utrulling til de allerede innleste CD-ene. Bevar kuratering og
historikk når nye kildeobservasjoner legges til.

Ferdig når faktisk tilleggstekst og originalfil kan åpnes på riktig oppføring,
menyomtalen er uendret, kildebinding og filintegritet er kontrollert, og feil/manglende
RTF håndteres uten å stoppe øvrig publisering.

### 2. Kurs og annet originalmateriale

Gjør kurs, PDF-hefter, guider og tilhørende øvingsfiler fra innleste medier lette
å finne og åpne. Behold originalt navn, omtale, språk og CD-tilhørighet. En kursserie
kan ha flere leksjoner og vedlegg uten å bli fremstilt som flere programmer.
Start med ett faktisk kurs som pilot. Koble bare materiale der kilden underbygger
sammenhengen; ikke anta at alle filer i en mappe er egne kurs eller sikre vedlegg.
Vis filtype og størrelse ved nedlasting. Definer separat kontrakt for kurs og
vedlegg før den generelle publiseringsflyten utvides.

### 3. Videokurs med innebygd YouTube-spiller

Avventer innlesing av nyere K-CD-distribusjoner som faktisk inneholder videokurs.
Ingen videopilot eller spillerimplementering startes på dagens CD-er.

Stian ønsker at videokurs fra senere K-CD-er kan spilles på Bootdisk via en
innebygd YouTube-spiller, med videoene lastet opp på en valgt YouTube-kanal.
Dette er en planlagt integrasjon; ingen kanal eller videoer er opprettet/lastet opp.

Bevar originalvideofilen, filhash og koblingen til CD, kurs og leksjon uavhengig
av YouTube. Catalog registrerer kursrekkefølge og en eksplisitt kobling til
YouTube-video-ID; Publish/Web lager spiller og lenke. Nettstedet skal forklare
hvis videoen ikke kan vises og tilby å åpne den på YouTube. En slettet video må
ikke slette arkivets kildeopplysninger eller originalbevaring.

Før pilotopplasting: velg én faktisk leksjon, avklar tillatelse til offentlig
gjenpublisering, hvilken kanal som skal brukes og ønsket synlighet. Kontroller
format, lyd, bilde, leksjonstittel og eventuell teksting. Verifiser aktuelle
YouTube-krav og innbyggingsmuligheter når integrasjonen gjennomføres. Bruk
klikk-for-å-laste spiller slik at ekstern avspilling først lastes ved brukerens valg.
Opplasting er en egen, eksplisitt godkjent handling; denne roadmappen publiserer
eller autoriserer ikke konkrete videoer automatisk.

### Egen milepæl: CD-omslag

Bruk tilgjengelige skannede PDF-omslag først. Vis forside på CD-kort, større
omslagsvisning og original PDF. Bekreft utgave/år visuelt før kobling; dokumenter
manglende omslag for senere skanning. Komplett skanning er ikke en forutsetning.
Ingen dato eller plass foran RTF/kurs er satt for denne milepælen.

### Utsatt: fullstendighet på tvers av menyformater

Alle sju publiserte CD-er er remontert skrivebeskyttet og har nye manifestfiler.
Dagens adaptere gir fremdeles 207 kildeposter. Dette er ikke en bekreftelse på
at alt program- og kursinnhold er representert.

- 1/2000, 4/2000, 9/2000 og 13/2000 har Director-menyer der dagens kvalifiserte
  profil bare dekker deler av innholdet.
- 1/2001 og 8/2001 har Tools-mapper uten Tools.dtx. Hovedinnholdet leses fra DTX.
- 15/2001 leses fra K.DTX og Tools.dtx, men heller ikke her er total dekning bevist.
- Direkte ISO-uttrekking løste tilgangsproblemene med DATA1.CAB på 15/2001.
  13/2000 ble lest fra tidligere dokumentert ISO-tre etter kontroll av ISO-hash.

Gjenoppta senere med eksplisitt meny-/fildekningsrapport, ikke med antall exe-filer
som mål på antall programmer. Ikke svekk kildekrav eller omskriv eksisterende
kuratering for å øke antallet poster. Lokale funn og manifestfiler er bevart under
`local-results/seven-disc-completeness` i Bootdisk-arbeidsområdet.

Retrotelleren er delegert til Claude i separat arbeidsordre og endrer ikke
rekkefølgen over. Automatisk kuratering/køintegrasjon er fortsatt uferdig og
skal ikke fremstilles som levert av disse innholdsmilepælene.

### 2026-09-25 — Verktøyhyllene på de seks øvrige CD-ene

162 ekstra kildeposter er observert med original omtale og menyillustrasjon. Samlet arkiv blir 369 poster. Se [rc7 og kildeavvik](release-1.2.0-rc7.md). Ved videre innlesing skal akseptansen eksplisitt avstemme hovedmeny, Tools.dtx eller Director-verktøyhyller, bilder og uavklarte seksjoner. En vellykket hovedmenyimport alene beviser ikke at CD-en er ferdig innlest. Full seksjonsavstemming og kursinnhold gjenstår som egne milepæler.

### Neste arbeidsøkt — RTF-dekning og tydelig kildemerking (avtalt 2026-09-25)

Prioriter dette før videre innholdsutvidelse. Dagens «Les originaltekst fra CD-en (RTF)» gjelder en separat, kildebundet RTF-fil. Menyomtalen er også originaltekst; fravær av feltet beviser derfor verken at omtalen mangler eller at CD-en ikke har en RTF-fil.

- Undersøk RTF-filer for de 162 nye verktøypostene fra seks CD-er. De har menyomtale, men ingen tilknyttede RTF-er i dagens innlesing. Bevar originalfil og lesbar tekst der koblingen til riktig post kan dokumenteres; ikke koble bare på lignende programnavn.
- Lag en dekningsrapport per CD som skiller mellom tilknyttet og lesbar RTF, samme tekst som menyomtalen, uleselig RTF, undersøkt uten funn og ennå ikke undersøkt eller tvetydig kobling. «Ikke funnet» må ikke fremstilles som «finnes ikke».
- Gjør ordlyden tydeligere i frontend, for eksempel «Les vedlagt tekstfil fra CD-en (RTF)». Menyomtalen og den vedlagte filen skal være forståelige som ulike kilder. Behold nedlasting og forklar hvorfor lesefeltet eventuelt ikke vises.
- Bevar menyomtalen ordrett, eksisterende kildekoblinger, kuratering og URL-er. Identisk tekst skal fortsatt ikke gjentas unødvendig; uleselig tekst skal fortsatt ha originalnedlasting når filen er tilgjengelig.

Ferdig når de seks CD-ene er undersøkt eller konkrete hindringer dokumentert, sikre RTF-koblinger er tatt gjennom Ingest → Catalog → Publish → Web, og visningen er kontrollert for alle tilfellene over. Bruk vanlig PR/test/merge-modell og lag ny pakke først når dette er gjennomført. Dette er planlagt arbeid, ikke en del av rc9.
