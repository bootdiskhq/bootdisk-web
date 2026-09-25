# Bootdisk 1.2.0-rc6

Samlet levering av RTF-integrasjonen fra PR46/48 og den avslåtte besøkstelleren fra PR47. Menyomtaler og eksisterende kuratering beholdes. Lengre RTF-tekst kan åpnes på detaljsiden, og originalfilen kan lastes ned. Identisk tekst vises ikke to ganger; dokumenter som ikke kan tydes tilbys fortsatt som originalfil.

Datagrunnlaget er de samme sju CD-ene og 207 kildepostene som i rc5, inkludert 68 poster fra K-CD 15/2001 og de 29 Tools.dtx-postene. Pakken har 632 bildeobjekter og 102 unike originalfiler knyttet til 103 RTF-observasjoner. Én omtale (Freesaver MP3, K-CD 8/2001) har originalfil, men mangler lesbar tekst. Dette er ikke en ny fullstendighetsgaranti for CD-ene.

Besøkstelleren er avslått med endpoint: null. PHP-tjeneste, database, kuratering og automatiseringskø inngår ikke i den offentlige pakken. Aktivering av telleren behandles separat etter verifisering av webhotellet.

Bygges fra RTF-pilotens data og publiserte filer med --expected-entries 207. Før opplasting skal hele testsuiten, lokal HTTP-verifikasjon og bytekontroll av ZIP-filen være gjennomført. Ta vare på rc5 for tilbakeføring og last opp hele rc6 samlet.
