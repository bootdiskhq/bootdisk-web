# Automatisk kildekatalog

Catalog ADR 011 leverer `source_catalog` ved ordinær projeksjon. Nettsiden viser
«Oppgitt på CD-en» når denne vurderingen er dokumentert og produktidentiteten
fortsatt er pending. Eksisterende identifiserte og foreløpig identifiserte
programmer beholder statusen. Ingen produktidentitet eller versjon fabrikkeres.

Detaljsiden og arkivet bruker samme regel. Arkivets statusfilter har en egen
verdi `source_documented`; dokumenterte kildeposter skal ikke lenger telles i
«Venter på identifisering». Kildeavvik vises fortsatt på detaljsiden. Eldre data
uten feltet fungerer som før. Byggverktøyet kontrollerer samsvar mellom indeks,
detalj, kilde og tittel, slik at status ikke kan avvike mellom søk og detaljside.

## Oppdateringshistorikk v3

Synlig status er utvidet, derfor er kontrakten nå `bootdisk-public-updates-v3`
og projeksjonen `visible-v3`. Ny kode `source_documented` forklares som
«Navnet er dokumentert i CD-kilden». Dette er ikke `identified`.

Før publisering må historikken bygges på nytt fra de samme historiske datasettene
og faktiske publiseringstidspunktene. En v2-fil må ikke bare ommerkes til v3.
Nettsiden aksepterer kun v3. Den lokale forhåndsvisningen leveres uten historikk
og er ikke en opplastingspakke. Rc15 på nettet er uendret.

## Kontroll 2026-10-15

426 poster og 832 bilder kontrollert via lokal HTTP. De 194 pending-postene har
alle et dokumentert kildenavn; 10 har videre maskinoppgaver om filkobling. Det
betyr ikke at programfilene er identifisert. Eksisterende semantiske vedtak og
originalomtaler er uendret. Testpakken kjørte 322 tester: 214 bestått, 108 hoppet
over (nettleseravhengige kontroller m.m.); hoppet over er ikke bestått.
