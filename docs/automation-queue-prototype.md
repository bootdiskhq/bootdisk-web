# Automatisk førstegjennomgang: lesevisning (prototype)

Status: lokal prototype, 24. september 2026. Ikke integrert med Catalogs lokale tjeneste,
ikke i den offentlige releasen, ingen versjonsøkning. Arbeidsordre:
«Oversikt for automatisk kuratering» (Stian, 24.09.2026). Kontrakt:
[automation-queue-v1.md](automation-queue-v1.md), kopiert uendret.

## For Stian: slik bruker du den

Fra rotmappen i en egen checkout av `bootdisk-web`:

```sh
python3 -m http.server 8803 --bind 127.0.0.1
```

Åpne så én av disse:

| Adresse | Hva du ser |
| --- | --- |
| `http://127.0.0.1:8803/automation.html` | Valg av datakilde. Ingenting lastes før du velger. |
| `http://127.0.0.1:8803/automation.html?kilde=fil` | Velg én eller flere køfiler fra Catalogs førstegjennomgang (én fil per CD-manifest). Filene leses i nettleseren og endres ikke. En fil merket `fixture: true` vises med «Prøvedata»; ekte og merkede filer kan ikke åpnes sammen. |
| `http://127.0.0.1:8803/automation.html?kilde=prove` | **Prøvedata**: kontraktens eksempelfil med fire poster. |
| `http://127.0.0.1:8803/automation.html?kilde=syntetisk` | **Prøvedata**: 5 000 syntetiske poster på 125 CD-er. |

Port 8803 er et forslag; enhver ledig port virker. Ikke bruk 8772, 8794, 8795, 8797 eller 8798.

Øverst står fire innganger med tall. **Trenger din vurdering** er det eneste som er
oppgaver til deg. Trykk på den for å se bare de postene. **Undersøkes maskinelt** er
maskinens egen arbeidsliste, **Forslag klare** er forslag som ikke er godkjent, og
**Bevarte vurderinger** er menneskearbeid maskinen ikke rører. Linjen under tallene sier
om maskinen fortsatt har arbeid igjen, så en tom menneskekø aldri ser ut som en ferdig
katalog. «Fortsatt ukjent» nevner felt uten fastslått verdi, uten å be deg gjøre noe.

Klikk en post (eller Tab til den og trykk Enter) for å lese forslaget: verdi, begrunnelse,
regel og kildebelegg, med motstridende belegg side om side. Omtaler vises ordrett med
linjeskift. Hasher og JSON-pekere ligger under «Tekniske kildedetaljer». «Tilbake til
køen», Escape eller nettleserens tilbakeknapp tar deg tilbake til samme søk, filtre, side
og rad. Adressen kan deles; den åpner samme visning.

Siden har ingen godkjenn-, lagre- eller angreknapper, fordi kontrakten ikke har slike
operasjoner.

## Filer

| Fil | Rolle |
| --- | --- |
| `automation.html`, `automation.css` | Siden. |
| `automation-core.js` | Uten DOM: validering mot kontrakten, opptelling, søk, filtre, stabil sortering, sider, adressefelt. |
| `automation-adapter.js` | Lesende adapter med bare `loadQueue()`. Kilder: fil fra samme server (GET), fil valgt av brukeren. |
| `automation-sample.js` | Deterministiske syntetiske køer. Lastes bare på `?kilde=syntetisk`. |
| `automation.js` | Binder dette til siden. All kildetekst settes med `textContent`. |
| `tests/fixtures/automation-queue-v1.json` | Kontraktens eksempelfil, uendret (SHA-256 låst i test). |
| `docs/automation-queue-v1.md` | Kontraktkopi, uendret (SHA-256 låst i test). |

Siden bruker også `styles.css`, `accessibility.css` og `curator-labels.js` (visningsnavn som
«Spill» for `game`). Ingen ny kode i kuratorskjermen, oversikten, skriveadapteren, Catalog,
Ingest eller Publish. Oversikten har fått én lenke hit.

## Tolkninger av kontrakten

Dette er hvordan Web leser kontrakten der den ikke sier det helt eksplisitt. Ingen av dem
endrer kontrakten; de er beskrevet slik at Catalog kan bekrefte eller korrigere dem.

1. **Én fil er ett manifest.** `input.manifest` er ett manifest, så hver post må ha
   `key.manifest` lik den. En fil med poster fra et annet manifest avvises. Samlet visning
   over flere CD-er er flere filer lest side om side; samme manifest to ganger avvises.
2. **`requires_human` og `needs_review` hører sammen begge veier.** `requires_human: true`
   utenfor `needs_review` avvises (kontrakten), og `needs_review` med `false` avvises
   også (ordren: «needs_review, requires_human true»). Å gjette ville plassert posten feil.
