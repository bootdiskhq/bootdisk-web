<?php
/* Bootdisk kontaktskjema: mottak på webhotellet (PHP 8.1+). Se docs/kontaktskjema.md.
 *
 * Kontrakt:
 *   GET   -> 200 {"ready": true,  "provider": "turnstile", "site_key": "…", "max_message": 4000}
 *         -> 200 {"ready": false}                       (oppsett mangler eller er ufullstendig)
 *   POST  {"email": "…", "message": "…", "captcha": "…", "website": ""}
 *         -> 200 {"ok": true}
 *         -> 4xx/5xx {"ok": false, "error": "<kode>"}  (kodene står i docs/kontaktskjema.md)
 *
 * Rekkefølgen ved POST er fast: oppsett -> opphav -> felter -> hyppighetsgrense -> CAPTCHA ->
 * sending. Ingenting sendes før CAPTCHA er godkjent av leverandøren.
 *
 * Filen inneholder ingen adresser, nøkler eller passord. Alt det ligger i en privat PHP-fil
 * utenfor webroten (standard: ../../bootdisk-privat/kontakt-config.php sett fra denne filen,
 * altså ved siden av /www). Miljøvariabelen BOOTDISK_CONTACT_CONFIG brukes av testene.
 * Meldingen lagres ikke. Den eneste filen som skrives, er hyppighetsgrensen i state_dir, med
 * HMAC av klientadressen og tidspunkter, aldri adresser eller tekst. */
declare(strict_types=1);

const MAX_BODY_BYTES = 65536; // 4000 tegn, også når JSON skriver hvert tegn som \uXXXX-par
const MAX_MESSAGE_CHARS = 4000;
const MAX_EMAIL_CHARS = 254;
const CAPTCHA_PROVIDERS = [
    'turnstile' => 'https://challenges.cloudflare.com/turnstile/v0/siteverify',
    'hcaptcha' => 'https://api.hcaptcha.com/siteverify',
];
/* Leverandørenes feilkoder. Utløpt og allerede brukt behandles likt: leseren må krysse av på nytt. */
const CAPTCHA_EXPIRED = ['timeout-or-duplicate', 'expired-input-response', 'already-seen-response',
    'invalid-or-already-seen-response'];
const CAPTCHA_MISSING = ['missing-input-response'];
const CAPTCHA_SERVER_FAULT = ['missing-input-secret', 'invalid-input-secret', 'sitekey-secret-mismatch',
    'internal-error', 'bad-request'];

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
    echo json_encode($body, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    exit;
}

function fail(int $status, string $code, array $headers = []): never
{
    respond($status, ['ok' => false, 'error' => $code], $headers);
}

/* Driftslogg uten innhold: aldri adresser, meldingstekst, tokens eller nøkler. */
function note(string $event): void
{
    error_log('bootdisk-kontakt: ' . $event);
}

function config_path(): string
{
    $override = getenv('BOOTDISK_CONTACT_CONFIG');
    if ($override !== false && $override !== '') {
        return $override;
    }
    return dirname(__DIR__, 2) . '/bootdisk-privat/kontakt-config.php';
}

function inside(string $path, string $root): bool
{
    $path = rtrim($path, '/') . '/';
    $root = rtrim($root, '/') . '/';
    return str_starts_with($path, $root);
}

function valid_mailbox(mixed $value): bool
{
    return is_string($value) && strlen($value) <= MAX_EMAIL_CHARS && !preg_match('/[\r\n\0,;<>"]/', $value)
        && filter_var($value, FILTER_VALIDATE_EMAIL) !== false;
}

