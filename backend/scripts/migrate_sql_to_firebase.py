from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from dotenv import load_dotenv
from google.cloud import firestore
from google.oauth2 import service_account
from sqlalchemy import create_engine
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(dotenv_path=BACKEND_DIR / ".env", override=False)
load_dotenv(override=False)
from utils.secret_manager import bootstrap_secret_manager_env  # noqa: E402
bootstrap_secret_manager_env()

from models import (  # noqa: E402
    Chat,
    DataRightsRequest,
    Paper,
    SearchHistory,
    User,
    UserSessionState,
    Workspace,
    WorkspaceDocument,
    WorkspaceFile,
)


@dataclass(frozen=True)
class MigrationTarget:
    collection: str
    model: Any
    counter_key: str | None = None


TARGETS: Dict[str, MigrationTarget] = {
    "users": MigrationTarget("users", User, "user_id"),
    "workspaces": MigrationTarget("workspaces", Workspace, "workspace_id"),
    "papers": MigrationTarget("papers", Paper, "paper_id"),
    "chats": MigrationTarget("chats", Chat, "chat_id"),
    "search_history": MigrationTarget("search_history", SearchHistory, "search_history_id"),
    "user_session_state": MigrationTarget("user_session_state", UserSessionState, "session_state_id"),
    "workspace_documents": MigrationTarget("workspace_documents", WorkspaceDocument, "workspace_document_id"),
    "workspace_files": MigrationTarget("workspace_files", WorkspaceFile, "workspace_file_id"),
    "data_rights_requests": MigrationTarget("data_rights_requests", DataRightsRequest, "data_rights_request_id"),
}


def _resolve_sqlite_url(raw_url: str) -> str:
    if raw_url.startswith("sqlite:///./"):
        rel = raw_url.replace("sqlite:///./", "", 1)
        abs_path = (BACKEND_DIR / rel).resolve()
        return f"sqlite:///{abs_path.as_posix()}"
    if raw_url.startswith("sqlite:///"):
        raw_path = raw_url.replace("sqlite:///", "", 1)
        path_obj = Path(raw_path)
        is_windows_abs = len(raw_path) > 2 and raw_path[1:3] in {":\\", ":/"}
        if path_obj.is_absolute() or is_windows_abs:
            return raw_url
        abs_path = (BACKEND_DIR / raw_path).resolve()
        return f"sqlite:///{abs_path.as_posix()}"
    return raw_url


def resolve_sql_url(explicit: str | None) -> str:
    raw = (explicit or os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return f"sqlite:///{(BACKEND_DIR / 'researchhub.db').resolve().as_posix()}"
    return _resolve_sqlite_url(raw)


_ENV_ESCAPE_REVERSE = {
    "\a": "a",
    "\b": "b",
    "\f": "f",
    "\n": "n",
    "\r": "r",
    "\t": "t",
    "\v": "v",
}


def _normalize_windows_env_path(raw_value: str | None) -> str | None:
    value = (raw_value or "").strip().strip('"').strip("'")
    if not value:
        return None
    rebuilt: List[str] = []
    for ch in value:
        if ch in _ENV_ESCAPE_REVERSE:
            rebuilt.append("\\" + _ENV_ESCAPE_REVERSE[ch])
        else:
            rebuilt.append(ch)
    normalized = "".join(rebuilt)
    if len(normalized) > 2 and normalized[1] == ":":
        normalized = normalized.replace("\\", "/")
    return normalized


def resolve_firebase_config(
    explicit_project_id: str | None,
    explicit_credentials_path: str | None,
) -> tuple[str | None, str | None]:
    project_id = (explicit_project_id or os.getenv("FIREBASE_PROJECT_ID") or "").strip() or None
    credentials_path = _normalize_windows_env_path(
        explicit_credentials_path or os.getenv("FIREBASE_CREDENTIALS_PATH"),
    )
    google_application_credentials = _normalize_windows_env_path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    if not credentials_path and not google_application_credentials:
        raise SystemExit(
            "Set FIREBASE_CREDENTIALS_PATH or GOOGLE_APPLICATION_CREDENTIALS before running Firebase migration.",
        )
    return project_id, credentials_path or google_application_credentials


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate SQLAlchemy-backed Soyog AI data into Firestore collections.",
    )
    parser.add_argument(
        "--collections",
        nargs="+",
        default=list(TARGETS.keys()),
        choices=list(TARGETS.keys()),
        help="Collections/tables to migrate.",
    )
    parser.add_argument("--sql-url", help="Override DATABASE_URL for the SQL source.")
    parser.add_argument("--firebase-project-id", help="Override FIREBASE_PROJECT_ID for Firestore.")
    parser.add_argument("--firebase-credentials-path", help="Override FIREBASE_CREDENTIALS_PATH for Firestore.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned counts without writing to Firestore.")
    parser.add_argument(
        "--drop-target",
        action="store_true",
        help="Delete target collection contents before migrating selected collections.",
    )
    parser.add_argument(
        "--skip-counters",
        action="store_true",
        help="Skip seeding Firestore _counters from max SQL IDs.",
    )
    return parser.parse_args()


