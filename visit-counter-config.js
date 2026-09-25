/* Aktivering av besøkstelleren. Produksjonsaktivering er BLOKKERT: det er ikke dokumentert at
 * bootdisk.no-hostingen kan kjøre counter/besok.php med vedvarende lagring utenfor /www.
 * Se «Før aktivering» i docs/visit-counter.md. Med `endpoint: null` gjør siden ingen forespørsel
 * og viser ikke telleren. */
window.BOOTDISK_VISIT_COUNTER = Object.freeze({ origin: "https://bootdisk.no", endpoint: null });
