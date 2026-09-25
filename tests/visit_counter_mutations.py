"""Legger inn kjente feil i besøkstelleren én om gangen og kjører testene mot hver.

Ikke en del av testkjøringen. Kjør fra reporoten når telleren eller testene endres:

    python tests/visit_counter_mutations.py            # alle
    python tests/visit_counter_mutations.py M8 M13     # utvalgte

Hver fil settes tilbake etterpå, også ved avbrudd. Resultatene står i docs/visit-counter.md.
Uten Playwright, Chromium eller PHP hoppes de aktuelle testene over, og da blir flere feil
«IKKE FANGET». Sett CURATOR_CHROMIUM som for nettlesertestene.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = dict(os.environ)
M = [
 ("M1 inaktivitetsgrense < i stedet for <=", "visit-counter-core.js", "now - previous.last <= VISIT_IDLE_MS", "now - previous.last < VISIT_IDLE_MS"),
 ("M2 bekreftet besøk sendes likevel", "visit-counter-core.js", "const retry = !record.confirmed && now", "const retry = true || now"),
 ("M3 ny nøkkel ved ny innsending", "visit-counter-core.js", "return { record, action: retry ? \"record\" : \"read\" };", "return retry ? { record: { ...record, key: newKey() }, action: \"record\" } : { record, action: \"read\" };"),
 ("M4 blokkert lagring teller hver side", "visit-counter-core.js", "if (!plan || plan.action === \"read\")", "if (!plan) plan = { action: 'record', record: { key: newKey() } };\n  if (plan.action === \"read\")"),
 ("M5 bekreftelse overskriver annen fanes besøk", "visit-counter-core.js", "if (!current || current.key !== key) return null;", "if (!current) return null;"),
 ("M6 svarkontroll godtar tekst-total", "visit-counter-core.js", "if (!Number.isSafeInteger(body.total) || body.total < 0)", "if (body.total === undefined)"),
 ("M7 feil vises som nuller", "visit-counter.js", "root.replaceChildren(Object.assign(document.createElement(\"span\"), { className: \"visit-counter-unavailable\", textContent: \"Teller utilgjengelig\" }));", "cells(visitDigits(0));"),
 ("M8 uten Web Locks", "visit-counter.js", "navigator.locks && typeof navigator.locks.request === \"function\"", "false"),
 ("M9 hidden overstyres av display", "visit-counter.css", ".visit-counter[hidden] {\n  display: none;\n}", ""),
 ("M10 sifre leses opp enkeltvis", "visit-counter.js", "digits.setAttribute(\"aria-hidden\", \"true\");", ""),
 ("M11 fem sifferfelt", "visit-counter-core.js", "const VISIT_MIN_DIGITS = 6;", "const VISIT_MIN_DIGITS = 5;"),
 ("M12 teller aktiv uten produksjonsopprinnelse", "visit-counter.js", " || config.origin !== window.location.origin", ""),
 ("M13 PHP les-endre-skriv uten transaksjon", "counter/besok.php", [("$result = current_total($pdo);\n        $pdo->exec('COMMIT');", "$result = current_total($pdo);"), ("$pdo->exec('BEGIN IMMEDIATE');", ""), ("$pdo->exec('UPDATE counter SET total = total + 1 WHERE id = 1');", "$t = (int) $pdo->query('SELECT total FROM counter')->fetchColumn(); usleep(20000); $pdo->exec('UPDATE counter SET total = ' . ($t + 1));"), ("$pdo->exec('ROLLBACK');", "")], None),
 ("M14 PHP uten dedup", "counter/besok.php", "if ($known->fetchColumn() === false) {", "if (true) { $pdo->prepare('DELETE FROM visits WHERE key = ?')->execute([$key]);"),
 ("M15 PHP uten opprinnelsessjekk", "counter/besok.php", "if (($_SERVER['HTTP_ORIGIN'] ?? '') !== $allowedOrigin) {", "if (false) {"),
 ("M16 PHP lager manglende database", "counter/besok.php", "    if (!is_file($path)) {\n        respond(503, ['error' => 'unavailable']);\n    }\n", ""),
 ("M17 PHP uten grenser", "counter/besok.php", "if ((int) $minuteCount->fetchColumn() >= $minuteLimit ||", "if (false &&"),
 ("M18 PHP nøkler huskes 1 time", "counter/besok.php", "const VISIT_KEY_TTL = 48 * 3600;", "const VISIT_KEY_TTL = 3600;"),
 ("M19 backend i releasen", "scripts/build-release.py", '"visit-counter.js", "VERSION")', '"visit-counter.js", "counter/besok.php", "VERSION")'),
 ("M20 aktivert konfig pakkes", "visit-counter-config.js", "endpoint: null });", "endpoint: \"/api/besok.php\" });"),
 ("M21 adapter uten tidsavbrudd", "visit-counter-adapter.js", "if (controller) controller.abort();", ""),
]
only = sys.argv[1:]
for name, rel, old, new in M:
    if only and not any(name.startswith(o+" ") for o in only): continue
    path = ROOT / rel
    src = path.read_text()
    pairs = old if isinstance(old, list) else [(old, new)]
    mutated = src
    for o, n in pairs:
        assert mutated.count(o) == 1, (name, o, mutated.count(o))
        mutated = mutated.replace(o, n)
    try:
        path.write_text(mutated)
        mods = ["tests.test_visit_counter", "tests.test_visit_counter_browser"]
        r = subprocess.run([sys.executable, "-m", "unittest", *mods], cwd=ROOT, capture_output=True, text=True, env=env, timeout=600)
        fails = [l for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
        print(("FANGET " if r.returncode else "IKKE FANGET ") + name, len(fails))
        for l in fails[:4]: print("   ", l[:150])
    finally:
        path.write_text(src)
