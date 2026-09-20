# Bootdisk Web

Statisk presentasjonslag for det bevarte Bootdisk-arkivet. Catalog eier identitet og evidens; Publish eier webklare filer. Dette repoet eier bare den gjenoppbyggbare visningen.

## Lokal test

```sh
python -m unittest discover -s tests -v
```

Node må være tilgjengelig for JavaScript-testene. Nettleserkontrollene i
`tests/test_curator_browser.py` hoppes over uten Playwright; kjør dem lokalt med
`pip install playwright && playwright install chromium`.

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

Offentlige, stabile lenker og metadata er dokumentert i [`docs/url-contract.md`](docs/url-contract.md). Sitemap og `robots.txt` genereres automatisk av releasebygget.

## Lokal kuratering i 1.2

Kurateringsskjermen kjører lokalt mot prøvedata. Start den fra reporoten, fordi
prøvedataene ligger under `tests/fixtures/`:

```sh
python -m http.server 8000
```

Åpne `http://localhost:8000/curate.html`. Skjermen er merket
«Prøvedata – endrer ikke katalogen» og skriver ingenting til katalogen.

[Arbeidsordren til Claude](docs/claude-curator-work-order.md) avgrenser frontend-
leveransen, og [frontend v1](docs/curator-frontend-v1.md) beskriver filene,
hurtigtastene og kontraktobservasjonene. Datakontrakt og ADR-er eies av
`bootdisk-catalog`; ekte kataloglagring bygges separat. Kurateringsverktøyet inngår
ikke i den offentlige statiske releasen.

## Kurateringsoversikt (prototype)

En egen oversikt over hele kurateringskøen, med søk, filtre, status og navigasjon til og
fra kurateringsskjermen. Kjør den fra reporoten på en egen port, så den ikke kolliderer
med en kjørende lokal tjeneste:

```sh
python -m http.server 8791
```

Åpne `http://localhost:8791/overview.html`. Oversikten bruker syntetiske prøvedata for å
måle skalaen, leser bare, og er ikke integrert med den lokale tjenesten.
[Prototypen](docs/curator-overview-prototype.md) beskriver hva som virker, hva som bare er
prøvedata, forslaget til lesekontrakt og backendavhengighetene.

## Ekte lokal kuratering

Start Catalogs lokale tjeneste med dette repoet som `--web-root`, og åpne
`http://127.0.0.1:8772/curate.html?mode=local`. Se
[oppsettet](https://github.com/bootdiskhq/bootdisk-catalog/blob/main/docs/local-curator-service.md).
Denne modusen lagrer i arbeidsområdet på disk og faller aldri tilbake til prøvedata
ved feil. Den publiserer ikke til bootdisk.no.
