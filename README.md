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