/** Leser og kontrollerer den private konfigurasjonen. Returnerer null når noe mangler. */
function load_config(): ?array
{
    $path = config_path();
    $real = realpath($path);
    if ($real === false || !is_file($real) || !is_readable($real)) {
        note('oppsett mangler');
        return null;
    }
    // Privat konfig i webroten er en feil i seg selv: da kan den havne i en pakke eller en kopi.
    $docroot = realpath((string) ($_SERVER['DOCUMENT_ROOT'] ?? ''));
    if ($docroot !== false && $docroot !== '' && inside($real, $docroot)) {
        note('oppsett ligger i webroten og blir ikke brukt');
        return null;
    }
    $config = (static fn (string $file) => include $file)($real);
    if (!is_array($config)) {
        note('oppsett er ikke en tabell');
        return null;
    }
    $captcha = $config['captcha'] ?? null;
    $transport = $config['transport'] ?? null;
    $ok = valid_mailbox($config['recipient'] ?? null)
        && valid_mailbox($config['sender'] ?? null)
        && is_string($config['client_salt'] ?? null) && strlen($config['client_salt']) >= 32
        && is_string($config['allowed_origin'] ?? null) && preg_match('#^https?://[^/\s]+$#', $config['allowed_origin'])
        && is_string($config['state_dir'] ?? null) && $config['state_dir'] !== ''
        && is_array($captcha) && isset(CAPTCHA_PROVIDERS[$captcha['provider'] ?? ''])
        && is_string($captcha['site_key'] ?? null) && $captcha['site_key'] !== ''
        && is_string($captcha['secret'] ?? null) && $captcha['secret'] !== ''
        && is_array($transport) && in_array($transport['type'] ?? '', ['mail', 'smtp'], true);
    if (!$ok) {
        note('oppsett er ufullstendig');
        return null;
    }
    if ($transport['type'] === 'smtp') {
        $security = $transport['security'] ?? 'starttls';
        if (!is_string($transport['host'] ?? null) || !in_array($security, ['starttls', 'tls', 'none'], true)) {
            note('smtp-oppsett er ufullstendig');
            return null;
        }
        // Passord sendes aldri i klartekst over nettet.
        if ($security === 'none' && isset($transport['username'])) {
            note('smtp med pålogging krever kryptering');
            return null;
        }
    }
    $state = realpath($config['state_dir']);
    if ($state === false || !is_dir($state) || !is_writable($state)
        || ($docroot !== false && $docroot !== '' && inside($state, $docroot))) {
        note('tilstandsmappe mangler, er ikke skrivbar eller ligger i webroten');
        return null;
    }
    $config['state_dir'] = $state;
    return $config;
}

function read_body(): array
{
    $type = strtolower((string) ($_SERVER['CONTENT_TYPE'] ?? ''));
    if (!str_starts_with($type, 'application/json')) {
        fail(415, 'bad_request');
    }
    $raw = file_get_contents('php://input', false, null, 0, MAX_BODY_BYTES + 1);
    if ($raw === false || strlen($raw) > MAX_BODY_BYTES) {
        fail(413, 'bad_request');
    }
    $body = json_decode($raw, true);
    if (!is_array($body)) {
        fail(400, 'bad_request');
    }
    return $body;
}

