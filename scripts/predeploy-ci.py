#!/usr/bin/env python3
"""Qualify the accepted Commons image with native private backup/restore tools."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import uuid

APP = "commons-app"
ROOT = Path("/srv/apps/projects/commons")
STATE = Path("/srv/deploy/commons/state")
REPOSITORY = "https://git.subcult.tv/subculture-collective/commons"
RESTIC = "sftp:patrick@10.0.0.50:/mnt/data2/backups/nuc/restic"
SFTP = "-i /home/patrick/.ssh/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/.ssh/known_hosts -o ServerAliveInterval=10 -o ServerAliveCountMax=2"


def run(args, *, timeout=35, output=None):
    result = subprocess.run(args, stdout=output or subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        raise RuntimeError("A qualification command failed; inspect the private checkpoint")
    return result.stdout


def inspect(name, kind="container"):
    return json.loads(run(["docker", kind, "inspect", name]))[0]


def fingerprint(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as database:
        assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not database.execute("PRAGMA foreign_key_check").fetchall()
        schema = database.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        users = hashlib.sha256()
        for row in database.execute("SELECT * FROM users ORDER BY id"):
            users.update(json.dumps(row).encode() + b"\n")
        tables = {row[1] for row in schema if row[0] == "table"}
        counts = {name: database.execute('SELECT count(*) FROM "' + name + '"').fetchone()[0]
                  for name in ("users", "projects", "messages", "memberships", "bookmarks", "reports") if name in tables}
        return {"schema": hashlib.sha256(json.dumps(schema).encode()).hexdigest(),
                "users": users.hexdigest(), "counts": counts}


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.digest()


def restic(args, *, output=None):
    return run(["sudo", "-n", "/usr/bin/env",
                "RESTIC_PASSWORD_FILE=/etc/nuc-router-backup/restic-password",
                "/usr/bin/timeout", "--signal=TERM", "--kill-after=5s", "25s",
                "/usr/bin/restic", "-r", RESTIC, "-o", "sftp.args=" + SFTP, *args],
               timeout=32, output=output)


def qualify(image, revision):
    os.umask(0o077)
    assert re.fullmatch(r"[0-9a-f]{40}", revision)
    registration = json.loads((STATE / "registration.json").read_text())
    assert file_hash(ROOT / ".env").hex() == registration["env_file_sha256"], "Configuration changed; requalify the runtime baseline"
    current = inspect(APP)
    candidate = inspect(image, "image")
    assert candidate["Config"]["Labels"]["org.opencontainers.image.revision"] == revision
    assert candidate["Config"]["Labels"]["org.opencontainers.image.source"] == REPOSITORY
    image = candidate["Id"]
    # Automatic image rollback requires the same database initialization code.
    # A migration-changing release needs its separate reviewed admission.
    old_db = run(["docker", "exec", APP, "cat", "/app/server/db.js"])
    new_db = run(["docker", "run", "--rm", "--network", "none", "--read-only",
                  "--tmpfs", "/data:uid=1000,gid=1000,mode=0700", "--entrypoint", "cat",
                  image, "/app/server/db.js"])
    assert old_db == new_db, "Database initialization changed; separate migration admission required"
    assert next(m for m in current["Mounts"] if m["Destination"] == "/backups")["Source"] == str(ROOT / "backups")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
    directory = ROOT / "backups/ci-deploy" / (revision + "-" + stamp)
    # Runs as root (sudo): hand checkpoint paths to the container user, as the
    # unprivileged deploy account owned them when it shared the container UID.
    owner = tuple(int(run(["docker", "exec", APP, "id", flag])) for flag in ("-u", "-g"))
    directory.mkdir(parents=True, mode=0o700)
    os.chown(directory, *owner)
    checkpoint = {"revision": revision, "image": candidate["Id"], "previous_image": current["Image"], "stage": "backup"}
    record = directory / "qualification.json"
    def save(stage):
        checkpoint["stage"] = stage
        record.write_text(json.dumps(checkpoint, indent=2) + "\n")
    save("backup")
    source = directory / "backup.sqlite"
    run(["docker", "exec", APP, "node", "scripts/backup.mjs",
         "/backups/" + str(source.relative_to(ROOT / "backups"))])
    assert source.stat().st_mode & 0o777 == 0o600
    original = fingerprint(source)
    save("encrypted-offhost-backup")
    paths = [source, ROOT / ".env", ROOT / "current/compose.yaml", ROOT / "current/deploy", ROOT / "operations"]
    paths += [path for path in [Path("/srv/deploy/commons/profile.json"),
                               Path("/srv/deploy/commons/compose.json"), Path(__file__)] if path.exists()]
    events = restic(["backup", "--json", "--tag", "commons", "--tag", "ci-deploy", *map(str, paths)])
    summary = next(json.loads(line) for line in events.splitlines() if json.loads(line).get("message_type") == "summary")
    snapshot = summary["snapshot_id"]
    assert re.fullmatch(r"[0-9a-f]{8,64}", snapshot)
    checkpoint["offhost_snapshot"] = snapshot
    recovered = directory / "offhost-restored.sqlite"
    with recovered.open("xb") as output:
        restic(["dump", snapshot, str(source)], output=output)
    os.chown(recovered, *owner)
    assert file_hash(source) == file_hash(recovered)
    save("isolated-native-restore")
    restored = directory / "restored/commons.sqlite"
    restored.parent.mkdir(mode=0o700)
    os.chown(restored.parent, *owner)
    common = ["docker", "run", "--rm", "--network", "none", "--read-only",
              "--tmpfs", "/tmp:uid=1000,gid=1000,mode=1777,size=32m",
              "--mount", "type=bind,src=" + str(recovered) + ",dst=/backup.sqlite,readonly",
              "--mount", "type=bind,src=" + str(restored.parent) + ",dst=/data"]
    run(common + ["--entrypoint", "node", image, "scripts/restore.mjs",
                  "/backup.sqlite", "/data/commons.sqlite", "--app-stopped"])
    assert fingerprint(restored) == original
    save("isolated-candidate-startup")
    name = "commons-ci-qualification-" + uuid.uuid4().hex[:12]
    cid = run(["docker", "create", "--rm", "--name", name, "--network", "none", "--read-only", "--init",
               "--tmpfs", "/tmp:uid=1000,gid=1000,mode=1777,size=32m",
               "--mount", "type=bind,src=" + str(restored.parent) + ",dst=/data",
               "--memory", "512m", "--cpus", "1", "--pids-limit", "160",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
               "-e", "PUBLIC_URL=https://commons.subcult.tv", "-e", "OPERATOR_NAME=Qualification fixture",
               "-e", "CONTACT_EMAIL=qualification@example.invalid", "-e", "TRUST_PROXY=0",
               "-e", "BREVO_API_KEY=", "-e", "BREVO_SENDER_EMAIL=",
               "--entrypoint", "/usr/bin/timeout", image, "--signal=TERM", "--kill-after=5s", "70s",
               "node", "server/index.js"]).decode().strip()
    assert re.fullmatch(r"[0-9a-f]{64}", cid)
    checkpoint["fixture_container"] = cid
    try:
        run(["docker", "start", cid])
        for attempt in range(15):
            healthy = subprocess.run(["docker", "exec", cid, "node", "scripts/healthcheck.mjs"], capture_output=True)
            if healthy.returncode == 0:
                break
            time.sleep(0.3)
        assert healthy.returncode == 0, "Isolated restored candidate did not become ready"
        assert fingerprint(restored) == original, "Candidate changed schema, account records or protected row counts"
        assert inspect(APP)["Id"] == current["Id"] and inspect(APP)["Image"] == current["Image"]
        assert file_hash(ROOT / ".env").hex() == registration["env_file_sha256"]
        checkpoint.update(result="qualified", schema_accounts_counts="PASS", offhost_byte_exact_restore="PASS", provider_network="disabled")
        save("complete")
        print(json.dumps({key: checkpoint[key] for key in ["result", "revision", "image", "offhost_snapshot", "schema_accounts_counts", "offhost_byte_exact_restore"]}))
    finally:
        subprocess.run(["docker", "rm", "-f", cid], capture_output=True)


def main():
    revision = run(["git", "ls-remote", "--exit-code", REPOSITORY + ".git", "refs/heads/main"]).decode().split()[0]
    qualify("fleet-deploy/commons/app:" + revision, revision)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Commons pre-deployment qualification refused activation; inspect its private backup checkpoint") from None
