# Host access and recovery

Prepared for one **new Ubuntu 24.04** OVH VPS. These files have not been applied
to a server. They do not establish a successful deployment, backup or restore.

## Access

Use an SSH key created and retained on the operator's Mac. Add only its public
key to the VPS's existing non-root `ubuntu` account. Verify the host fingerprint
against the OVH console, then prove a second key-only SSH login works while the
first session stays open. Never paste a private key or account password into chat.

On that fresh VPS, from the reviewed checkout:

```bash
sudo bash deploy/ovh/host/prepare-host.sh ubuntu --key-login-confirmed
```

The script installs Docker/Compose from Docker's official Ubuntu repository,
enables key-only SSH, denies root SSH, allows inbound SSH/HTTP/HTTPS, and installs
security updates without automatic reboot. It refuses existing containers,
application listeners and conflicting container packages on an unprepared host.
It does not add users to the root-equivalent Docker group. Keep the first session
open and test another login after hardening. Keep OVH console/recovery access.
OVH account MFA should be enabled by its owner.

Docker published ports bypass UFW. The Compose configuration must publish only
the proxy's 80/443; PostgreSQL, Redis, the API and frontend stay on its private
network. Confirm this on the actual host and from an external machine.

## Application backups

The included OVH standard daily backup is a provider VM recovery layer. It does
not prove application-consistent recovery, and copies in the same provider/data
center are not an independent off-server destination controlled by us.

Create an `age` identity on the Mac, keep it in the Mac's protected credentials
backup, and copy **only its public recipient** to
`/etc/boomsay/backup-recipient.txt` on the VPS (root-owned mode600).

```bash
# Mac, with age installed from Homebrew if needed:
umask 077
mkdir -p "$HOME/.config/boomsay"
chmod 700 "$HOME/.config/boomsay"
age-keygen -o "$HOME/.config/boomsay/backup-identity.txt"
```

The private identity must never go to the VPS, Git, chat or a shared file store.
The environment file is `/etc/boomsay/boomsay.env`, root-owned mode600. Once the
full deployment and PostgreSQL are healthy:

```bash
sudo bash /opt/boomsay/current/deploy/ovh/host/backup.sh
# After verifying the first archive and planning the off-server copy:
sudo bash /opt/boomsay/current/deploy/ovh/host/backup.sh install-timer
sudo systemctl list-timers boomsay-backup.timer
sudo journalctl -u boomsay-backup.service
```

Backups contain a consistent custom-format `pg_dump`, the environment including
the LLM encryption key, source commit, time and scope. Plaintext staging is
root-only and removed at exit. Encryption uses the Mac's public recipient;
seven successful archives are retained. Failed dumps/encryption exit nonzero
and do not prune previous backups. Timer failures appear in the system journal;
no email or continuous external monitoring is configured.

Redis queue/scheduler state and TLS volumes are excluded from these application
archives. Redis AOF and the provider's VM backup protect separate operational
state. After recovery, reconcile pending jobs and keep deliveries disabled until
reviewed; do not replay a stale queue blindly.

## Off-server copy and restore drill

**Still pending:** choosing and verifying a regular off-server destination. A
protected Mac copy via the operator's existing SSH account avoids a new monthly
storage charge. A host-local backup alone is not accepted as off-server backup.
For a manual pull, run on the Mac after obtaining the actual server address:

```bash
umask 077
# Replace ubuntu@SERVER with the operator and actual server address.
ssh ubuntu@SERVER "sudo -n bash -c 'cd /var/backups/boomsay && exec tar -cf - boomsay-*.tar.age boomsay-*.tar.age.sha256'" > boomsay-encrypted-backups.tar.partial && mv boomsay-encrypted-backups.tar.partial boomsay-encrypted-backups.tar
# Extract in a private Mac folder, verify sha256, then decrypt a chosen archive:
shasum -a 256 -c CHOSEN.tar.age.sha256
age --decrypt -i "$HOME/.config/boomsay/backup-identity.txt" CHOSEN.tar.age > recovery.tar
```

Do not expose decrypted `boomsay.env` or overwrite the current installation.
The pull uses the standard Ubuntu operator's noninteractive sudo access. If sudo
requires a password, it stops; arrange an operator-controlled encrypted-file
copy rather than putting a password in the command. The filename globs include
only encrypted archives/checksums, never the temporary plaintext staging folder.
For the server restore drill, copy only the trusted decrypted database dump to
a root-owned mode600 path, then run:

```bash
sudo bash /opt/boomsay/current/deploy/ovh/host/restore-check.sh /protected/database.dump
```

This restores into a uniquely named **new database** and retains it on success or
failure. Compare record counts and known survey answers/chats with the source;
then test an isolated app against it with delivery/model keys disabled. The
script never drops databases or volumes. Remove the retained verification
database only after explicit operator review. A format-list check is not a
restore test; no successful real restore is claimed by this preparation.

## Verification scope

Before accepting hosting: verify key-only access, effective SSH settings, open
ports, TLS, full application workflows, actual RAM/CPU/disk usage, worker jobs,
restarts/persistence, daily timer, encrypted off-server copy, and a restore drill.
The 4GB fit must be measured; configured limits do not establish capacity.

Run `python3 deploy/ovh/host/verify_preparation.py` for bounded preparation
checks. They verify unchanged non-root refusals and shell syntax, then use an
isolated fixture copy and fake Docker/age transport to exercise retention and
dump/encryption failures. Twelve checks passed in preparation. This is not a
test of the root host changes, actual age encryption, Docker, pg_dump or restore.
Failed live verification must remain a failed gate; do not infer it from these
fixture results. The recovery drill compares aggregate core-table counts with
the current app; concurrent writes can cause a legitimate difference. Review
known record contents too before accepting recovery.

Official references read during preparation:

- https://docs.docker.com/engine/install/ubuntu/
- https://docs.docker.com/engine/network/packet-filtering-firewalls/
- https://www.postgresql.org/docs/16/app-pgdump.html
- https://github.com/FiloSottile/age
