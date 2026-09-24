# 1.2.0-rc5 — 24. september 2026

- K-CD 15/2001 utvides med 29 Tools-kildeposter med original norsk omtale og bilder: 68 kildeposter på CD-en, 207 totalt fra sju CD-er.
- Historiske K-lenker og tidligere identifiseringer beholdes; nye Tools-poster er uavklarte og får navneromsatte lenker.
- Lokal lesevisning for automatisk førstegjennomgang er utviklet, men følger ikke med offentlig pakke.

# 1.2.0-rc4 — 24. september 2026

Offentlig pakke med godkjent Bootdisk-forside og Komputer for alle-samling.
Sju CD-er, 178 kildeposter og 576 bildefiler; kildedata er uendret fra rc3.
Kurateringsprototypen nedenfor følger fortsatt ikke med den offentlige pakken.

# Upubliserte endringer

- Bootdisk-forside på rotadressen i stedet for omdirigering til arkivet. Komputer for
  alle presenteres som første samling, med antall CD-er og kildeposter hentet fra data
  og en lenke til alle kildeposter.
- Samlingsside (`collection.html?collection=komputer-for-alle`) med ny historietekst,
  kilder og alle CD-ene gruppert etter år, nyeste utgave først og numerisk sortert.
- CD-visning i arkivet (`archive.html?medium=…`) med CD-navn, vei tilbake til samlingen
  og til alle kildeposter. Detaljsiden har brødsmuler: Bootdisk → samling → CD → post.
- Web-eid samlingsregister (`collections.json`) med byggeport: et medium uten samling,
  en dobbel kobling eller en ukjent kildepost stopper releasen med en forklaring.
- Egne tilstander for lasting, tom samling, ukjent samling, ukjent post og datafeil.
  Feil vises aldri som null CD-er. Et medium som registeret ikke kobler til en samling,
  gir feilmelding også i nettleseren, ikke en lavere telling.
- Sitemap tar med forsiden og samlingssidene. HTTP-verifikatoren kontrollerer forsiden,
  samlingssidene og at kuratorfilene ikke er offentlige.
- Arkivets filterlinje gir ikke lenger horisontal rulling ved 1280 eller 360 px bredde.

- Kurateringsoversikt (`overview.html`) som prototype: søk på navn og kildepost,
  status- og feltfiltre, sortering, sidevisning på 50 rader, og åpning av en rad i den
  eksisterende kurateringsflyten med retur til samme søk, filtre, side og tastaturfokus.
  Raden friskes opp fra adapterens faktiske svar etter en beslutning.
- Oversikten skiller kladd fra sist godkjent verdi, og gjennomgått fra fullstendig
  avklart. Status er lesbar uten farge, og smal skjerm beholder alle kolonnene.
- Deterministiske syntetiske prøvedata på 5 230 oppføringer fordelt på 125 kildeposter,
  med gjentatte K-ID-er og programnavn. Genereres i minnet og lagres ikke.
- Prototypens leselag er et forslag til Catalog, på sitt eget skjema, og har ingen
  skriveoperasjon. Oversikt, leselag og prøvedata er holdt utenfor den offentlige
  release-allowlisten.
- Detaljskjermen laster bare filer den lokale tjenesten faktisk serverer, så lokal
  kuratering starter som før. Prototypens filer lastes først når skjermen åpnes fra
  oversikten med prøvedata.
- «Tilbake til oversikten» venter på at siste kladd er bekreftet, og stopper returen ved
  lagringsfeil, konflikt eller pågående beslutning. Teksten beholdes, med en forklaring.
- Oversikten regner arbeidsbehov fra kladden, slik Catalogs tjeneste gjør, og viser endret
  vurdering eller begrunnelse selv når verdien er den samme. En kladd som setter et felt
  til «Belagt» vises som kladd, ikke som en ny godkjent vurdering.
- Retur og beslutning deler nå én grense: mens en retur venter på siste skriving, avvises
  nye beslutninger og intern navigasjon, og selve navigasjonen skjer innenfor grensen.
- Kildevalg teller som kladdendring. Kilde-ID-er sammenlignes som et sett, sammensatte
  verdier sammenlignes semantisk, og raden sier om belegg er lagt til, fjernet eller byttet.
- Kvitteringer bindes til kildepost og oppføring sammen, ikke til K-ID-en alene.
- Prøvedataadapteren beskytter den tilbakeførte CD-omtalen mot overskriving og gir
  «Utsatt: …» tilbake til skjermen, slik den lokale tjenesten gjør.
- [Kontrollmatrise](docs/curator-control-matrix.md) med regel, kode, test og faktisk
  resultat for kuratorskjermene, lenket fra README.
- Merkelenken øverst på kurateringsskjermen går gjennom samme lagringskontroll som
  «Tilbake til oversikten»: en bekreftet kladd slipper rett gjennom uten spørsmål, mens
  lagringsfeil, konflikt eller pågående beslutning stopper utgangen og beholder teksten.
  Modifisert klikk åpner fortsatt ny fane og lar siden stå.

- Vis identiske CD-omtaler én gang under «Omtale på CD-en», med eksisterende
  kildevalg bevart og begge tekniske referanser tilgjengelige.

- Vis beskrivelsen som skrivebeskyttet original CD-omtale når Catalog har
  tilbakeført originalteksten. Vis tilbakeføringen i beslutningshistorikken.

- Vis CD-kategori og lisens som lesbare kildebelegg, forklar avhukingen og åpne
  kildevalgene når tidligere klassifisering trenger ny kontroll.

- Vis ukjent versjon som «Ikke oppgitt» i kurateringen; behold katalogens lagringsformat.

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
