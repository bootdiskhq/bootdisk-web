# Changelog

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
