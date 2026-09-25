<?php
/* Bootdisk besøksteller: foreslått backend (PHP 8 + PDO SQLite). IKKE AKTIVERT.
 *
 * Kontrakt (docs/visit-counter.md):
 *   GET                                -> 200 {"total": 123, "since": "2026-09-25"}
 *   POST {"visit": "<32 små hex-tegn>"} -> 200 {"total": 124, "since": "2026-09-25", "counted": true, "limited": false}
 *
 * - Telleren oppdateres i én SQLite-transaksjon (BEGIN IMMEDIATE), så parallelle forespørsler
 *   ikke mister oppdateringer.
 * - Samme besøksnøkkel telles bare én gang så lenge den huskes (48 timer).
 * - Minutt- og døgngrenser begrenser hvor fort totalen kan blåses opp. Avviste besøk telles
 *   bare som et samlet døgntall.
 * - Ingen IP-adresser, ingen informasjonskapsler, ingen logging fra denne filen.
 * - Filen lager aldri databasen. Mangler den, svarer tjenesten 503 og siden viser
 *   «Teller utilgjengelig»; totalen blir aldri stille nullstilt.
 *
 * Innstillinger kommer fra miljøvariabler når de finnes, ellers fra standardverdiene under.
 * BOOTDISK_COUNTER_NOW finnes bare for testene (styrt klokke) og settes aldri i drift. */
declare(strict_types=1);

const VISIT_KEY_TTL = 48 * 3600;
const MINUTES_KEPT = 5;
const MAX_BODY_BYTES = 256;

function setting(string $name, string $default): string
{
    $value = getenv($name);
    return $value === false || $value === '' ? $default : $value;
}

function respond(int $status, array $body, array $headers = []): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    header('Referrer-Policy: no-referrer');
    foreach ($headers as $header) {
        header($header);
    }
    echo json_encode($body, JSON_UNESCAPED_SLASHES);
    exit;
}

function open_counter(string $path): PDO
{
    // En manglende fil er en driftsfeil, ikke et nytt nullpunkt.
    if (!is_file($path)) {
        respond(503, ['error' => 'unavailable']);
    }
    $pdo = new PDO('sqlite:' . $path, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('PRAGMA busy_timeout = 5000');
    if ((int) $pdo->query('PRAGMA user_version')->fetchColumn() !== 1) {
        respond(503, ['error' => 'unavailable']);
    }
    return $pdo;
}

function current_total(PDO $pdo): array
{
    $row = $pdo->query('SELECT total, since FROM counter WHERE id = 1')->fetch(PDO::FETCH_ASSOC);
    if (!$row) {
        throw new RuntimeException('counter row missing');
    }
    return ['total' => (int) $row['total'], 'since' => (string) $row['since']];
}

$databasePath = setting('BOOTDISK_COUNTER_DB', dirname(__DIR__, 2) . '/bootdisk-besok/besok.sqlite');
$allowedOrigin = setting('BOOTDISK_COUNTER_ORIGIN', 'https://bootdisk.no');
$minuteLimit = (int) setting('BOOTDISK_COUNTER_MINUTE_LIMIT', '60');
$dayLimit = (int) setting('BOOTDISK_COUNTER_DAY_LIMIT', '3000');
$now = (int) setting('BOOTDISK_COUNTER_NOW', (string) time());
$day = (new DateTimeImmutable('@' . $now))->setTimezone(new DateTimeZone('Europe/Oslo'))->format('Y-m-d');
$minute = intdiv($now, 60);

$method = $_SERVER['REQUEST_METHOD'] ?? '';

try {
    if ($method === 'GET' || $method === 'HEAD') {
        respond(200, current_total(open_counter($databasePath)));
    }
    if ($method !== 'POST') {
        respond(405, ['error' => 'method'], ['Allow: GET, HEAD, POST']);
    }

    // Grovfilter mot forespørsler fra andre nettsteder. Et skript kan forfalske disse; grensene
    // lenger ned er det som faktisk begrenser oppblåsing.
    if (($_SERVER['HTTP_ORIGIN'] ?? '') !== $allowedOrigin) {
        respond(403, ['error' => 'origin']);
    }
    $site = $_SERVER['HTTP_SEC_FETCH_SITE'] ?? 'same-origin';
    if ($site !== 'same-origin') {
        respond(403, ['error' => 'origin']);
    }
    if (stripos($_SERVER['CONTENT_TYPE'] ?? '', 'application/json') !== 0) {
        respond(415, ['error' => 'content-type']);
    }
    $raw = file_get_contents('php://input', false, null, 0, MAX_BODY_BYTES + 1);
    if ($raw === false || strlen($raw) > MAX_BODY_BYTES) {
        respond(413, ['error' => 'size']);
    }
    $body = json_decode($raw, true);
    if (!is_array($body) || array_keys($body) !== ['visit'] || !is_string($body['visit'])
        || preg_match('/^[0-9a-f]{32}$/D', $body['visit']) !== 1) {
        respond(400, ['error' => 'visit']);
    }
    $key = $body['visit'];

    $pdo = open_counter($databasePath);
    $pdo->exec('BEGIN IMMEDIATE');
    try {
        $pdo->prepare('DELETE FROM visits WHERE expires <= ?')->execute([$now]);
        $pdo->prepare('DELETE FROM minutes WHERE minute < ?')->execute([$minute - MINUTES_KEPT]);

        $known = $pdo->prepare('SELECT 1 FROM visits WHERE key = ?');
        $known->execute([$key]);
        $counted = false;
        $limited = false;
        if ($known->fetchColumn() === false) {
            $minuteCount = $pdo->prepare('SELECT counted FROM minutes WHERE minute = ?');
            $minuteCount->execute([$minute]);
            $dayCount = $pdo->prepare('SELECT counted FROM daily WHERE day = ?');
            $dayCount->execute([$day]);
            if ((int) $minuteCount->fetchColumn() >= $minuteLimit || (int) $dayCount->fetchColumn() >= $dayLimit) {
                $limited = true;
                $pdo->prepare('INSERT INTO daily (day, limited) VALUES (?, 1)
                               ON CONFLICT (day) DO UPDATE SET limited = limited + 1')->execute([$day]);
            } else {
                $pdo->prepare('INSERT INTO visits (key, expires) VALUES (?, ?)')->execute([$key, $now + VISIT_KEY_TTL]);
                $pdo->exec('UPDATE counter SET total = total + 1 WHERE id = 1');
                $pdo->prepare('INSERT INTO daily (day, counted) VALUES (?, 1)
                               ON CONFLICT (day) DO UPDATE SET counted = counted + 1')->execute([$day]);
                $pdo->prepare('INSERT INTO minutes (minute, counted) VALUES (?, 1)
                               ON CONFLICT (minute) DO UPDATE SET counted = counted + 1')->execute([$minute]);
                $counted = true;
            }
        }
        $result = current_total($pdo);
        $pdo->exec('COMMIT');
    } catch (Throwable $error) {
        $pdo->exec('ROLLBACK');
        throw $error;
    }
    respond(200, $result + ['counted' => $counted, 'limited' => $limited]);
} catch (Throwable $error) {
    // Ingen detaljer ut, ingen logglinje med forespørselsdata.
    respond(503, ['error' => 'unavailable']);
}
