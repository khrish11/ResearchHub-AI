#!/usr/bin/env python
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


def _resolve_database_url(explicit: str | None) -> str:
    value = explicit or os.getenv("DATABASE_URL", "")
    if not value:
        raise RuntimeError("DATABASE_URL is required (arg or env).")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_path(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise RuntimeError("Not a sqlite URL.")
    raw = parsed.path or ""
    if raw.startswith("/") and len(raw) >= 3 and raw[2] == ":":
        raw = raw[1:]
    return Path(unquote(raw)).resolve()


def _restore_sqlite(database_url: str, backup_file: Path, force: bool) -> dict:
    target = _sqlite_path(database_url)
    if not force and target.exists():
        raise RuntimeError(f"Target database exists: {target}. Use --force to overwrite.")

    target.parent.mkdir(parents=True, exist_ok=True)
    prior_backup = None
    if target.exists():
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        prior_backup = target.with_suffix(target.suffix + f".pre_restore_{suffix}.bak")
        shutil.copy2(target, prior_backup)

    shutil.copy2(backup_file, target)
    return {
        "restored_to": target.as_posix(),
        "restored_from": backup_file.as_posix(),
        "target_sha256": _sha256(target),
        "pre_restore_backup": prior_backup.as_posix() if prior_backup else None,
    }


def _restore_postgres(database_url: str, backup_file: Path, force: bool) -> dict:
    command = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--dbname", database_url, backup_file.as_posix()]
    if not force:
        command.insert(1, "--single-transaction")
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "pg_restore failed: "
            + (completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}")
        )
    return {
        "restored_to": database_url,
        "restored_from": backup_file.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore database from backup file.")
    parser.add_argument("--database-url", dest="database_url", default=None)
    parser.add_argument("--backup-file", dest="backup_file", required=True)
    parser.add_argument("--manifest-file", dest="manifest_file", default=None)
    parser.add_argument("--force", action="store_true", default=False)
    args = parser.parse_args()

    database_url = _resolve_database_url(args.database_url).strip()
    backup_file = Path(args.backup_file).resolve()
    if not backup_file.exists():
        raise RuntimeError(f"Backup file not found: {backup_file}")

    if args.manifest_file:
        manifest_file = Path(args.manifest_file).resolve()
        if not manifest_file.exists():
            raise RuntimeError(f"Manifest file not found: {manifest_file}")
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        expected_hash = str(manifest.get("sha256", "")).strip().lower()
        if expected_hash:
            actual_hash = _sha256(backup_file).lower()
            if actual_hash != expected_hash:
                raise RuntimeError("Backup checksum mismatch; restore aborted.")

    if database_url.startswith("sqlite:///"):
        result = _restore_sqlite(database_url, backup_file, args.force)
    elif database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        result = _restore_postgres(database_url, backup_file, args.force)
    else:
        raise RuntimeError("Unsupported DATABASE_URL. Supported: sqlite, postgresql.")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Restore failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
