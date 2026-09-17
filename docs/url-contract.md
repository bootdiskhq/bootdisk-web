# URL- og metadata-kontrakt 1.0

Bootdisk Web 1.0 publiserer følgende stabile offentlige URL-er:

- `https://bootdisk.no/archive.html` er arkivoversikten.
- `https://bootdisk.no/index.html?entry=K<nummer>` er en permanent detaljlenke til én kildepost.
- `https://bootdisk.no/data/` og `https://bootdisk.no/store/` er genererte grensesnitt for presentasjonslaget, ikke menneskelige inngangsadresser.

Rotadressen leder til arkivoversikten. K-ID-en er den stabile identifikatoren i URL-en, mens menneskelige programnavn vises i grensesnittet og kan forbedres gjennom Catalog uten å bryte gamle lenker.

## Oppdagelse og deling

Releasebygget genererer `robots.txt` og `sitemap.xml` fra den validerte indeksen. Derfor følger nye kildeposter automatisk med uten håndredigering. Arkivoversikten har en statisk canonical-URL og Open Graph-metadata. Detaljvisningen setter canonical-URL, tittel og beskrivelse fra den aktuelle kildeposten. 404-siden er merket `noindex`.

Produksjonsverifikatoren krever at sitemap og indeks inneholder nøyaktig samme sett detaljlenker.
