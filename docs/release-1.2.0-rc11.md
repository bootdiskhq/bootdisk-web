# Rc11: revalidate public curation data

After rc10, Firefox could show a cached pending search result while the detail page showed an identified entry. Private browsing showed the current data. Public JSON requests previously used the browser's default cache policy and the hosting response had no explicit Cache-Control header.

Archive, detail, front-page and collection JSON loaders now use cache: no-cache, allowing cached bytes but requiring server validation before reuse. HTML references to changed scripts have a new query version so existing cached scripts are not reused after loading the updated page. This does not refresh an already-open page automatically; one normal reload is needed after deployment.

The data, images and RTF files are byte-identical to rc10. A Node regression check exercises the real loaders' request options and fails against rc10. It does not emulate Firefox's HTTP cache; the original symptom was confirmed by the user's normal/private-window comparison.
