# URL- og metadata-kontrakt

Bootdisk Web publiserer statiske sider som virker uten serveromskrivinger:

| URL | Innhold | Canonical |
|---|---|---|
| `https://bootdisk.no/` og `/index.html` uten `entry` | Bootdisk-forsiden med samlingene | `https://bootdisk.no/` |
| `/collection.html?collection=<nøkkel>` | Én samling: introduksjon og alle CD-ene, for eksempel `komputer-for-alle` | Seg selv, satt av sidescriptet |
| `/archive.html` | Alle kildeposter på tvers av samlinger | `https://bootdisk.no/archive.html` |
| `/archive.html?medium=<medie-ID>` | Innholdet på én CD, for eksempel `kcd-13-2000` | `https://bootdisk.no/archive.html` |
| `/index.html?entry=<ID>` | Permanent detaljlenke til én kildepost | Seg selv, satt av sidescriptet |
| `/data/`, `/store/`, `/collections.json` | Genererte grensesnitt for presentasjonslaget, ikke inngangsadresser | – |

Detaljlenkene er stabile. Den historiske CD-en beholder korte lenker som
`index.html?entry=K37` (Winamp på K-CD 15/2001), mens nyere CD-er får navnerom som
`index.html?entry=kcd-1-2001--K37` (WinZip på K-CD 1/2001). Menneskelige programnavn vises
i grensesnittet og kan forbedres gjennom Catalog uten å bryte gamle lenker.

`index.html` er både forside og detaljside. Uten `entry`-parameter viser den forsiden og
sender ikke lenger nettleseren videre til arkivet. Med `entry` viser den kildeposten. En
ugyldig, tom eller ukjent `entry` gir en egen feilvisning merket `noindex`, aldri forsiden
eller en tilfeldig post. En ukjent eller ugyldig `collection` gir «Fant ikke samlingen»,
og en ukjent `medium` i arkivet sier fra og viser alle kildeposter. ID-er valideres før de
brukes i filstier; samlingsnøkkelen brukes aldri i en filsti.

Arkivets filtre (`q`, `medium`, `status`, `sort`) står i adressen. Derfor bevarer
nettleserens tilbakeknapp valgt CD og søk, og lenker kan kopieres og åpnes i ny fane.

## Oppdagelse og deling

Releasebygget genererer `robots.txt` og `sitemap.xml` fra den validerte indeksen og
samlingsregisteret. Sitemap inneholder forsiden, arkivoversikten, hver samling som har
minst én CD, og nøyaktig én detaljlenke per kildepost. Nye kildeposter og samlinger følger
automatisk med uten håndredigering. CD-filtrene står ikke i sitemap; de er visninger av
arkivet.

Forsiden og arkivet har statisk canonical-URL og Open Graph-metadata. Samlings- og
detaljsider setter canonical-URL, tittel og beskrivelse fra data. Feilvisninger og
404-siden er merket `noindex`.

Produksjonsverifikatoren (`scripts/verify-deployment.py`) krever at forsiden svarer på både
`/` og `/index.html` med rot-canonical, at hver samlingsside svarer, at sitemap har nøyaktig
samme sett detaljlenker som indeksen og ellers bare forside, arkiv og samlinger, og at
kurateringsfiler og prøvedata svarer 404.
