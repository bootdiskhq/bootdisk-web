# Kontrollmatrise for kuratorskjermene

Reglene kuratorflaten må holde, hvilken kode som bærer hver regel, hvilken test som
kontrollerer den, og hva resultatet faktisk ble. Matrisen er ment å gjenbrukes: en
avgrenset akseptansekontroll skal kunne gjøres mot den, i stedet for at grunnleggende feil
oppdages på nytt i hver runde.

**Når du endrer kuratorkoden:** nye domeneobjekter og nye skrive- eller navigasjonsveier
utvider matrisen. En ny lenke, knapp eller hurtigtast som kan nå en skriveoperasjon skal ha
en rad her før den regnes som ferdig.

Tre ting testene *ikke* gjør, sagt tydelig: de venter aldri på klokken (hvert forløp holder
adaptersvaret og slipper det selv), de teller ikke grønne tester som dekning, og en regel
uten rad her er ikke kontrollert.

Kjør alt:

```sh
python -m unittest discover -s tests
```

Radene under viser testnavnet; filen står i parentes første gang den brukes.

## A. Navigasjon og skriving

| Regel | Kode | Test | Resultat |
| --- | --- | --- | --- |
| Siden forlates først når siste kladd er bekreftet lagret | `leave()` i `curate-core.js` | `test_typing_then_returning_before_the_autosave_starts_saves_the_text` (`tests/test_navigation_gate.py`) | Grønn. Teksten ligger i kladden hos adapteren før returen skjer. |
| Vilkårene gjelder når navigasjonen faktisk skjer, ikke bare før en venting | `leave()` tar porten for hele returen; navigasjonen kjøres inne i porten | `test_a_decision_started_while_the_return_waits_cannot_slip_past_the_gate` | Grønn. Falt på koden før rettingen (`leave allowed: true busy: true`). |
| En gitt retur låser skjermen; ingenting starter på en side som er på vei ut | `leave()` åpner ikke porten igjen etter et ja | `test_a_granted_return_keeps_the_gate_shut` | Grønn. |
| Retur, godkjenning, utsettelse, angre og intern navigasjon starter ikke konkurrerende forløp | `state.leaving` sperrer `decide`, `select`, `setFilter` og `retry` | `test_defer_undo_and_internal_navigation_are_refused_while_the_return_waits` | Grønn. Sperring, ikke serialisering — se begrunnelsen under. |
| Retur under en pågående beslutning stoppes | `leave()` svarer nei på `state.busy` | `test_a_return_during_a_running_decision_is_refused_and_the_decision_finishes` | Grønn. Falt på koden før rettingen. |
| Nye inndata mens et eldre lagringssvar venter går ikke tapt | `flush()` og `save()`s kvitteringssjekk | `test_text_typed_while_the_return_waits_is_never_lost` | Grønn. Teksten lagres, eller returen stoppes med teksten i behold. |
| Et gammelt svar gjør aldri nyere tekst «lagret» | `save()` sammenligner kvitteringens kladd med gjeldende | `test_an_old_answer_arriving_after_newer_text_never_marks_it_saved`, `test_a_late_autosave_receipt_cannot_mark_newer_input_as_saved` | Grønne. Status blir `dirty`, ikke `saved`. |
| Dobbeltklikk gir verken doble beslutninger eller kryssende navigasjon | `leaving`-memoet og `state.busy` | `test_double_clicking_return_or_approve_produces_one_of_each` | Grønn. Falt på koden før rettingen. |
| Retur kan lagre kladd, men godkjenner aldri som bivirkning | `leave()` kaller bare `flush()` | `test_typing_then_returning_before_the_autosave_starts_saves_the_text` | Grønn. Køtilstanden er uendret etter retur. |
| En feilet beslutning forblir synlig; ingen skjult retur | `applyError`, `state.pendingRetry` | `test_a_failed_decision_stays_visible_and_blocks_the_return` | Grønn. |
| Feil og konflikt beholder teksten og gir en vei videre | `applyError`, `resolveConflict` | `test_a_failed_save_and_a_revision_conflict_both_stop_the_return_and_keep_the_text` | Grønn for begge feilene. |
| Returlenken i nettleseren følger samme regel som controlleren | `bindReturnLink` i `curate.js` | `test_returning_right_after_typing_saves_the_text_as_a_draft`, `test_a_failed_save_stops_the_return_and_keeps_the_text`, `test_a_revision_conflict_stops_the_return_and_keeps_the_text`, `test_returning_during_a_running_decision_neither_navigates_nor_decides_twice` (`tests/test_overview_browser.py`) | Grønne i Chromium. |
| Tastaturaktivering av lenken går gjennom samme port | `bindReturnLink` lytter på `click`, som Enter utløser | `test_the_return_link_runs_the_same_gate_from_the_keyboard` | Grønn. |
| Modifisert klikk beholder vanlig nettleseroppførsel uten å forlate siden | `bindReturnLink` slipper gjennom modifiserte klikk | `test_a_modified_click_keeps_the_page_and_its_draft_where_they_are` | Grønn. Siden og teksten står. |