3. **`summary` kontrolleres mot postene.** Avvik i ett tall avviser hele filen, i stedet for
   å vise tall som ikke stemmer med listen. `automatic_decisions` og `human_decisions` må
   være 0.
4. **Ukjent enumverdi avvises** (stage, status, feltnavn) med egen feilmelding, i stedet
   for å vises som noe kjent.
5. **Ukjent form på et belegg (`value`) vises som tekst** og merkes som uventet, slik
   kontrakten ber om, i stedet for å avvise filen.
6. **`fixture: true` er et eksplisitt prøvedatasignal.** Det står i kontraktens
   eksempelfil (sammen med `fixture_note`), men ikke i kontraktteksten. Web bevarer det
   gjennom validering og sammenslåing og merker liste, panel og banner ut fra det, også når
   filen åpnes med filvelgeren. Filnavnet brukes ikke. Mangler feltet, er filen ekte. En
   verdi som ikke er true/false avvises. Ekte og merkede filer valgt sammen avvises
   (`mixed_fixture`), så tellinger aldri blander oppdiktede og ekte poster. Den syntetiske
   generatoren merker sine filer på samme måte.
7. **Ikke alle fem felt kreves.** En post må ikke ha samme felt to ganger, men et manglende
   felt vises bare ikke. Kontrakten sier ikke om alle fem alltid er med.

## Kontraktsavvik og brukerbehov (til Catalog/Birk)

| # | Felt | Hva mangler | Brukerbehov |
| --- | --- | --- | --- |
| A1 | `fields[].proposed` for `preserve` | Er `null` i eksempelet. Den bevarte menneskeverdien følger ikke med. | Stian kan ikke se *hva* som er bevart uten å åpne kuratorskjermen. Web viser «Ikke fastslått» + «Den bevarte verdien følger ikke med i denne køen». Et lesefelt som `preserved_value` (eller en henvisning til claimen) ville løst det. |
| A2 | Snapshot per manifest | Ingen liste over snapshots eller samlet dokument for flere CD-er. | Oversikten skal være samlet. Web leser nå flere filer valgt for hånd. Tjenesten trenger en måte å liste snapshots på. |
| A3 | Menneskelig navn på CD | Bare `sha256:`-digest identifiserer CD-en. | «CD 2 av 125 (a931ac80)» er ikke lesbart. Et medienavn (for eksempel «K-CD 15/2001») per snapshot ville gjort radene forståelige. |
| A4 | `tasks[].code` | Bare maskinkode, ingen visningstekst. | Web viser `reason` og legger koden under teknisk detalj. Greit nå; en fast liste med koder ville gjort filtrering på oppgavetype mulig. |
| A6 | `fixture` / `fixture_note` | Brukt i eksempelfilen, ikke beskrevet i kontrakten. | Web trenger et eksplisitt signal for prøvedata. Kontrakten bør nevne feltene, og at ekte køfiler aldri har `fixture: true`. |
| A5 | Tidspunkt/alder | Bevisst utelatt (reproduserbart), men da kan ikke Web si hvor gammel kjøringen er. | Ved integrasjon bør tjenesten si når snapshotet ble laget, utenfor selve dokumentet. |

## Fremtidige Catalog-avhengigheter (ikke gjort)

Tjenesteintegrasjonen er **ikke gjennomført**. En fri statisk server er ikke Catalog-akseptanse.

- **STATIC-listen i `bootdisk_catalog/service.py`** (main `7d22183`) er lukket og har bare
  kuratorfilene. For at tjenesten skal kunne vise køen, må disse legges til, eksakt:
  `automation.html`, `automation.css`, `automation.js`, `automation-core.js`,
  `automation-adapter.js`, `curator-labels.js`. (`styles.css` og `accessibility.css` er
  der allerede.) `automation-sample.js` og fixturen skal *ikke* inn. Merk at tjenesten
  krever at alle STATIC-filer finnes ved oppstart, og at logoen og «Til
  kurateringsoversikten» peker på `overview.html`, som tjenesten heller ikke serverer.
- **En lesende operasjon** som gir snapshotet (eller listen over snapshots, se A2). Web
  dikter ikke opp noen endpoint. Når Catalog har en, kobles den inn ved å gi
  `createAutomationQueueAdapter({ read })` en `read`-funksjon som returnerer
  dokumentteksten, og en ny eksplisitt `kilde=`-verdi i `automation.js`. Feil derfra skal gi
  samme feilskjermer som nå, aldri prøvedata.
- **`needs_review` og `protected`** finnes bare i syntetiske prøvedata. Første
  backendleveranse lager bare `proposals` og `inspecting`.

