# Automatic Commons production delivery

Verified main pushes and manual main dispatches deploy the accepted application
image to the existing NUC service. The native CI job retains formatting, API and
database-tool tests, and rendered SEO checks. It also checks production dependency
advisories and the actual image's health, rendered metadata, icons and uncached
build marker. PRs run those checks without production credentials.

`SOURCE_REVISION` identifies the immutable source commit inside
`/build-info.json`; that response uses `Cache-Control: no-store`. The homepage is
rendered with public database content, so the release marker identifies the build
independently of changes in projects or activity. CI compares the complete marker
bytes, checks public health and compares the selected favicon after activation.

## Host configuration and credentials

The existing single replica, `commons-app`, stays on NUC with `commons_data`, the
backups bind mount, network, ingress, runtime limits and unprivileged user.
Registration is operator-owned under
`/srv/deploy/commons/profile.json`, with its qualified Compose baseline in
`compose.json` beside it. Runtime guards refuse configuration
drift. Keep environment references bound to `/srv/apps/projects/commons/.env`;
never copy its Brevo credential into the baseline, source, CI or image.
The data hook also checks the registered environment-file hash before and after
qualification, so a configuration edit requires a fresh runtime baseline.

Dedicated `HOMELAB_DEPLOY_KEY` and `HOMELAB_KNOWN_HOSTS` secrets invoke a pinned
fleet receiver with only this profile and service `app`. The receiver requires
current main and validates the repository/revision labels. It retains one
accepted image configuration per commit; a retry reuses that image. Key custody
belongs to the homelab operator; initial rotation is due 2027-02-03.

Install `scripts/predeploy-ci.py` from the reviewed merged commit under
`/usr/local/lib/fleet-deploy/commons/<sha256>/`. The profile's fixed
`pre_deploy_command` runs that exact file as root through `sudo -n`, because the
hook hands its checkpoint files to the app container's user, which differs from
the deploy account. If CI arrives before installation, the hook fails before activation; finish
installation and retry the current main job. Preserve the old image and receipts.

## Data qualification before each activation

The hook performs these checks while the receiver holds the app deployment lock:

1. Require identical database initialization code in the live and candidate
   images. A database-changing release needs separate migration admission.
2. Use the live application's native `VACUUM INTO` backup tool, including
   integrity, foreign-key and private-permission checks. The live database and
   its WAL remain under the running application.
3. Back up that snapshot and the native recovery/configuration sources into the
   existing encrypted NUC Restic repository on Kvant. Read the snapshot back and
   require byte identity. The hook runs no retention or deletion commands.
4. Use the candidate image's native restore tool to create a new database in a
   private qualification directory. Require SQLite integrity, identical schema,
   account-record fingerprint and protected table counts.
5. Start the candidate against only that restored copy, with no network or mail
   credentials. Require health and unchanged schema/account/count fingerprints.
   The fixture has an internal lifetime limit and automatic removal, so it also
   expires if its operator process is interrupted.

Snapshots and checkpoints remain mode 0600 under private directories in
`/srv/apps/projects/commons/backups/ci-deploy/`. Off-host snapshots carry `commons`
and `ci-deploy` tags; the existing backup job's host/tag retention grouping keeps
this recovery cohort separate. Its existing timer and retention policy retain
their ownership. Native root backup commands have their own deadline in addition
to the receiver's bounded hook deadline.

The receiver rechecks main and container identity after the hook. A failed check
prevents image activation. It then activates only `app`, checks readiness and
runtime configuration, and retains the previous immutable image for rollback.
No qualification fixture uses or restores over the live database.

## First marker adoption and recovery

The retained pre-CI image has no build marker. First activation must use readiness
checks that can also verify that legacy image: public health, rendered Commons
content and an existing image-backed icon. CI independently requires the new
marker's complete bytes and source revision before accepting the delivery.

After that verified activation, qualify and enable the image-backed marker in
the host profile. Keep its previous profile with the first release's rollback
record. Later normal rollback images also contain markers; emergency recovery to
the legacy image must use its saved legacy-compatible profile and exact receipt
command after checking for newer deployments and host changes.

An image rollback leaves the live database in place. Automatic admission is
limited to the verified compatible initialization/schema. A schema-changing
release uses the native migration and stopped-app restore procedures instead.
Never overwrite a live database or apply an old WAL to a restored snapshot.

Production deployment proves the accepted build, configuration and readiness.
Provider acceptance, inbox delivery, owner moderation and broader community
qualification retain their own evidence; the release check sends no test mail
and creates no public account or activity.
