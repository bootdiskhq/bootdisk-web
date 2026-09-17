# Bootdisk Web

Statisk presentasjonslag for det bevarte Bootdisk-arkivet. Catalog eier identitet og evidens; Publish eier webklare filer. Dette repoet eier bare den gjenoppbyggbare visningen.

## Lokal test

```sh
python -m unittest discover -s tests -v
```

## Bygg en release

Bygg først frontend-data fra de autoritative Catalog- og Publish-resultatene:

```sh
python scripts/build-preview.py CATALOG_ROOT INGEST_MANIFEST PUBLISH_ROOT/publish-manifest.json --output build/data
```

Lag så den lukkede deploymappen. Porten avviser færre/flere enn 39 poster, manglende detaljdokumenter, utrygge stier og manglende bilder:

```sh
python scripts/build-release.py build/data PUBLISH_ROOT --output dist/bootdisk-web --expected-entries 39
```

Innholdet i `dist/bootdisk-web/` kan lastes direkte opp til webroten. Kjør en lokal kontroll med:

```sh
python -m http.server --directory dist/bootdisk-web 8000
```

Åpne `http://localhost:8000/`. Roten sender nettleseren til arkivoversikten; detaljsider bruker stabile lenker som `index.html?entry=K37`.

## Bygg komplett releaseartefakt

Én kommando kan bygge frontend-data, lukket deploymappe, deterministisk ZIP og en maskinlesbar JSON-rapport:

```sh
PYTHONPATH=/path/to/bootdisk-catalog python scripts/build-release-artifact.py PUBLISH_ROOT \
  --catalog-root CATALOG_ROOT \
  --ingest-manifest INGEST_MANIFEST \
  --expected-entries 39
```

Rapporten lagrer versjon, input-hasher, antall poster, antall publiserte filer og ZIP-ens SHA-256.

Etter opplasting verifiseres hele den offentlige kjeden med:

```sh
python scripts/verify-deployment.py https://bootdisk.no/ --expected-entries 39
```

Se [`docs/domeneshop-deploy.md`](docs/domeneshop-deploy.md) for deploy- og rollback-prosedyren.

Den stabile 1.0-kontrakten mellom de genererte dataene og presentasjonslaget er dokumentert i [`docs/frontend-data-contract.md`](docs/frontend-data-contract.md). Den kan kontrolleres separat med:

```sh
python scripts/frontend_contract.py build/data --expected-entries 39
```