**Hvorfor sperring er trygt.** Ordren tillater sperring eller serialisering. Valget er
sperring: mens en retur venter på siste skriving, avvises nye beslutninger og intern
navigasjon i stedet for å legges i kø. Det er trygt fordi vinduet er kort og avgrenset av
én skriving, fordi controlleren allerede eier rekkefølgen på skrivinger, og fordi et avvist
knappetrykk er synlig for kuratoren — knappene er samtidig deaktivert — mens en serialisert
beslutning ville kjørt etter at kuratoren allerede har bedt om å forlate siden. Skriving i
feltene er bevisst *ikke* sperret: teksten blir enten lagret av flush-en eller stopper
returen, og ingen av delene mister tegn.

## B. En påstand er mer enn tekstverdien

Påstandens redigerbare innhold er `value`, `assessment`, `reason` og `evidence_ids`.

| Regel | Kode | Test | Resultat |
| --- | --- | --- | --- |
| Lik verdi med annen vurdering er en endring | `overviewClaimChange()` i `overview-adapter.js` | `test_each_editable_part_of_a_claim_counts_as_draft_work_on_its_own` (`tests/test_overview.py`) | Grønn. |
| Lik verdi med annen begrunnelse er en endring | samme | samme test | Grønn. |
| Lik verdi med annet kildevalg er en endring | `overviewSameEvidence()` | `test_source_selection_is_compared_as_a_set_and_explained_in_the_row` | Grønn. Falt på koden før rettingen. |
| Kilde-ID-er sammenlignes som et sett | `overviewEvidenceSet()` | samme test | Grønn. Annen rekkefølge og gjentatt ID gir ingen falsk endring. |
| Tilføying, fjerning og bytte behandles hver for seg og forklares i raden | `evidence_added`/`evidence_removed`, `evidenceNote()` i `overview.js` | samme test, og `test_changing_only_the_source_selection_shows_up_as_draft_work_in_the_overview` | Grønne. Raden sier «lagt til / fjernet / byttet kildebelegg». |
| Sammensatte verdier sammenlignes semantisk | `overviewCanonical()`, samme praksis som `curatorCanonical()` | `test_composite_values_are_compared_by_meaning_not_by_property_order` | Grønn. Falt på koden før rettingen. |
| Arbeidsbehov og sist godkjent verdi er separate begreper | `open_fields` fra kladden, `accepted_open_fields` fra godkjent tilstand | `test_a_draft_assessment_is_work_even_when_the_value_is_unchanged` | Grønn. Belagt → uavklart og uavklart → belagt begge dekket. |
| Gjennomgått er ikke fullstendig avklart | `fully_resolved` krever fire tomme lister | `test_decisions_update_the_row_from_what_the_adapter_answers` | Grønn. |
| Godkjenning, angre og gjenåpning oppdaterer statusene fra adapterens svar | `overviewApplyRecord`, `refreshEntry` | `test_approve_undo_and_reopen_keep_the_work_need_and_the_approved_state_apart`, `test_a_changed_source_selection_survives_saving_approval_and_undo` | Grønne. |
| Originalteksten på CD-omtalen er fortsatt skrivebeskyttet | `originalDescriptionError()` i `curate-adapter.js`, read-only-feltet i `curate.js` | `test_a_restored_cd_description_cannot_be_rewritten_through_the_adapter` (`tests/test_curator.py`), `test_a_restored_cd_description_stays_read_only_through_a_draft_and_a_return` | Grønne. Falt på koden før rettingen: fixture-laget slapp en omskrevet original gjennom. |
| Kildealiasene fra duplikatrettingen vises fortsatt riktig | `curate.js` | `tests/test_evidence_display.py` | Grønn. |

