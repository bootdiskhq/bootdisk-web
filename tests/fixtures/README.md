# Kuratorfixtures

`curator-fixtures-v1.json` er kopiert **uendret** fra `bootdisk-catalog`.

| | |
| --- | --- |
| Kilde | https://github.com/bootdiskhq/bootdisk-catalog/blob/main/docs/curator-fixtures-v1.json |
| Catalog-commit | `09bd0dbccac4e9ee39f1d2593558f96543449116` |
| Kontraktversjon | `bootdisk-curator-v1` ([curator-contract-v1.md](https://github.com/bootdiskhq/bootdisk-catalog/blob/main/docs/curator-contract-v1.md)) |
| SHA-256 | `9d5516da282578794bf913e26a2b801e674e9b97497fd5ee44d924b794e2e3e1` |

Filen inneholder ekte kildeobservasjoner for K23 (CPU-Z) og K4 (Blockout), men
**simulert** gjennomgangstilstand og simulerte revisjoner. Den er ikke en
katalogimport og ikke en katalogbeslutning.

## Regler

Filen skal ligge her uendret. `tests/test_curator.py` verifiserer SHA-256-summen
over. Feil, konflikter, manglende media og videre tilstander simuleres i
`curate-adapter.js` eller i testene — aldri ved å redigere denne filen.

Mappen ligger under `tests/` og er derfor utenfor den offentlige
release-allowlisten i `scripts/build-release.py`.
