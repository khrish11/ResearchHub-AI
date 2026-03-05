#!/usr/bin/env python
import argparse
import hashlib
import json
import os
import sqlite3
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


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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
    resolved = Path(unquote(raw)).resolve()
    return resolved


def _backup_sqlite(database_url: str, out_dir: Path, label: str) -> tuple[Path, dict]:
    source = _sqlite_path(database_url)
    if not source.exists():
        raise RuntimeError(f"SQLite database not found: {source}")

    out_file = out_dir / f"{label}.sqlite3"
    temp_file = out_dir / f"{label}.tmp.sqlite3"
    if temp_file.exists():
        temp_file.unlink()

    src_conn = sqlite3.connect(source.as_posix())
    dst_conn = sqlite3.connect(temp_file.as_posix())
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    temp_file.replace(out_file)
    manifest = {
        "type": "sqlite",
        "database_url": database_url,
        "source_file": source.as_posix(),
        "backup_file": out_file.name,
        "size_bytes": out_file.stat().st_size,
        "sha256": _sha256(out_file),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return out_file, manifest


def _backup_postgres(database_url: str, out_dir: Path, label: str) -> tuple[Path, dict]:
    out_file = out_dir / f"{label}.dump"
    command = ["pg_dump", "--format=custom", "--file", out_file.as_posix(), database_url]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "pg_dump failed: "
            + (completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}")
        )
    manifest = {
        "type": "postgresql",
        "database_url": database_url,
        "backup_file": out_file.name,
        "size_bytes": out_file.stat().st_size,
        "sha256": _sha256(out_file),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return out_file, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create database backup with manifest + checksum.")
    parser.add_argument("--database-url", dest="database_url", default=None)
    parser.add_argument("--out-dir", dest="out_dir", default="backups")
    parser.add_argument("--label", dest="label", default=None)
    args = parser.parse_args()

    database_url = _resolve_database_url(args.database_url).strip()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    label = args.label or f"backup_{_timestamp()}"

    if database_url.startswith("sqlite:///"):
        backup_file, manifest = _backup_sqlite(database_url, out_dir, label)
    elif database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        backup_file, manifest = _backup_postgres(database_url, out_dir, label)
    else:
        raise RuntimeError("Unsupported DATABASE_URL. Supported: sqlite, postgresql.")

    manifest_path = out_dir / f"{label}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"backup_file": backup_file.as_posix(), "manifest_file": manifest_path.as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
