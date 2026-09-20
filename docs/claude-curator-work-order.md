# Arbeidsordre til Claude: lokal kuratering i Bootdisk 1.2

Du skal implementere første frontend-leveranse for en rask kurateringsflyt.
Stian skal kunne undersøke kildebelegg, rette eller godkjenne en oppføring og gå
videre uten hjelp fra en agent, terminal eller håndredigering av JSON.

**Leveransen din er en fungerende lokal kurateringsskjerm med fixture-adapter,
meningsfulle tester og en PR. Backend og ekte kataloglagring bygges parallelt av
Codex. Ikke presenter fixture-lagring som ekte kataloglagring.**

## 1. Arbeidssted og dokumenter du skal lese

Arbeidsområde: `/Users/stian/Bootdisk`. Endre kun `bootdisk-web`.
Arbeid på en egen gren, foreslått navn `feat/curator-ui-v1`, fra oppdatert `main`.
Hvis noen allerede bruker grenen eller arbeidsmappen har endringer, opprett en
separat checkout/worktree; ikke flytt, overskriv eller nullstill andres arbeid.

Les disse filene i naborepoet `bootdisk-catalog` før implementering:

- `docs/adr-004-local-curator-boundary.md`
- `docs/adr-005-review-state-and-decisions.md`
- `docs/curator-contract-v1.md`
- `docs/curator-fixtures-v1.json`
- `docs/curation-next-step.md`
- `docs/kcd15-2001-remaining-work.md`

Les også `README.md`, `docs/frontend-data-contract.md`,
`docs/url-contract.md`, `scripts/build-release.py` og `tests/test_contract.py`
i webrepoet. Catalog-dokumentene er autoritative for den nye adapteren; den
publiserte frontend-kontrakten gjelder fortsatt det eksisterende arkivet.

