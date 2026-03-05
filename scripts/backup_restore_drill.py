#!/usr/bin/env python
import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rh_backup_drill_") as tmp:
        root = Path(tmp)
        src = root / "source.db"
        restored = root / "restored.db"
        backups = root / "backups"
        backups.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(src.as_posix())
        conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO records (value) VALUES ('alpha'), ('beta'), ('gamma')")
        conn.commit()
        conn.close()

        db_url = f"sqlite:///{src.as_posix()}"
        backup_cmd = [
            "python",
            "scripts/db_backup.py",
            "--database-url",
            db_url,
            "--out-dir",
            backups.as_posix(),
            "--label",
            "drill",
        ]
        subprocess.run(backup_cmd, check=True)

        manifest = backups / "drill.manifest.json"
        backup_file = backups / "drill.sqlite3"
        restore_cmd = [
            "python",
            "scripts/db_restore.py",
            "--database-url",
            f"sqlite:///{restored.as_posix()}",
            "--backup-file",
            backup_file.as_posix(),
            "--manifest-file",
            manifest.as_posix(),
            "--force",
        ]
        subprocess.run(restore_cmd, check=True)

        verify_conn = sqlite3.connect(restored.as_posix())
        count = int(verify_conn.execute("SELECT COUNT(*) FROM records").fetchone()[0])
        verify_conn.close()
        if count != 3:
            raise RuntimeError(f"Drill failed: expected 3 rows, found {count}")

        print(json.dumps({"status": "ok", "restored_rows": count}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
