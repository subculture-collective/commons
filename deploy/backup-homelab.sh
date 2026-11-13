#!/usr/bin/env bash
set -euo pipefail
exec 9>/run/commons-backup.lock
flock -n 9
root=/srv/apps/projects/commons
stamp=$(date -u +%Y%m%dT%H%M%SZ)
snapshot="$root/backups/commons-$stamp.sqlite"
export RESTIC_PASSWORD_FILE=/etc/nuc-router-backup/restic-password
repo=sftp:patrick@10.0.0.50:/mnt/data2/backups/nuc/restic
sftp_args='-i /home/patrick/.ssh/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/.ssh/known_hosts'
docker compose --env-file "$root/.env" -p commons -f "$root/current/compose.yaml" -f "$root/current/deploy/compose.homelab.yaml" exec -T app node scripts/backup.mjs "/backups/commons-$stamp.sqlite"
restic -r "$repo" -o "sftp.args=$sftp_args" backup --tag commons "$snapshot" "$root/.env" "$root/current/compose.yaml" "$root/current/deploy" "$root/operations"
restic -r "$repo" -o "sftp.args=$sftp_args" forget --tag commons --group-by host,tags --keep-daily 7 --keep-weekly 4
# Only local Commons snapshots older than the off-host retention window are removed.
find "$root/backups" -maxdepth 1 -type f -name 'commons-*.sqlite' -mtime +35 -delete
