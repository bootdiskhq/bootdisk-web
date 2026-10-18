# Retro-designet

Bootdisk bygger på det første utkastet fra september: mørk terminalbakgrunn, cyan
BOOTDISK_-logo, ravgule etiketter og monospace. Oppå det ligger de harde kantene fra et
90-tallsprogram: avfasede knapper og felt, vinduer med tittellinje, pikselikoner, en
verktøylinje, adresselinje og statuslinje, og DOS der siden viser aktivitet og systemstatus. Alt ligger i de eksisterende stilarkene;
ingen nye filer, skrifter eller avhengigheter.

## Hvor ting ligger

- `styles.css` er felles for alle sider, også kurateringsverktøyene. Den har fargepaletten,
  avfasingene (`--raised`, `--pressed`, `--sunken`, `--etched`), pikselikonene som SVG i
  CSS-variabler (`--icon-floppy`, `--icon-folder`, `--icon-cd`, `--icon-warning` …) og de
  gjenbrukbare komponentene: programvinduet (`.app-window`, `.title-bar`, `.toolbar`),
  undervinduer (`.window`/`.win`), knapper (`button`, `.button`, `.primary-link`), felt,
  dialogmeldinger (`.system-message`/`.msg`), terminal (`.terminal`, `.prompt`,
  `.block-cursor`), informasjonsboks (`.about`), ikonvisning (`.archive-grid`) og
  statuslinjen (`footer`).
- De eldre variabelnavnene (`--ink`, `--muted`, `--cyan`, `--amber` …) peker på den nye
  paletten, slik at sidefilene kan bruke dem uten egne fargekoder.
- Sidefilene (`publication.css`, `updates.css`, `curate.css`, `overview.css`,
  `automation.css` …) legger bare ut sitt eget innhold.

## Regler

- **Program for struktur, DOS for aktivitet.** Navigasjon, skjemaer, lister og dialoger er
  avfasede programkontroller. Lasting, oppdateringshistorikken, tallene på forsiden og oppstartsteksten er DOS.
- **Ingen pyntekontroller.** Vinduene har ingen minimer-, maksimer- eller lukkeknapper, og
  kolonneoverskrifter er flate fordi de ikke sorterer. Alt som ser ut som en knapp, er en
  knapp eller en lenke med én tydelig handling.
- **Verktøylinjen er ekte navigasjon** på de offentlige sidene (Forside, Alle kildeposter,
  Oppdateringer) og markerer gjeldende side med `aria-current`. Kurateringssidene har bare
  tittellinjen, så navigasjonsporten der ikke får nye lenker.
- **Status har alltid ord.** Farge er aldri eneste signal; oppdateringsmerker står i klammer.
- **Fokus** er en prikket ramme på 2 px, lys på mørke flater og mørk på cyan markering.
- **Bevegelse** er bare blinkende markør og en oppstartstekst som kommer linje for linje på
  under et halvt sekund. Begge stopper med `prefers-reduced-motion`.
- **Mobil:** verktøylinjen blir tre like store knapper med ikon over
  tekst, filtre og paneler stables, og trykkflatene er minst 40–56 px høye.