def build_session(sql_url: str):
    engine = create_engine(
        sql_url,
        connect_args={"check_same_thread": False} if "sqlite" in sql_url else {},
    )
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def serialize_sqlalchemy_row(instance: Any) -> Dict[str, Any]:
    mapper = sa_inspect(instance.__class__)
    data: Dict[str, Any] = {}
    for attr in mapper.column_attrs:
        key = attr.key
        value = getattr(instance, key)
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        data[key] = value
    return data


def load_rows(session, targets: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {}
    for name in targets:
        target = TARGETS[name]
        rows = session.query(target.model).all()
        result[name] = [serialize_sqlalchemy_row(row) for row in rows]
    return result


def build_firestore_client(project_id: str | None, credentials_path: str | None):
    client_kwargs: Dict[str, Any] = {}
    if project_id:
        client_kwargs["project"] = project_id
    if credentials_path:
        client_kwargs["credentials"] = service_account.Credentials.from_service_account_file(credentials_path)
    return firestore.Client(**client_kwargs)


def delete_collection(db, collection_ref) -> int:
    deleted = 0
    while True:
        batch = collection_ref.limit(400).stream()
        snapshots = list(batch)
        if not snapshots:
            return deleted
        write_batch = db.batch()
        for snapshot in snapshots:
            write_batch.delete(snapshot.reference)
            deleted += 1
        write_batch.commit()


def write_rows(db, rows_by_collection: Dict[str, List[Dict[str, Any]]], targets: Sequence[str], drop_target: bool) -> Dict[str, int]:
    written: Dict[str, int] = {}
    for name in targets:
        target = TARGETS[name]
        collection_ref = db.collection(target.collection)
        if drop_target:
            delete_collection(db, collection_ref)
        rows = rows_by_collection.get(name) or []
        if not rows:
            written[name] = 0
            continue

        total_written = 0
        pending = 0
        batch = db.batch()
        for row in rows:
            doc_ref = collection_ref.document(str(row["id"]))
            batch.set(doc_ref, row)
            total_written += 1
            pending += 1
            if pending >= 400:
                batch.commit()
                batch = db.batch()
                pending = 0
        if pending:
            batch.commit()
        written[name] = total_written
    return written


def seed_counters(db, rows_by_collection: Dict[str, List[Dict[str, Any]]], targets: Sequence[str]) -> None:
    counters = db.collection("_counters")
    for name in targets:
        target = TARGETS[name]
        if not target.counter_key:
            continue
        rows = rows_by_collection.get(name) or []
        max_id = max((int(row.get("id") or 0) for row in rows), default=0)
        counters.document(target.counter_key).set({"value": max_id}, merge=True)


def firestore_collection_count(db, name: str) -> int:
    return sum(1 for _ in db.collection(name).stream())


def print_summary(rows_by_collection: Dict[str, List[Dict[str, Any]]], firebase_db=None, written: Dict[str, int] | None = None) -> None:
    print("Migration summary")
    print("=================")
    for name, rows in rows_by_collection.items():
        sql_count = len(rows)
        parts = [f"sql={sql_count}"]
        if firebase_db is not None:
            firebase_count = firestore_collection_count(firebase_db, name)
            parts.append(f"firestore={firebase_count}")
        if written is not None:
            parts.append(f"written={written.get(name, 0)}")
        print(f"- {name}: " + ", ".join(parts))


def main() -> int:
    args = parse_args()
    sql_url = resolve_sql_url(args.sql_url)
    session = build_session(sql_url)
    try:
        rows_by_collection = load_rows(session, args.collections)
    finally:
        session.close()

    if args.dry_run:
        print(f"Dry run only. Source SQL URL: {sql_url}")
        print_summary(rows_by_collection)
        return 0

    project_id, credentials_path = resolve_firebase_config(
        args.firebase_project_id,
        args.firebase_credentials_path,
    )
    db = build_firestore_client(project_id, credentials_path)

    written = write_rows(db, rows_by_collection, args.collections, args.drop_target)

    if not args.skip_counters:
        seed_counters(db, rows_by_collection, args.collections)

    print(f"Source SQL URL: {sql_url}")
    print(f"Target Firestore project: {project_id or 'default credentials project'}")
    print_summary(rows_by_collection, firebase_db=db, written=written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
