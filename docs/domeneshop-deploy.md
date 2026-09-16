# Domeneshop deploy and rollback

Bootdisk Web is a static release. Deploy the contents of the generated `bootdisk-web-<version>/` directory, not the directory itself, to the web root.

## Connection

- Server: `ftp.domeneshop.no`
- Port: `21`
- Mode: passive FTP
- User: `bootdisk`
- Remote directory: `/www`

The password stays in the operator's password manager or FTP client. It must never be committed, pasted into a script, or stored in a release report.

## Deploy

1. Run `build-release-artifact.py` and retain its ZIP and JSON report.
2. Compare the ZIP SHA-256 with the report before upload.
3. Download the current `/www` contents as a timestamped rollback copy.
4. Upload the new release contents to `/www`, preserving the `data/` and `store/` hierarchy.
5. Remove files that are not present in the new closed release directory. Otherwise deleted entries or old assets can remain publicly reachable.
6. Run the deployment verifier:

   ```sh
   python scripts/verify-deployment.py https://bootdisk.no/ --expected-entries 39
   ```

7. Visually check the archive overview and K37 on both narrow and wide screens.

Do not promote a release when the verifier reports a missing document, unexpected entry count, HTTP failure, or content-hash mismatch.

## Rollback

1. Stop uploading the failed release.
2. Replace `/www` with the complete timestamped rollback copy; do not mix files from two versions.
3. Run the same deployment verifier.
4. Record the failed release hash and observed defect before attempting a corrected build.

Rollback uses a previously verified complete release, not ad-hoc edits on the server. Archive facts and media are always rebuilt from Ingest, Catalog and Publish inputs.
