-- Besøkstellerens lagring (SQLite). Opprettes bare av scripts/visit-counter-db.py init;
-- counter/besok.php lager aldri en ny database, slik at en borte fil gir «Teller utilgjengelig»
-- i stedet for en stille nullstilling.
PRAGMA user_version = 1;

-- Én rad: totalen og datoen telleren ble satt i drift (Europe/Oslo).
CREATE TABLE counter (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  total INTEGER NOT NULL CHECK (total >= 0),
  since TEXT NOT NULL
);

-- Besøksnøkler som allerede er telt, slik at samme nøkkel aldri telles to ganger.
-- Nøkkelen er et tilfeldig tall fra nettleseren; ingen IP, ingen nettleserdata. Slettes etter 48 timer.
CREATE TABLE visits (
  key TEXT PRIMARY KEY,
  expires INTEGER NOT NULL
) WITHOUT ROWID;
CREATE INDEX visits_expires ON visits (expires);

-- Samlet per døgn: telte besøk og hvor mange som ble avvist av grensene. Brukes til å oppdage
-- og rette opp oppblåste tall. Inneholder ingen enkeltbesøk.
CREATE TABLE daily (
  day TEXT PRIMARY KEY,
  counted INTEGER NOT NULL DEFAULT 0,
  limited INTEGER NOT NULL DEFAULT 0
) WITHOUT ROWID;

-- Nye besøk per minutt, for minuttgrensen. Slettes etter fem minutter.
CREATE TABLE minutes (
  minute INTEGER PRIMARY KEY,
  counted INTEGER NOT NULL DEFAULT 0
);
