<?php
/* Testruter for `php -S`: /api/besok.php kjører den foreslåtte tellertjenesten, alt annet
 * serveres som statiske filer fra dokumentroten (en bygget release). Bare for testene. */
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
if ($path === '/api/besok.php') {
    require getenv('BOOTDISK_COUNTER_SCRIPT');
    return true;
}
return false;
