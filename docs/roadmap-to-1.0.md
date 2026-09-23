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
