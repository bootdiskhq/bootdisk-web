# Frontend-datakontrakt 1.0

Bootdisk Web leser bare genererte presentasjonsdata. Catalog eier programvareidentitet og evidens, mens Publish eier publiserte filer. Kontrakten nedenfor fryses for 1.0-serien slik at presentasjonslaget kan slettes og bygges på nytt uten håndredigering.

## `data/index.json`

Rotobjektet skal inneholde:

- `publication`: ikke-tom tekst fra byggeparameteren.
- `medium`: ikke-tom tekst fra byggeparameteren.
- `entries`: kildeposter i stigende numerisk K-rekkefølge.

Hver indekspost skal minst ha en unik `entry` på formen `K<nummer>` og `curation_status` lik `identified` eller `pending`. `editorial_title`, `software_name`, `version` og `icon` kan være `null`; nettleseren skal aldri finne på manglende identitet.

## `data/k<nummer>.json`

Det skal finnes nøyaktig ett detaljdokument per indekspost. Dokumentets `entry`, `publication` og `medium` skal samsvare med indeksen. `software` og `assets` er alltid lister, også når de er tomme.

En ressurs skal:

- tilhøre samme `entry` som detaljdokumentet;
- ha typen `icon` eller `screenshot`;
- peke til en relativ `store/`-sti uten `..`;
- oppgi en SHA-256 for originalen og hvert derivat.

Utvidelser kan legge til felter. Eksisterende felt endres eller fjernes først i en ny hovedversjon av kontrakten.

## Validering

Kjør kontraktporten direkte med:

```sh
python scripts/frontend_contract.py build/data --expected-entries 39
```

`build-release.py` kjører samme port automatisk før den kopierer data eller filer til en deploymappe. Dermed kan en ugyldig eller halvferdig projeksjon ikke pakkes som release.
