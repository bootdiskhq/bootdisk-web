# Upubliserte endringer

- Kildebelegg viser lesbar kildetype, filnavn og tekstutdrag ved avkryssingen.
  Lange utdrag kan åpnes, og hasher ligger under «Tekniske detaljer».

- Lokal kurateringsskjerm (`curate.html`) med kø, kildebelegg, redigerbare påstander,
  «godkjenn/lagre og neste», «hopp over» og «angre».
- Fixture-adapter for `bootdisk-curator-v1` med versjonert nettleserlagring, eksplisitt
  tilbakestilling og simulerte feil-, konflikt- og kildeproblemtilstander.
- Kurator, prøvedata og skriveveier er holdt utenfor den offentlige release-allowlisten.
- Rettet etter gjennomgang av PR #27: lagringssvar er bundet til sin egen kildepost,
  gjenforsøk sender den opprinnelige forespørselen for alle skriveoperasjoner, og en
  avvist nettleserlagring meldes som mislykket skriving i stedet for lagret kladd.
- Rettet etter gjennomgang av PR #28: «Bruk forslaget» oppdaterer feltet og
  kildebelegget med én gang, så skjemaet aldri viser en annen verdi enn den som
  ville blitt godkjent.

# 1.1.0-rc2

- Oppdatert kataloggrunnlag: 35 kuraterte og fire foreløpige identifikasjoner.
- CPU-Z 1.10 og Font Xplorer Lite 1.2.2 bekreftet fra pakkene.
- Icebreaker-pakkens innebygde kildekode er identifisert som 1.2.1.

# 1.1.0-rc1

- Vis innholdstype og distribusjonsutgave fra Catalog.
- Merk foreløpige identifikasjoner i oversikt og detaljvisning.
- Vis ukjent versjon på norsk; utelat den fra sidetittel og oversiktskort.

# Changelog

## Unreleased — local 1.2 integration

- Connect curator to the durable Catalog service through an explicit live adapter.
- Show local-workspace mode, history and defer reasons; hide fixture simulations.
- Unlock controls after decisions and refresh accepted labels after undo.


## 1.0.0

- Promoterer den produksjonsgodkjente `1.0.0-rc1`-kandidaten uten funksjonelle endringer.
- Bekrefter komplett produksjonsverifikasjon av 39 kildeposter, 136 filer og 40 sitemap-adresser.
- Bekrefter arkiv, detaljsider, søk og navigasjon visuelt på desktop og mobil.

## 1.0.0-rc1

- Fryser og dokumenterer frontend-datakontrakten for 1.0-serien.
- Validerer kildeposter, kildekontekst, kurateringsstatus, ressursbindinger, stier og SHA-256 før releasepakking.
- Dokumenterer stabile offentlige URL-er med K-ID som varig identifikator.
- Legger til canonical- og delingsmetadata, `robots.txt` og komplett sitemap.
- Utvider produksjonsverifikasjonen til å kreve samsvar mellom sitemap og alle kildeposter.
- Avgrenser kandidaten til den komplette, regenererbare publiseringen av K-CD 15/2001.

## 0.4.0

- Samler frontendbygg, pakking og release-rapport i én kontrollert kommando.
- Produserer deterministisk ZIP og maskinlesbar rapport med input- og output-hasher.
- Legger til full HTTP-verifisering av poster, mediefiler, innholdshasher og 404.
- Dokumenterer sikker Domeneshop-deploy, backup og komplett rollback.
- Viser menneskelige programnavn i forrige/neste-navigasjonen og støtter piltaster.

## 0.3.0

- Legger til eksplisitte last-, feil- og tomtilstander for datadrevne sider.
- Genererer detaljsidens beskrivelse og skjermbildetekst fra presentasjonsdata.
- Legger til hopp-lenker, stabile hovedlandemerker og no-script-meldinger.
- Respekterer brukerens preferanse for redusert bevegelse.
- Presenterer kurateringsstatus med menneskevennlige norske navn.

## 0.2.0

- Legger til delbare søk, statusfiltre og sortering i arkivoversikten.
- Lar brukeren nullstille filtrene uten å laste siden på nytt.
- Legger til forrige/neste-navigasjon som følger den autoritative kildeindeksen.
- Beholder den statiske, regenererbare arkitekturen og Catalog/Publish-grensene.

## 0.1.0

Første stabile Bootdisk Web-utgivelse.

- Presenterer hele K-CD 15/2001 som et søkbart statisk arkiv.
- Viser kuratert programvareidentitet uten å gjette på uidentifiserte poster.
- Kobler Catalog-fakta til verifiserte Publish-bilder gjennom stabile kildeposter og hashverdier.
- Bygger en lukket deploymappe som bare inneholder refererte filer.
- Legger til trygg tekst-rendering, mobilvennlig visning, rot-routing og 404-side.
- Promotert fra den validerte `0.1.0-rc1`-kandidaten uten nye funksjoner.

## 0.1.0-rc1

- Presenterer hele K-CD 15/2001 som et søkbart statisk arkiv.
- Viser kuratert programvareidentitet uten å gjette på uidentifiserte poster.
- Kobler Catalog-fakta til verifiserte Publish-bilder gjennom stabile kildeposter og hashverdier.
- Bygger en lukket deploymappe som bare inneholder refererte filer.
- Legger til trygg tekst-rendering, mobilvennlig visning, rot-routing og 404-side.