## Kontrollmatrise

Kjørt på head `4f0a28d` av `feat/automation-queue` (første head `251fd18`), Chromium 141 (Playwright 1.63,
`CURATOR_CHROMIUM=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`), Node 22.22,
Python 3.11, Linux. «Feiler på feil kode» betyr at testen ble kjørt mot en bevisst
ødelagt variant og feilet (se «Mutasjonskontroll»).

| Krav | Forventet | Faktisk | Bevis |
| --- | --- | --- | --- |
| Fire stage-verdier vises med riktig betydning | Fire innganger med navn og forklaring | Som forventet | `test_contract_example_shows_every_stage_and_status_with_its_meaning`, skjermbilde 03 |
| Fem feltstatuser vises med riktig betydning | Alle fem i forklaring og rader | Som forventet | samme test; `test_the_contract_example_validates_and_its_summary_is_recounted` |
| Maskinoppgaver blir ikke menneskekrav | Menneskeantall bare fra `requires_human`; oppgaver merket «ikke oppgaver til deg» | Som forventet | `test_machine_tasks_are_never_counted_as_human_work`, `test_only_needs_review_can_ask_for_a_human` (M1) |
| Null menneskeoppgaver ≠ ferdig kuratert | Egen setning når maskinarbeid gjenstår | Som forventet | `test_no_human_work_is_not_presented_as_finished_while_the_machine_has_work` (M12) |
| Like K-ID-er på to CD-er er to poster | Egne paneler, egne belegg | Som forventet | `test_the_same_k_id_on_two_cds_is_two_entries_with_their_own_evidence`, `test_the_same_k_id_on_two_cds_opens_two_different_panels` (M9, M11) |
| Søk + filtre + side → åpne → tilbake | Samme søk, filtre, side, adresse og fokus på raden | Som forventet, også med Escape, nederste knapp, nettleserens tilbake og omlasting | `test_search_filters_and_page_survive_open_and_close_with_focus_back_on_the_row` (M6, M7) |
| Forslag, ukjent og bevart blir ikke godkjent i UI | «godkjent» bare som «ikke godkjent»; ingen godkjenn/lagre/angre | Som forventet | `test_the_panel_shows_proposal_reason_rule_and_evidence_and_nothing_is_approved`, `test_the_protected_entry_is_shown_as_preserved_not_as_unknown_work`, `test_the_queue_never_writes` |
| null vises som «Ikke fastslått» | Aldri «null», aldri sletting | Som forventet | samme paneltest (M2) |
| Tomt, laster, mangler, ugyldig JSON, ugyldig skjema, ukjent enum | Seks ulike skjermer; feil viser ingen tall og ingen prøvedata | Som forventet | `test_loading_is_its_own_state`, `test_missing_invalid_json_invalid_schema_and_unknown_values_are_different_errors`, `test_an_empty_run_says_so_…`, `test_missing_invalid_and_unknown_are_different_errors_and_never_sample_data` (M4, M8, M10), skjermbilde 04 |
| Summary stemmer med postene | Avvik avviser filen | Som forventet | `test_the_summary_must_add_up_and_decisions_stay_zero` (M5) |
| Prøvedata er merket uansett vei inn (P2 fra gjennomgang av `251fd18`) | Fil med `fixture: true` via filvelger gir banner, «Prøvedata ·» i tellingen og merknad i panelet; ekte filer gir ingen merking; blanding avvises | Som forventet | `test_a_marked_file_opened_through_the_file_picker_is_labelled_as_sample_data`, `test_real_files_opened_through_the_file_picker_are_not_labelled_as_sample_data`, `test_mixing_real_and_sample_files_is_refused_without_counts`, `test_sample_chosen_in_the_address_bar_is_marked_in_list_and_panel`, `test_an_explicit_fixture_marking_survives_validation_and_combination`, `test_sample_and_real_snapshots_are_never_counted_together`. Fem av seks feiler på `251fd18`; den sjette (ekte filer umerket) er en vakt mot overmerking og består på begge. |
| Ingen prøvedata uten eksplisitt valg | Uten `kilde` lastes ingenting | Som forventet | `test_without_a_chosen_source_nothing_is_loaded_and_no_sample_is_shown`, `test_sample_data_is_loaded_only_when_chosen`, skjermbilde 05 |
| HTML-lignende kildetekst vises bokstavelig | Ingen `<b>`/`<script>` i DOM; tekst lik kilden | Som forventet | `test_the_original_description_keeps_its_spaces_and_line_breaks_and_markup_stays_text` (M3), `test_source_text_is_never_parsed_as_html` |
| Originalomtale beholder linjeskift og mellomrom | `textContent` lik kilden, `white-space: pre-wrap` | Som forventet | samme test (M13) |
| Ingen skriving | Bare GET; `localStorage` tom; kilde uendret | Som forventet | alle nettlesertester sjekker metode og `localStorage`; `test_the_adapter_only_reads` |
| Stabil sortering | Samme rekkefølge uansett inndata | Som forventet | `test_the_order_is_stable_and_independent_of_input_order` |
| 5 000 poster, sidevisning | 25 rader i DOM, ingen paneler bygget før åpning | Som forventet | `test_five_thousand_entries_build_one_page_and_respond_quickly` |
| Tastatur uten fokusfelle | Enter åpner, Escape lukker, Tab kommer ut av panelet | Som forventet | `test_the_panel_does_not_trap_the_keyboard` |
| Synlig fokus og leserekkefølge | Omriss på fokus; overskrifter i skjermrekkefølge | Som forventet | `test_focus_is_visible_and_reading_order_follows_the_screen` |
| 360 px | Ingen vannrett rulling i liste, panel og lange belegg | Som forventet | `test_360_px_has_no_horizontal_scroll_in_the_list_or_the_panel`, skjermbilde 06, 07 |
| Gammel oversikt og kuratorflyt | Uendret | Alle eksisterende tester grønne (inkl. nettleser og Catalog-allowlist) | full kjøring nedenfor |
| Offentlig pakke | Nye filer 404 over HTTP; forside, samling og gamle programlenker virker | Som forventet | `test_http_verifier_passes_…` (verifiseringen sjekker nå også køfilene), `test_http_verifier_refuses_a_release_that_serves_the_automation_queue`, `test_release_contains_the_public_pages_and_nothing_private`, `test_nothing_of_the_queue_is_in_the_public_release` |