/** Hyppighetsgrense med fillås. Kaster ikke; returnerer sekunder å vente, 0 når innsendingen er tillatt. */
function rate_limit(array $config): int
{
    $limits = ($config['rate_limit'] ?? []) + ['window' => 600, 'per_client' => 3, 'per_day' => 40];
    $now = time();
    $client = hash_hmac('sha256', (string) ($_SERVER['REMOTE_ADDR'] ?? ''), $config['client_salt']);
    $file = $config['state_dir'] . '/kontakt-grenser.json';
    $handle = @fopen($file, 'c+');
    if ($handle === false || !flock($handle, LOCK_EX)) {
        note('hyppighetsgrensen kunne ikke låses');
        return -1;
    }
    try {
        $state = json_decode((string) stream_get_contents($handle), true);
        $state = is_array($state) ? $state : [];
        $day = array_values(array_filter($state['all'] ?? [], fn ($t) => is_int($t) && $t > $now - 86400));
        $clients = [];
        foreach ($state['clients'] ?? [] as $key => $times) {
            $kept = array_values(array_filter((array) $times, fn ($t) => is_int($t) && $t > $now - (int) $limits['window']));
            if ($kept) {
                $clients[$key] = $kept;
            }
        }
        $mine = $clients[$client] ?? [];
        $wait = 0;
        if (count($mine) >= (int) $limits['per_client']) {
            $wait = max(1, min($mine) + (int) $limits['window'] - $now);
        } elseif (count($day) >= (int) $limits['per_day']) {
            $wait = max(1, min($day) + 86400 - $now);
        } else {
            $mine[] = $now;
            $day[] = $now;
            $clients[$client] = $mine;
        }
        ftruncate($handle, 0);
        rewind($handle);
        fwrite($handle, json_encode(['clients' => $clients, 'all' => $day]));
        fflush($handle);
        return $wait;
    } finally {
        flock($handle, LOCK_UN);
        fclose($handle);
    }
}

function post_form(string $url, array $fields, int $timeout): ?string
{
    $payload = http_build_query($fields);
    if (function_exists('curl_init')) {
        $curl = curl_init($url);
        curl_setopt_array($curl, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $payload,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => $timeout,
            CURLOPT_CONNECTTIMEOUT => $timeout,
            CURLOPT_HTTPHEADER => ['Content-Type: application/x-www-form-urlencoded'],
        ]);
        $result = curl_exec($curl);
        $status = (int) curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
        curl_close($curl);
        return is_string($result) && $status === 200 ? $result : null;
    }
    $context = stream_context_create(['http' => [
        'method' => 'POST',
        'header' => "Content-Type: application/x-www-form-urlencoded\r\n",
        'content' => $payload,
        'timeout' => $timeout,
        'ignore_errors' => false,
    ]]);
    $result = @file_get_contents($url, false, $context);
    return is_string($result) ? $result : null;
}

/** Returnerer null når CAPTCHA er godkjent, ellers en feilkode. */
function verify_captcha(array $captcha, string $token): ?string
{
    if ($token === '') {
        return 'captcha_missing';
    }
    if (strlen($token) > 4096) {
        return 'captcha_rejected';
    }
    // verify_url finnes for testene; i drift brukes leverandørens faste adresse.
    $url = is_string($captcha['verify_url'] ?? null) ? $captcha['verify_url'] : CAPTCHA_PROVIDERS[$captcha['provider']];
    $raw = post_form($url, ['secret' => $captcha['secret'], 'response' => $token,
        'remoteip' => (string) ($_SERVER['REMOTE_ADDR'] ?? ''), 'sitekey' => $captcha['site_key']], 8);
    $result = $raw === null ? null : json_decode($raw, true);
    if (!is_array($result)) {
        note('captcha-leverandøren svarte ikke');
        return 'captcha_unavailable';
    }
    if (($result['success'] ?? false) === true) {
        $expected = $captcha['hostname'] ?? null;
        if (is_string($expected) && ($result['hostname'] ?? null) !== $expected) {
            note('captcha fra feil vertsnavn');
            return 'captcha_rejected';
        }
        return null;
    }
    $codes = array_map('strval', (array) ($result['error-codes'] ?? []));
    if (array_intersect($codes, CAPTCHA_SERVER_FAULT)) {
        note('captcha-oppsettet avvises av leverandøren: ' . implode(',', $codes));
        return 'captcha_unavailable';
    }
    if (array_intersect($codes, CAPTCHA_EXPIRED)) {
        return 'captcha_expired';
    }
    if (array_intersect($codes, CAPTCHA_MISSING)) {
        return 'captcha_missing';
    }
    return 'captcha_rejected';
}

function encoded_header(string $text): string
{
    return '=?UTF-8?B?' . base64_encode($text) . '?=';
}