Hvis naborepoet ikke er tilgjengelig, hent dokumentene fra
[bootdisk-catalog](https://github.com/bootdiskhq/bootdisk-catalog/tree/main/docs).
Noter Catalog-commit og kontraktversjon du bygger mot i PR-en. Ikke lag en egen
konkurrerende datakontrakt. Rapporter et konkret kontraktproblem med et forslag;
fortsett uavhengige frontend-deler mens det avklares.

## 2. Din første leveranse

Lag en egen lokal side, for eksempel `curate.html`, med egne frontend-filer og
en utskiftbar asynkron adapter. Følg eksisterende enkel HTML/CSS/JavaScript-stil;
ikke start en rammeverksmigrering. Del opp i filer som gjør adapteren testbar.

Skjermen skal ha:

- En kø med filtrene ventende, utsatt, åpne felt og alle. Vis hvilken oppføring
  som er valgt, antall i filteret og forskjellen på gjennomgått og avklart.
- Original tittel og beskrivelse, pakkens filer og lesbare kildeobservasjoner.
  Behold kilde og tolkning som to synlige deler. Tekst fra media vises som tekst,
  aldri som HTML, kjørbar kode eller ukontrollerte fil-lenker.
- Redigerbare felt for identitet/navn, versjon, innholdstype, distribusjon og norsk
  beskrivelse. Vis akseptert verdi, forslag og kildebelegg forståelig. En retting
  må kunne få begrunnelse og knyttes til tilgjengelig kildebelegg.
- «Godkjenn og neste» når kladden er uendret, «Lagre og neste» etter retting,
  «Hopp over» med begrunnelse, og «Angre» når adapteren tillater det. Begge de
  første knappene godkjenner eksplisitt; automatisk lagring lagrer bare kladd.
- Synlig tilstand for endringer som ikke er lagret, pågående lagring, lagret kladd
  og feil. Behold innholdet ved feil. Ikke gå videre før adapteren bekrefter
  godkjenning eller utsettelse. Vis en tydelig avslutning når køen er tom.
- Gjenopptakelse av kladd og sist besøkte oppføring. Fixture-adapteren simulerer
  dette med versjonert nettleserlagring og en eksplisitt tilbakestilling.

Bruk norsk bokmål i grensesnittet og eksisterende visuell identitet. Førstevisningen
skal prioritere beslutningen; lange fil-/evidenslister kan foldes ut. Lag en ryddig
smal visning også. Bruk synlige etiketter, semantiske kontroller, tastaturfokus,
statusmeldinger som hjelpemidler oppfatter, og markører som ikke bare bygger på farge.

## 3. Hurtig for et menneske

En tilstrekkelig dokumentert, ferdig utfylt oppføring skal kunne godkjennes og
åpne neste med én handling. Ikke legg en generell bekreftelsesdialog foran hver
normal godkjenning. En faktisk konflikt trenger derimot bevisst håndtering.

Velg og dokumenter et lite sett hurtigtaster med synlige hint. De skal ikke
utløses mens brukeren skriver i input, textarea, select eller contenteditable,
ved tekstkomposisjon eller på gjentatte keydown-hendelser. Ikke overstyr vanlige
nettlesersnarveier. Flytt fokus forutsigbart til den nye oppføringen og behold
fokus/innhold ved feil. Tastatur og knapper skal bruke samme handlingskode.

Ikke autogodkjenn foreløpige forslag. Ukjent versjon/distribusjon kan beholdes med
begrunnelse. At en oppføring er gjennomgått betyr ikke at alle felt er avklart.
En manglende fil eller vanskelig installasjonspakke skal ikke sperre resten av køen.

## 4. Adapter og prøvedata

Implementer alle metodene i kontrakten: `getQueue`, `getEntry`, `saveDraft`,
`defer`, `approve`, `undo`, `setResume`. UI-koden skal ikke kjenne lagringsformatet.
Bruk en tydelig synlig «Prøvedata – endrer ikke katalogen»-markering. Ingen
nettverksfeil skal utløse en skjult overgang fra virkelig adapter til prøvedata.

Kopier fixture-dokumentet fra Catalog til en avgrenset test-/fixture-mappe i
webrepoet, med original commit og kilde i en README. Behold filen uendret som
utgangspunkt; simuler feil og videre tilstander i adapteren eller testene.
Det skal ikke være nødvendig å ha CD-en montert eller å installere gamle programmer.

K23 CPU-Z gir et konkret versjonstilfelle: 1.10 er produktversjon, mens PE-feltet
1.0.0.1 ikke er det. K4 Blockout gir en foreløpig identitet og udekodet pakke.
Begge har allerede katalogtolkninger, men skal kunne gjennomgås på nytt.
Test dessuten manglende media, lesefeil, konflikt og lagringsfeil som eksplisitt
simulerte tilstander. Ikke presenter simulerte observasjoner som ekte kildefunn.

Følg revisjons-/operasjonsreglene også i fixture-adapteren. En gjentatt operasjon
med samme ID og innhold skal ikke gi dobbelt godkjenning. En gammel revisjon skal
gi konflikt. Vis lokal kladd sammen med gjeldende servertilstand ved konflikt og
la brukeren velge å laste serverversjonen eller eksplisitt bygge en ny kladd;
ingen stille overskriving. Tøm ventende autosave før godkjenning/utsettelse,
og sørg for at sene svar ikke overskriver nyere inntasting.

## 5. Avgrensning og samarbeid

Codex eier den virkelige lokale tjenesten, katalogendringer, inspector/utpakking,
identitetsvalidering, semantiske ID-er, historikk på disk og integrasjon. Du skal
ikke endre disse eller finne på autoritative katalogverdier. En ukjent identitet
kan sendes som navneforslag med null-ID etter kontrakten.

La eksisterende arkiv, stabile lenker, genererte data og publiseringsløype fungere.
Ikke legg kurator, fixture-data eller skrivemuligheter i den offentlige
release-allowlisten. Ikke importer neste CD, kjør historiske installatører, bump
releaseversjon, deploy eller merge selv. Lever PR for felles gjennomgang.

Det er lov å løse vanlige layout- og implementeringsvalg selv. Oppgi produkt- og
kontraktavvik eksplisitt i PR-en; ikke løs dem ved å endre Catalog-dokumentene.

## 6. Tester og akseptanse for PR-en

Kjør eksisterende tester (`python -m unittest discover -s tests -v`) med Python
3.10+ og Node tilgjengelig for JavaScript-testene. Bruk den etablerte teststilen,
utvid bare testverktøyene hvis det trengs for meningsfull nettleseratferd.

Dekk minst følgende observerbare forløp:

1. Åpne K23, les versjonsbelegg, godkjenn, og se neste oppføring først etter svar.
2. Rett et felt, lagre kladd, last siden på nytt og få rettingen tilbake uten at
   den regnes som godkjent. Godkjenn deretter med siste revisjon.
3. Hopp over K4 med begrunnelse, finn den igjen under utsatt og behold kladden.
4. Angre en godkjenning; tidligere verdier gjenopprettes, historikken beholdes,
   og oppføringen blir ventende. En eksisterende kladd skal ikke slettes.
5. Feilet autosave/godkjenning beholder inndata og stopper neste-handlingen.
   Dobbelklikk og timeout/retry gir ikke to beslutninger.
6. Konflikt mellom to revisjoner gir forståelig løsning uten tapt lokal tekst.
7. Hurtigtaster fungerer utenfor skrivefelt, men ikke under skriving/komposisjon.
8. Uavklarte felt og utilgjengelig kilde er synlige; øvrige oppføringer kan behandles.
9. Sene autosave-svar kan ikke markere nyere, ulagrede endringer som lagret.
10. Offentlig release-allowlist inkluderer ikke kurator eller fixture-filer.

Gjør også en manuell nettlesergjennomgang med tastatur, vanlig bredde og smal
visning. Testene skal verifisere atferd, ikke bare at funksjonsnavn finnes i teksten.
Dokumenter om noe ikke kunne kjøres; ikke rapporter det som bestått.

## 7. Levering tilbake til Stian og Codex

Lever en PR mot `bootdisk-web/main` med:

- Kort problem/beskrivelse og konkret hva som nå fungerer.
- Eksakt kommando og lokal URL for å starte prøvevisningen.
- Skjermbilder av normal skjerm, uavklart pakke og en feil-/konflikttilstand.
- Tester og manuelle kontroller du faktisk har kjørt, med resultat.
- Catalog-commit/kontraktversjon, endrede filer og eventuelle avvik.
- En tydelig liste over hva som fortsatt venter på den virkelige tjenesten.

Første frontend-PR er ferdig når flyten fungerer mot fixture-adapteren og kan
kobles til den virkelige adapteren uten å skrive om skjermen. Bootdisk 1.2 er først
ferdig etter integrasjon og Stians selvstendige prøve av ti ulike oppføringer.