### Mutasjonskontroll

Hver variant ble lagt inn, den relevante testen kjørt, og koden satt tilbake. Alle 13 feilet:

M1 fjernet koblingen `requires_human`/`needs_review` · M2 null vist som tekst · M3 `innerHTML`
for kildetekst · M4 fallback til fixture ved feil · M5 summary ikke kontrollert · M6 fokus ikke
tilbake på raden · M7 åpning uten historikk · M8 `key.manifest` ikke kontrollert · M9 alle
CD-er med samme nummer · M10 ukjent enum godtatt · M11 oppslag på K-ID alene · M12 tom
menneskekø kalt ferdig · M13 linjeskift slått sammen i CSS.

### Testtall

| Kjøring | Funnet | Kjørt | Bestått | Feilet | Hoppet over |
| --- | --- | --- | --- | --- | --- |
| Main `ae12d52`, Chromium + Catalog-checkout | 165 | 165 | 165 | 0 | 0 |
| `251fd18`, Chromium + Catalog-checkout | 199 | 199 | 199 | 0 | 0 |
| `251fd18`, som CI (uten Playwright og Catalog) | 199 | 136 | 136 | 0 | 63 |
| `4f0a28d`, Chromium + Catalog-checkout | 205 | 205 | 205 | 0 | 0 |
| `4f0a28d`, uten Playwright, med Catalog-checkout | 205 | 139 | 139 | 0 | 66 |
| `4f0a28d`, som CI (uten Playwright og Catalog) | 205 | 138 | 138 | 0 | 67 |

Nye tester: 20 i `tests/test_automation.py`, 19 i `tests/test_automation_browser.py`, 1 i
`tests/test_publication.py`. De hoppede er nettlesertester og (uten Catalog) allowlist-
sammenligningen; hoppet er ikke bestått.

### Målt respons, 5 000 poster

Chromium 141 headless, Linux-container, lokal `http.server`. Én kjøring:

| Handling | Tid |
| --- | --- |
| Sidelast til første rad, inkludert generering og validering av 125 filer | 375–542 ms |
| Søk «kvasar» (filtrering + ny side med 25 rader) | 14,6 ms |
| Søk «K17» | 12,7 ms |
| Søk «polarsjakk» | 12,1 ms |
| Tømme søket | 24,4 ms |
| Åpne lesepanel | 12–16 ms |

Søk er ikke forsinket (ingen debounce); hvert tastetrykk filtrerer hele køen. I Node:
validering og sammenslåing av 5 000 poster ca. 190 ms, verste søk under 10 ms.

## Kjente avvik

- `?kilde=fil` må velges på nytt etter omlasting; filen lagres ikke noe sted.
- Samlet visning over flere CD-er forutsetter at filene velges sammen (A2).
- Tjenesteintegrasjonen er ikke gjort (se Catalog-avhengigheter).
- Nettlesertestene hoppes over på CI, som mangler Playwright.
