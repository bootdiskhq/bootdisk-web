# 1.2.0-rc7: verktøyposter fra seks flere CD-er

Arkivet utvides fra 207 til 369 kildeposter. De 162 nye postene kommer fra verktøyhyllene på K-CD 1/2000 (22), 4/2000 (25), 9/2000 (25), 13/2000 (28), 1/2001 (29) og 8/2001 (33). Hver ny post har original omtale og menyillustrasjon. Programidentitet og versjon er fortsatt ubekreftet.

Alle 207 eksisterende postfiler er byte-identiske med rc6, inkludert kildebelegg, kuratering og RTF-lenker. K-CD 15/2001 har fortsatt 68 poster. Nye mediumtotaler er henholdsvis 43, 41, 45, 44, 63 og 65. Samme program på flere CD-er forblir egne kildeposter.

To kildeavvik følger med: SuperDesk på 4/2000 viser til `Tools/SuperDesk/Setup.exe`, og Add/Remove på 1/2001 til `Tools/AddRemove/adrmpro2.exe`. Disse filhenvisningene finnes ikke i inventaret. Ingen erstatninger er gjettet.

## Bygging

`append-source-posts.py BASE_DATA supplements.json --output NEW_DATA` legger separate, kildebundne projeksjoner til en eksisterende samling. Konfigurasjonen bruker samme `media: [{id,data}]` som samlingsbyggeren. Bare kjente medier godtas. Eksisterende dokumenter kopieres uendret. Duplikate ruter, samme manifest på nytt, manglende omtale/bilde og kildekryssing avvises.

Mediets opprinnelige `source_manifest` bevares. `supplemental_manifests` er en eksplisitt liste over tillatte tillegg. Hvert dokument må fortsatt samsvare med sin egen kildenøkkel, beskrivelse og belegg. Opprinnelige bildekrav gjelder uendret for den opprinnelige kilden; hvert tilleggsmanifest har et separat krav om bilde for alle sine poster. Ingen eksisterende bildekrav svekkes.

## Kontroll

- Ingest: 173 tester, 137 bestått og 36 hoppet over. Den nye testen mot alle seks monterte CD-er ble kjørt og bestod.
- Catalog: 117 tester, 116 bestått og én hoppet over.
- Publish: 52 tester, alle bestått.
- Web: 266 tester, 170 bestått og 96 hoppet over (Playwright/PHP-avhengige kontroller i dette miljøet). Hoppede tester regnes ikke som beståtte.
- Samlet releasebygg: 369 poster, 816 unike refererte filer, én samling. Alle eksisterende postfiler sammenlignet byte for byte mot rc6.
- Direkte nettleserkontroll: arkivet viser 369/369; Sandra fra 1/2000 viser omtale og originalfigur; Add/Remove fra 1/2001 viser kildeavviket. Alle 16 nye 32-bit-bilder visuelt kontrollert samlet.

Dette er dekning av de identifiserte verktøyhyllene, ikke en generell garanti om alle filer, kurs og menyseksjoner på enhver CD. Publiseringspakken er statisk. Kurateringstjenesten og besøkstellerens database publiseres ikke av dette bygget.
