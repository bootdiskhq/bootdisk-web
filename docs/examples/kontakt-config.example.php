<?php
/* EKSEMPEL. Alle verdier her er oppdiktede plassholdere og virker ikke.
 *
 * Den ekte filen heter kontakt-config.php og ligger på webhotellet utenfor webroten:
 *
 *     /bootdisk-privat/kontakt-config.php      (ved siden av /www, aldri inni)
 *
 * Den skal aldri inn i Git, i en releasepakke eller i en FTP-kopi av /www. api/kontakt.php
 * nekter å bruke en konfig som ligger under webroten. Se docs/kontaktskjema.md. */
return [
    // Fast mottaker. Skjemaet kan ikke sende til noen annen adresse.
    'recipient' => 'kontakt@example.invalid',
    // Fast avsender på eget domene. Leserens adresse brukes bare som Reply-To.
    'sender' => 'skjema@example.invalid',
    'sender_name' => 'Bootdisk kontaktskjema',
    'subject' => 'Melding fra kontaktskjemaet på Bootdisk',

    // Bare innsendinger fra denne adressen godtas (Origin-hodet). Ingen skråstrek på slutten.
    'allowed_origin' => 'https://bootdisk.example',

    // Skrivbar mappe utenfor webroten for hyppighetsgrensen. Lag den før første innsending.
    'state_dir' => '/sti/utenfor/webroten/bootdisk-privat/kontakt-tilstand',
    // Minst 32 tilfeldige tegn, for eksempel fra: php -r 'echo bin2hex(random_bytes(32));'
    'client_salt' => 'BYTT-MEG-plassholder-for-tilfeldig-hemmelighet-0000',
    // Valgfritt. Standard: 3 innsendinger per klient per 10 minutter, 40 totalt per døgn.
    'rate_limit' => ['window' => 600, 'per_client' => 3, 'per_day' => 40],

    'captcha' => [
        // 'turnstile' (Cloudflare) eller 'hcaptcha'.
        'provider' => 'turnstile',
        'site_key' => 'plassholder-offentlig-nokkel',
        'secret' => 'plassholder-hemmelig-nokkel',
        // Valgfritt: krev at leverandøren bekrefter dette vertsnavnet.
        'hostname' => 'bootdisk.example',
    ],

    // Enten PHPs mail() på webhotellet …
    'transport' => ['type' => 'mail'],
    // … eller SMTP med pålogging (passordet står bare her, på serveren):
    // 'transport' => [
    //     'type' => 'smtp',
    //     'host' => 'smtp.example.invalid',
    //     'port' => 587,
    //     'security' => 'starttls',   // 'starttls', 'tls' (port 465) eller 'none' (bare uten pålogging)
    //     'username' => 'skjema@example.invalid',
    //     'password' => 'plassholder-passord',
    // ],
];