## C. Lagring, identitet og svar

| Regel | Kode | Test | Resultat |
| --- | --- | --- | --- |
| Kildeidentitet er manifest og entry sammen | `curatorKeyId()` i `curate-core.js` | `test_a_receipt_is_bound_to_manifest_and_entry_together` | Grønn. Falt på koden før rettingen. |
| Hvert svar tilhører oppføringen og operasjonen som sendte forespørselen | `submit()`s `sentFor` | samme test, og `test_a_late_save_receipt_never_lands_on_another_entry` (`tests/test_curator.py`) | Grønne. |
| Gjenforsøk bruker samme operasjons-ID og uendret forespørsel | `submit()` bygger forespørselen én gang | `test_retry_resends_the_original_operation_for_every_mutation` | Grønn. |
| Sene svar overstyrer ikke nyere tilstand | `save()`s kvitteringssjekk, `write()`-serialiseringen | `test_an_old_answer_arriving_after_newer_text_never_marks_it_saved` | Grønn. |
| Oversikten viser adapterens bekreftede tilstand, ikke et knappetrykk | `refreshRow()` i `overview-core.js` leser `getEntry` | `test_decisions_update_the_row_from_what_the_adapter_answers` | Grønn. |
| Felt skjermen leser faller ikke ut av adapterens svar | `entryDocument()` i `curate-adapter.js` | `test_a_deferred_entry_carries_its_reason_back_to_the_screen` | Grønn. Falt på koden før rettingen: «Utsatt: …» kunne aldri vises i prøvedata. |
| Et tregt gammelt søkeresultat erstatter ikke et nyere | lastenummer i `overview-core.js` | `test_a_slow_old_search_result_cannot_replace_a_newer_one` | Grønn. |

## D. Integrasjon og grenser

| Regel | Kode | Test | Resultat |
| --- | --- | --- | --- |
| Ekte lokal kuratering starter og lagrer gjennom Catalogs tjeneste | `curate.html` holder seg til tjenestens lukkede allowlist | `test_the_detail_screen_only_loads_files_the_local_service_serves`, `test_the_pinned_allowlist_matches_the_catalog_service_when_it_is_available`, og kjøringen mot den ekte tjenesten | Grønne. Se [akseptansen](curator-overview-prototype.md#akseptanse-mot-den-ekte-lokale-tjenesten). |
| Prototypeavhengigheter lekker ikke inn i lokal oppstart | `loadPrototypeScripts()` kjører bare på `?dataset=sample` | `test_the_detail_screen_only_loads_files_the_local_service_serves` | Grønn. Ingen 404 mot tjenesten. |
| Ingen automatisk overgang til prøvedata ved feil i ekte modus | `createLiveAdapter()` | `tests/test_live_adapter.py` | Grønn. |
| De to kopiene av kuratorvokabularet er identiske | `curate.js` og `curator-labels.js` | `test_the_shared_curator_vocabulary_is_identical_in_both_copies` | Grønn. |
| Kildeinnhold rendres som tekst | `overview.js`, `curate.js` | `test_overview_rendering_builds_nodes_instead_of_markup` | Grønn. |
| Offentlig release utelater kurator og syntetiske data | `scripts/build-release.py` | `test_public_release_excludes_the_overview_and_its_sample_data` | Grønn. |
| Tester bruker aldri et ekte arbeidsområde | testene lager sitt eget | akseptansekjøringen bruker en engangsmappe og egen port | Grønn. |

## Kjente hull

- **Merkelenken øverst på siden** (`.brand`) er en vanlig lenke og går utenom porten, som
  den alltid har gjort. En ulagret kladd kan gå tapt ved å klikke den. Ordren forbyr en
  generell bekreftelsesdialog foran vellykket navigasjon, så den er ikke lagt inn; en
  eventuell retting hører hjemme i et eget forløp for «forlat siden helt».
- **Nettleserkontrollene krever Chromium** og hoppes over uten Playwright, som på CI.
  Hoppet test er ikke bestått test.
- **Sammenligningen mot Catalogs allowlist krever en Catalog-checkout**
  (`BOOTDISK_CATALOG_ROOT`). Uten den hopper den ene testen over, mens den fastspikrede
  kopien fortsatt kontrolleres.
