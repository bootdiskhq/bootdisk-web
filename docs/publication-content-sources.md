# Kilder for publikasjonsteksten

Teksten om Komputer for alle i `collections.json` er ny redaksjonell tekst skrevet for
Bootdisk. Den er ikke kopiert fra utgiveren. Originale programomtaler er en annen
innholdstype: de gjengis fortsatt fra kildedata uten omskriving.

Kontrollert 23. september 2026. «Lokal kilde» betyr bevarte data i Bootdisk-repoene, med
commit.

| Påstand i teksten | Kilde | Hva kilden faktisk støtter |
|---|---|---|
| K-CD-ene fulgte med bladet Komputer for alle. | Lokal kilde: omtalen av årsregisteret, K-CD 15/2001 `K26` (`bootdisk-catalog` `7d22183`, `data/curation/kcd15-2001.json`, `description:kfa-arsregister:unknown:nb-NO`): «Med Komputer for alles komplette årsregister kan du finne frem til samtlige artikler og programmer i bladet og på KCD-en.» Også ADR-0004/0005 i `bootdisk-ingest` `1099963` («the K-CD distributed with *Komputer for alle*»). | At K-CD 15/2001 hørte til bladet og at bladet hadde artikler og programmer. Ikke at alle utgaver hadde CD, eller når CD-serien begynte eller sluttet. |
| CD-ene er fra rundt årtusenskiftet. | Lokal kilde: medienavnene i den genererte samlingen (K-CD 1/2000 til K-CD 15/2001) i [five-disc-trial](five-disc-trial.md) og [release 1.2.0-rc3](release-1.2.0-rc3.md). | Årene på de bevarte CD-ene. Ikke hele seriens levetid. |
| CD-ene hadde spill, verktøy og kurs, blant annet Winamp, WinZip, Wordskolen, PowerPoint-skolen og Digitalkameraskolen. | Lokal kilde: Catalog `7d22183`, `kcd15-2001.json`: `software:winamp` (K37), `software:winzip` (K38), `software:wordskolen` (K32, «I dette kurset kan du lære hvordan du bruker programmet»), `software:powerpoint-skolen` (K27), `software:digitalkameraskolen` (K25), `content_kind` `game`/`application`/`course`. | Innholdet på K-CD 15/2001. Eksemplene er valgt fra én CD. |
| Noen spill kom som demoer, for eksempel MechCommander 2. | Lokal kilde: K-CD 15/2001 `K13`, `description:release:mechcommander:2:nb-NO`: «Her får du en stor demo av MechCommander 2.» | At denne posten var en demo. Ikke hvor mange programmer som var demoer, prøveversjoner eller fullversjoner. |
| Merkingen «K-CD 13/2000» er utgavenummer og år, ikke måned. | Arbeidsordren fra oppdragsgiver (23.09.2026) og medienavnene: nummer 13 og 15 finnes, så nummeret kan ikke være en måned. | Tolkningen av merkingen. Siden sier ikke hvor mange utgaver som kom per år. |
| Bootdisk er et uavhengig bevaringsprosjekt og ikke utgiverens nettsted. | Arbeidsordren og Bootdisks egne dokumenter (`bootdisk` README, ADR-0004). | Bootdisks egen rolle. |

Tolkninger som ikke er faktapåstander, og som er skrevet som det: at CD-ene gir «et
konkret bilde av hvordan PC-en ble tatt i bruk», og at en CD fra et blad er «et
øyeblikksbilde». De bygger på innholdet over, ikke på en ekstern kilde.

## Åpne spørsmål

- **Utgiverens side er ikke kontrollert.** Arbeidsordren oppgir
  <https://abonnement.komputer.no/brand/komputer-for-alle-no/> som startpunkt for dagens
  presentasjon. Nettverket i arbeidsmiljøet avviste forbindelsen (HTTP 403 fra proxyen),
  så siden er ikke lest. Teksten sier derfor ingenting om hvordan bladet lages eller
  distribueres i dag, bare at samlingen ikke beskriver det. Når siden er lest, kan én
  setning om dagens magasin legges til i `history` med lenken i `sources`.
- Startår, eventuelt nedleggelsesår, opplag, antall utgitte CD-er og om alle utgaver
  hadde CD er ikke undersøkt og står ikke i teksten.
- Utgiverens navn er utelatt fordi det ikke er kontrollert her.
- Om bladet fantes i flere land eller språkutgaver er ikke undersøkt.