function compose(array $config, string $email, string $message): array
{
    $domain = substr(strrchr($config['sender'], '@'), 1);
    $name = (string) ($config['sender_name'] ?? 'Bootdisk kontaktskjema');
    $subject = (string) ($config['subject'] ?? 'Melding fra kontaktskjemaet på Bootdisk');
    $when = date('Y-m-d H:i', time()) . ' (serverens tid)';
    $text = $message . "\n\n-- \nSendt fra kontaktskjemaet på Bootdisk " . $when . ".\n"
        . 'Svar går til avsenderens oppgitte adresse: ' . $email . "\n";
    $headers = [
        'From' => encoded_header($name) . ' <' . $config['sender'] . '>',
        'Reply-To' => '<' . $email . '>',
        'MIME-Version' => '1.0',
        'Content-Type' => 'text/plain; charset=UTF-8',
        'Content-Transfer-Encoding' => 'base64',
        'Message-ID' => '<' . bin2hex(random_bytes(12)) . '@' . $domain . '>',
        'Date' => date(DATE_RFC2822, time()),
        'X-Bootdisk-Form' => 'kontakt',
    ];
    return ['subject' => encoded_header($subject), 'headers' => $headers,
        'body' => rtrim(chunk_split(base64_encode($text), 76, "\r\n"))];
}

function send_with_mail(array $config, array $mail): bool
{
    $headers = $mail['headers'];
    unset($headers['Date']);
    $lines = [];
    foreach ($headers as $key => $value) {
        $lines[] = $key . ': ' . $value;
    }
    // Fast konvoluttavsender (-f), slik at returmeldinger og SPF følger avsenderdomenet.
    return mail($config['recipient'], $mail['subject'], $mail['body'], implode("\r\n", $lines), '-f' . $config['sender']);
}

final class SmtpFailure extends RuntimeException
{
}

function smtp_expect($socket, int ...$codes): string
{
    $reply = '';
    while (($line = fgets($socket, 1024)) !== false) {
        $reply .= $line;
        if (strlen($line) < 4 || $line[3] !== '-') {
            break;
        }
    }
    if ($reply === '' || !in_array((int) substr($reply, 0, 3), $codes, true)) {
        throw new SmtpFailure('uventet smtp-svar ' . substr($reply, 0, 3));
    }
    return $reply;
}

function smtp_send($socket, string $line, int ...$codes): string
{
    fwrite($socket, $line . "\r\n");
    return smtp_expect($socket, ...$codes);
}

