# Backup & Restore (plain-English guide)

This folder contains the small sidecar container that copies your trading bot's
data to Nextcloud every night and the tool that puts that data back if
something goes wrong.

The container runs `backup.sh`. It:

1. Takes a **consistent snapshot** of the live trading database (using SQLite's
   own backup command, so a trade happening at that exact moment cannot corrupt
   the copy), plus your logs and market data.
2. Packs everything into one `.tar.gz` archive.
3. **Encrypts** the archive with `age` so that nobody — including Nextcloud —
   can read it without your private key.
4. Checks that the encrypted file is valid, records its SHA256 fingerprint and
   writes a small `manifest.json` describing what is inside (timestamps, sizes,
   which database method was used, the fingerprint, and the *public* key used).
   The manifest never contains passwords or private keys.
5. Uploads both the archive and the manifest to
   `nextcloud:backups/daily/` and then deletes its local copies. If the upload
   fails, **nothing is deleted** — the files are kept under
   `/tmp/backup/failed/` so they can be retried or inspected.
6. Optionally proves the backup can be decrypted again — but only if the age
   **private** key is available to the container. If it is not, the log says
   `RESTORE-VERIFICATION SKIPPED` and you should treat that as a known risk.

Files on Nextcloud look like:

```
backup_20240315_030000.tar.gz.age      <- the encrypted backup
backup_20240315_030000.manifest.json   <- what is inside + fingerprint
```

Backups older than `BACKUP_RETENTION_DAILY` days (default 30) are deleted
automatically.

## Restoring

`restore.sh` lists backups, downloads one, checks its fingerprint, decrypts it
with the age private key, extracts it and then runs SQLite's own
`PRAGMA integrity_check` on every restored database before telling you whether
the data is good.

```bash
# What backups do I have?
/app/restore.sh --list

# Put the newest one into /tmp/restore-drill
/app/restore.sh --latest --dest /tmp/restore-drill --identity /run/secrets/age_identity

# Or a specific one
/app/restore.sh --archive backup_20240315_030000.tar.gz.age \
                --dest /tmp/restore-drill \
                --identity /run/secrets/age_identity
```

Safety rules built in:

* It **refuses to write into a folder that already has files in it** unless you
  add `--force`.
* The downloaded archive must match the fingerprint in its manifest, otherwise
  the restore stops.
* Restored data lands **inside** the destination folder, keeping the original
  layout — e.g. `--dest /tmp/restore-drill` gives you
  `/tmp/restore-drill/data/freqtrade/…` and `/tmp/restore-drill/data/logs/…`.
  Restoring with `--dest /` puts the files back exactly where they came from.

## Quarterly restore drill (please actually do this)

A backup nobody has ever restored is not a backup. Once every three months:

1. **Check the backups exist.**
   ```bash
   docker exec -it kraken-backup /app/restore.sh --list
   ```
   Look at the dates — there should be one per day, and the newest should be
   from this morning.

2. **Restore the newest backup into a scratch folder** (this does not touch the
   running bot). Run it from the folder that contains `docker-compose.yml`:
   ```bash
   mkdir -p /tmp/restore-drill
   docker compose run --rm \
     -v /tmp/restore-drill:/restore \
     -v "$PWD/secrets/age_identity:/run/secrets/age_identity:ro" \
     --entrypoint /app/restore.sh \
     backup --latest --dest /restore --identity /run/secrets/age_identity --force
   ```

3. **Read the report.** You must see:
   * `Checksum : VERIFIED against manifest`
   * `SQLite databases : PASSED (1 database(s) checked with PRAGMA integrity_check)`
   * `Result : OK - the backup extracted successfully and checks passed.`

   Anything else, or the words `RESTORE-VERIFICATION SKIPPED` in the log, means
   the backup must not be trusted — fix the problem *before* you need it.

4. **Peek at the data.**
   ```bash
   ls -R /tmp/restore-drill/data/freqtrade | head
   sqlite3 /tmp/restore-drill/data/freqtrade/tradesv3.sqlite "SELECT COUNT(*) FROM trades;"
   ```

5. **Clean up.**
   ```bash
   rm -rf /tmp/restore-drill
   ```

6. **Write the date of the drill** in your own notes/calendar, then schedule the
   next one for three months later.

If you have no internet access to Nextcloud, you can still drill: download an
`.age` file and its `.manifest.json` into a folder and use
`--local-dir <folder>` with `--archive`/`--latest`.

## Recovering from a real disaster

1. Stop the bot (`docker compose stop` or scale the services to 0) so nothing is
   writing to the data volume.
2. Run a restore into a scratch folder as in step 2 above and read the report.
3. Only if the report is `OK`, copy the restored data back over the live volume
   (or restore with `--dest / --force` from a container that has the data volume
   mounted).
4. Start the bot again and check the log for errors.

## The age private key — read this twice

Backups are encrypted with an age **public** key (`age1…`), which is safe to
keep on the server in `secrets/backup_encrypt_key.txt`. Decrypting requires the
matching age **secret** key (`AGE-SECRET-KEY-1…`).

**If the private key is lost, the backups are permanently unreadable.** There is
no recovery, no support line, and no back door — that is the point of the
encryption. Losing the key is exactly as bad as having no backups at all.

So keep the private key:

* in your password manager, as a secure note (copy the whole file contents,
  including the `AGE-SECRET-KEY-1…` line), **and**
* on an offline copy (printed in a safe, or on an encrypted USB stick kept
  somewhere else), **and**
* never in the repository, never in Nextcloud next to the backups, never in a
  chat message or ticket.

Rules of thumb:

* The private key file can be mounted read-only at `/run/secrets/age_identity`
  (or passed with `--identity`). It is only ever used to *test* and to
  *restore* — never to create a backup.
* Check at least once a year that the copy in your password manager actually
  decrypts a backup (the quarterly drill does this).
* If you ever suspect the private key leaked, generate a new age key pair, put
  the new public key in `secrets/backup_encrypt_key.txt`, and keep the old
  private key anyway — old backups can only be read with the old key.

## Useful settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `BACKUP_SCHEDULE` | `0 3 * * *` | Daily run time (minute hour, UTC unless `TZ` set) |
| `BACKUP_RETENTION_DAILY` | `30` | Days of backups kept on Nextcloud |
| `BACKUP_REMOTE_DIR` | `nextcloud:backups/daily` | Where archives are uploaded |
| `BACKUP_RUN_ONCE` | `0` | `1` = back up once and exit (handy with cron) |
| `BACKUP_SOURCE_DIRS` | `/data/freqtrade:/data/logs` | Folders to back up, colon-separated (mainly for testing) |
| `BACKUP_ENCRYPT_KEY_FILE` | `/run/secrets/backup_encrypt_key` | File with the age **public** key |
| `BACKUP_AGE_IDENTITY_FILE` | `/run/secrets/age_identity` | Optional age **private** key, enables self-verification |
| `NEXTCLOUD_URL_FILE` / `NEXTCLOUD_USER_FILE` / `NEXTCLOUD_PASS_FILE` | `/run/secrets/…` | Nextcloud credentials |

**Never put credentials or keys in environment variables** — this sidecar reads
them from Docker Swarm secret files only.

## Logs

Everything is written to stdout and to `/app/logs/backup.log`. Secret values are
never logged; the log only records that a secret *file* was found. Grep for
`ERROR`, `WARNING`, `RESTORE-VERIFICATION` and `SKIPPED` when reviewing a run.
