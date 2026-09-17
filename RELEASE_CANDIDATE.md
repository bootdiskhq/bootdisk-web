# Bootdisk Web 1.0.0-rc1

Denne kandidaten fryser den første stabile offentlige kontrakten for Bootdisk Web. K-CD 15/2001 er det komplette referansemediet: 39 kildeposter og 136 publiserte filer kan bygges på nytt fra bevarte data uten håndredigering av frontendkode.

## Godkjenningsport

- `data/index.json` skal inneholde nøyaktig 39 unike poster.
- Hver indekspost skal ha ett detaljdokument.
- Frontend-kontrakten skal validere kildekontekst, kurateringsstatus og ressursbindinger.
- Hver publisert filsti skal være relativ, ligge under `store/`, ha SHA-256 og finnes i Publish-resultatet.
- Urefererte Publish-filer skal ikke følge med deploypakken.
- `K37` skal presenteres som Winamp 2.76 fra Catalog-data, ikke hardkodet HTML.
- K-ID skal være den stabile URL-identiteten; menneskelige navn kommer fra Catalog.
- Sitemap skal inneholde arkivoversikten og nøyaktig én URL per kildepost.
- Release-rapporten skal identifisere frontend-projeksjonen og inngangsmanifestene med SHA-256.
- Hele testpakken, releasebygget og den lokale HTTP-verifikasjonen skal være grønne.
- Kandidaten skal deretter bestå produksjonsverifikasjon og visuell kontroll på mobil og desktop.

RC-en lastes opp fra den deterministiske ZIP-artefakten. Endelig `1.0.0` skal promoteres fra en godkjent kandidat uten nye funksjoner; bare blokkerende rettelser tillates mellom RC og stabil utgivelse.

Kandidatvalideringen er dokumentert i [`docs/1.0.0-rc1-validation.md`](docs/1.0.0-rc1-validation.md).
