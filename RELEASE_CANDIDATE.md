# Bootdisk Web 0.1.0-rc1

Denne kandidaten er den første komplette, statiske webpubliseringen av K-CD 15/2001.

## Godkjenningsport

- `data/index.json` skal inneholde nøyaktig 39 unike poster.
- Hver indekspost skal ha ett detaljdokument.
- Hver publisert filsti skal være relativ, ligge under `store/` og finnes i Publish-resultatet.
- Urefererte Publish-filer skal ikke følge med deploypakken.
- `K37` skal presenteres som Winamp 2.76 fra Catalog-data, ikke hardkodet HTML.
- Hele testpakken og en produksjonsbygging skal være grønne.

RC-en kan lastes opp direkte fra innholdet i `dist/bootdisk-web/`. Endelig `0.1.0` krever bare visuell kontroll på målserver og eventuelle blokkerende rettelser; nye funksjoner flyttes til neste versjon.

Produksjonsvalideringen er dokumentert i [`docs/rc-validation.md`](docs/rc-validation.md).