function send_with_smtp(array $config, array $mail): bool
{
    $t = $config['transport'];
    $security = $t['security'] ?? 'starttls';
    $port = (int) ($t['port'] ?? ($security === 'tls' ? 465 : 587));
    $timeout = (int) ($t['timeout'] ?? 10);
    $tls = ['verify_peer' => true, 'verify_peer_name' => true, 'peer_name' => $t['host']];
    if (is_string($t['ca_file'] ?? null)) {
        $tls['cafile'] = $t['ca_file'];
    }
    $context = stream_context_create(['ssl' => $tls]);
    $scheme = $security === 'tls' ? 'tls://' : 'tcp://';
    $socket = @stream_socket_client($scheme . $t['host'] . ':' . $port, $errno, $error, $timeout,
        STREAM_CLIENT_CONNECT, $context);
    if ($socket === false) {
        note('smtp-tilkobling feilet');
        return false;
    }
    stream_set_timeout($socket, $timeout);
    try {
        $helo = (string) ($t['helo'] ?? substr(strrchr($config['sender'], '@'), 1));
        smtp_expect($socket, 220);
        smtp_send($socket, 'EHLO ' . $helo, 250);
        if ($security === 'starttls') {
            smtp_send($socket, 'STARTTLS', 220);
            if (!stream_socket_enable_crypto($socket, true, STREAM_CRYPTO_METHOD_TLSv1_2_CLIENT | STREAM_CRYPTO_METHOD_TLSv1_3_CLIENT)) {
                throw new SmtpFailure('starttls feilet');
            }
            smtp_send($socket, 'EHLO ' . $helo, 250);
        }
        if (isset($t['username'])) {
            smtp_send($socket, 'AUTH LOGIN', 334);
            smtp_send($socket, base64_encode((string) $t['username']), 334);
            smtp_send($socket, base64_encode((string) ($t['password'] ?? '')), 235);
        }
        smtp_send($socket, 'MAIL FROM:<' . $config['sender'] . '>', 250);
        smtp_send($socket, 'RCPT TO:<' . $config['recipient'] . '>', 250, 251);
        smtp_send($socket, 'DATA', 354);
        $lines = ['To: <' . $config['recipient'] . '>', 'Subject: ' . $mail['subject']];
        foreach ($mail['headers'] as $key => $value) {
            $lines[] = $key . ': ' . $value;
        }
        // Base64-kroppen har aldri en linje som begynner med punktum, så ingen prikk-escaping trengs.
        smtp_send($socket, implode("\r\n", $lines) . "\r\n\r\n" . $mail['body'] . "\r\n.", 250);
        try {
            smtp_send($socket, 'QUIT', 221);
        } catch (SmtpFailure) {
            // Meldingen er allerede godtatt; et ufint farvel endrer ikke det.
        }
        return true;
    } catch (SmtpFailure $failure) {
        note('smtp: ' . $failure->getMessage());
        return false;
    } finally {
        fclose($socket);
    }
}

function public_setup(?array $config): array
{
    if ($config === null) {
        return ['ready' => false];
    }
    return ['ready' => true, 'provider' => $config['captcha']['provider'],
        'site_key' => $config['captcha']['site_key'], 'max_message' => MAX_MESSAGE_CHARS];
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
if ($method === 'GET' || $method === 'HEAD') {
    respond(200, public_setup(load_config()));
}
if ($method !== 'POST') {
    fail(405, 'method_not_allowed', ['Allow: GET, POST']);
}

$config = load_config();
if ($config === null) {
    fail(503, 'not_configured');
}
if (($_SERVER['HTTP_ORIGIN'] ?? '') !== $config['allowed_origin']) {
    fail(403, 'forbidden_origin');
}
$body = read_body();
$email = is_string($body['email'] ?? null) ? trim($body['email']) : '';
$message = is_string($body['message'] ?? null) ? str_replace("\r\n", "\n", trim($body['message'])) : '';
$token = is_string($body['captcha'] ?? null) ? trim($body['captcha']) : '';
if (!valid_mailbox($email)) {
    fail(422, 'invalid_email');
}
if ($message === '' || !mb_check_encoding($message, 'UTF-8')) {
    fail(422, 'invalid_message');
}
if (mb_strlen($message, 'UTF-8') > MAX_MESSAGE_CHARS) {
    fail(422, 'message_too_long');
}

$wait = rate_limit($config);
if ($wait < 0) {
    fail(503, 'not_configured');
}
if ($wait > 0) {
    fail(429, 'rate_limited', ['Retry-After: ' . $wait]);
}

$captcha = verify_captcha($config['captcha'], $token);
if ($captcha !== null) {
    $status = ['captcha_unavailable' => 503, 'captcha_missing' => 422][$captcha] ?? 403;
    fail($status, $captcha);
}

// Felle for roboter: et felt mennesker ikke ser. Svaret er det samme som ved sending.
if (is_string($body['website'] ?? null) && trim($body['website']) !== '') {
    note('fellefelt utfylt, ikke sendt');
    respond(200, ['ok' => true]);
}

$mail = compose($config, $email, $message);
$sent = $config['transport']['type'] === 'smtp' ? send_with_smtp($config, $mail) : send_with_mail($config, $mail);
if (!$sent) {
    note('sending feilet');
    fail(502, 'send_failed');
}
respond(200, ['ok' => true]);
