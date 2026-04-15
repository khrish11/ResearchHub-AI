from __future__ import annotations

import os
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Protocol, Sequence

from fastapi import Depends, HTTPException


try:
    from google.cloud import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    from google.oauth2 import service_account
except Exception:  # pragma: no cover - optional until Firebase path is enabled
    firestore = None
    FieldFilter = None  # type: ignore[assignment]
    service_account = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _firestore_client():
    """Return a Firestore client from the Firebase Admin SDK."""
    try:
        from utils.firebase_admin_client import get_firebase_admin_app
        import firebase_admin.firestore as _fs

        app = get_firebase_admin_app()
        return _fs.client(app=app)
    except Exception as exc:
        raise RuntimeError(f"Cannot create Firestore client: {exc}") from exc


def _normalize_email_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


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
    rebuilt: list[str] = []
    for ch in value:
        if ch in _ENV_ESCAPE_REVERSE:
            rebuilt.append("\\" + _ENV_ESCAPE_REVERSE[ch])
        else:
            rebuilt.append(ch)
    normalized = "".join(rebuilt)
    if len(normalized) > 2 and normalized[1] == ":":
        normalized = normalized.replace("\\", "/")
    return normalized


_JOB_ALLOWED_TRANSITIONS: Dict[str, set[str]] = {
    "pending": {"running"},
    "running": {"completed", "failed", "pending"},
    "completed": set(),
    "failed": set(),
}
_JOB_PRIORITY_ORDER: Dict[str, int] = {"high": 3, "normal": 2, "low": 1}
_JOB_TYPE_VALUES = {"fast", "heavy"}


def _normalize_job_status(raw_status: Any) -> str:
    status = str(raw_status or "").strip().lower()
    if status not in _JOB_ALLOWED_TRANSITIONS:
        raise ValueError(f"Invalid paper check job status: {raw_status!r}")
    return status


def _validate_job_transition(current_status: str, next_status: str) -> None:
    current = _normalize_job_status(current_status)
    target = _normalize_job_status(next_status)
    if current == target:
        return
    if target not in _JOB_ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid paper check job transition: {current} -> {target}")


def _normalize_job_priority(raw_priority: Any) -> str:
    priority = str(raw_priority or "normal").strip().lower()
    if priority not in _JOB_PRIORITY_ORDER:
        return "normal"
    return priority


def _normalize_job_type(raw_job_type: Any) -> str:
    job_type = str(raw_job_type or "fast").strip().lower()
    if job_type not in _JOB_TYPE_VALUES:
        return "fast"
    return job_type


@dataclass
class Workspace:
    id: int
    name: str
    description: Optional[str]
    user_id: int
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class User:
    id: Optional[int]
    email: str
    hashed_password: Optional[str] = None
    google_id: Optional[str] = None
    google_email: Optional[str] = None
    name: Optional[str] = None
    profile_pic: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    verification_token: Optional[str] = None
    verification_token_expires: Optional[datetime] = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    # ── Access control / feature flags ────────────────────────────────
    role: str = "user"  # "user" | "pro" | "admin"
    is_pro: bool = False  # quick shortcut; set to True for pro/admin roles
    feature_flags: Dict[str, Any] = field(default_factory=dict)  # per-user overrides
    has_completed_onboarding: bool = False


@dataclass
class Paper:
    id: int
    title: str
    authors: str
    abstract: str
    url: Optional[str] = None
    doi: Optional[str] = None
    bibcode: Optional[str] = None
    source: Optional[str] = None
    pdf_url: Optional[str] = None
    institutional_url: Optional[str] = None
    access_type: Optional[str] = None
    full_text_available: bool = False
    workspace_id: int = 0


@dataclass
class Chat:
    id: int
    message: str
    response: str
    workspace_id: int
    timestamp: datetime = field(default_factory=_utcnow)


@dataclass
class SearchHistory:
    id: Optional[int]
    user_id: int
    query: str
    source: str = "global_merged"
    result_count: int = 0
    filters_json: Optional[str] = None
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class UserSessionState:
    id: Optional[int]
    user_id: int
    page_path: str = "/home"
    workspace_id: Optional[int] = None
    last_query: Optional[str] = None
    draft_text: Optional[str] = None
    extra_json: Optional[str] = None
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class WorkspaceDocument:
    id: Optional[int]
    workspace_id: int
    user_id: int
    title: str
    content: str = ""
    version: int = 1
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class DataRightsRequest:
    id: Optional[int]
    user_id: Optional[int]
    email: str
    request_type: str
    jurisdiction: Optional[str] = None
    details: Optional[str] = None
    status: str = "submitted"
    submitted_at: datetime = field(default_factory=_utcnow)
    resolved_at: Optional[datetime] = None


@dataclass
class WorkspaceFile:
    id: Optional[int]
    workspace_id: int
    user_id: int
    kind: str
    filename: str
    storage_bucket: str
    storage_path: str
    content_type: Optional[str] = None
    size_bytes: int = 0
    download_url: Optional[str] = None
    paper_id: Optional[int] = None
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class PaperCheckJob:
    job_id: str
    user_id: int
    paper_id: Optional[int]
    fingerprint: Optional[str] = None
    queue_partition: Optional[int] = None
    priority: str = "normal"
    job_type: str = "fast"
    status: str = "pending"
    input_data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retryable: bool = False
    retry_count: int = 0
    max_retries: int = 2
    claimed_by: Optional[str] = None
    claimed_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    latency_ms: Optional[int] = None
    attempt_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

@dataclass
class PaperComparison:
    id: str
    user_id: int
    paper_ids: List[int]
    optional_context: Optional[str] = None
    fingerprint: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=_utcnow)



@dataclass
class ResearchReport:
    id: str
    user_id: int
    paper_ids: List[int]
    topic: Optional[str] = None
    fingerprint: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=_utcnow)


class ResearchRepository(Protocol):
    db: Any  # type: ignore[assignment]  — actual type is google.cloud.firestore.Client

    def get_user_by_id(self, user_id: int) -> Optional[User]: ...
    def get_user_by_email(self, email: str) -> Optional[User]: ...
    def get_user_by_google_id(self, google_id: str) -> Optional[User]: ...
    def get_user_by_verification_token(self, token: str) -> Optional[User]: ...
    def list_users_for_normalized_email(self, normalized_email: str) -> list[User]: ...
    def list_users(
        self,
        *,
        query: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[User]: ...
    def create_user(
        self,
        *,
        email: str,
        hashed_password: Optional[str] = None,
        google_id: Optional[str] = None,
        google_email: Optional[str] = None,
        name: Optional[str] = None,
        profile_pic: Optional[str] = None,
        is_active: bool = True,
        is_verified: bool = False,
        verification_token: Optional[str] = None,
        verification_token_expires: Optional[datetime] = None,
        has_completed_onboarding: bool = False,
    ) -> User: ...
    def merge_user_accounts(
        self, primary_user_id: int, secondary_user_id: int
    ) -> None: ...
    def list_workspaces_for_user(self, user_id: int) -> list[Workspace]: ...
    def find_workspace_for_user(
        self, workspace_id: int, user_id: int
    ) -> Optional[Workspace]: ...
    def find_workspace_by_name_for_user(
        self, user_id: int, name: str
    ) -> Optional[Workspace]: ...
    def create_workspace(
        self, user_id: int, name: str, description: Optional[str] = None
    ) -> Workspace: ...
    def get_or_create_default_workspace(self, user_id: int) -> Workspace: ...
    def workspace_exists_for_user(self, workspace_id: int, user_id: int) -> bool: ...
    def list_papers_for_workspace(
        self, workspace_id: int, paper_ids: Optional[Sequence[int]] = None
    ) -> list[Paper]: ...
    def find_paper_for_user(self, paper_id: int, user_id: int) -> Optional[Paper]: ...
    def create_paper(
        self,
        workspace_id: int,
        title: str,
        authors: str,
        abstract: str,
        url: Optional[str] = None,
        pdf_url: Optional[str] = None,
    ) -> Paper: ...
    def delete_paper_for_user(self, paper_id: int, user_id: int) -> bool: ...
    def list_chats_for_workspace(
        self,
        workspace_id: int,
        *,
        ascending: bool = True,
        limit: Optional[int] = None,
    ) -> list[Chat]: ...
    def create_chat(self, workspace_id: int, message: str, response: str) -> Chat: ...
    def list_search_history_for_user(
        self,
        user_id: int,
        *,
        limit: Optional[int] = None,
    ) -> list[SearchHistory]: ...
    def count_search_history_for_user(self, user_id: int) -> int: ...
    def record_search_history(
        self,
        *,
        user_id: int,
        query: str,
        source: str,
        result_count: int,
        filters_json: Optional[str] = None,
        dedupe_seconds: int = 240,
        max_items: int = 250,
    ) -> SearchHistory: ...
    def delete_search_history(
        self, user_id: int, item_id: Optional[int] = None
    ) -> int: ...
    def get_session_state_for_user(
        self, user_id: int
    ) -> Optional[UserSessionState]: ...
    def create_session_state(self, user_id: int) -> UserSessionState: ...
    def save(self, instance: object) -> object: ...
    def get_docspace_document(
        self, workspace_id: int, user_id: int
    ) -> Optional[WorkspaceDocument]: ...
    def list_workspace_documents_for_user(
        self, user_id: int
    ) -> list[WorkspaceDocument]: ...
    def create_docspace_document(
        self,
        workspace_id: int,
        user_id: int,
        title: str,
        content: str = "",
        version: int = 1,
    ) -> WorkspaceDocument: ...
    def create_workspace_file(
        self,
        workspace_id: int,
        user_id: int,
        kind: str,
        filename: str,
        storage_bucket: str,
        storage_path: str,
        content_type: Optional[str] = None,
        size_bytes: int = 0,
        download_url: Optional[str] = None,
        paper_id: Optional[int] = None,
    ) -> WorkspaceFile: ...
    def list_workspace_files_for_workspace(
        self, workspace_id: int, user_id: int
    ) -> list[WorkspaceFile]: ...
    def get_workspace_file_for_user(
        self, file_id: int, workspace_id: int, user_id: int
    ) -> Optional[WorkspaceFile]: ...
    def get_workspace_file_for_paper(
        self, paper_id: int, workspace_id: int, user_id: int
    ) -> Optional[WorkspaceFile]: ...
    def create_paper_check_job(
        self,
        *,
        job_id: str,
        user_id: int,
        paper_id: Optional[int],
        fingerprint: Optional[str] = None,
        queue_partition: Optional[int] = None,
        priority: str = "normal",
        job_type: str = "fast",
        input_data: Dict[str, Any],
        status: str = "pending",
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        retryable: bool = False,
        retry_count: int = 0,
        max_retries: int = 2,
        claimed_by: Optional[str] = None,
        claimed_at: Optional[datetime] = None,
        processing_started_at: Optional[datetime] = None,
        processing_completed_at: Optional[datetime] = None,
        latency_ms: Optional[int] = None,
        attempt_history: Optional[List[Dict[str, Any]]] = None,
    ) -> PaperCheckJob: ...
    def get_paper_check_job(self, job_id: str) -> Optional[PaperCheckJob]: ...
    def update_paper_check_job(
        self,
        job_id: str,
        updates: Dict[str, Any],
    ) -> Optional[PaperCheckJob]: ...
    def update_job_status(
        self,
        job_id: str,
        updates: Dict[str, Any],
    ) -> Optional[PaperCheckJob]: ...
    def claim_next_job(self, worker_id: str) -> Optional[PaperCheckJob]: ...
    def get_stuck_jobs(self, timeout_seconds: int) -> list[PaperCheckJob]: ...
    def reset_job(self, job_id: str) -> Optional[PaperCheckJob]: ...
    def requeue_paper_check_job(self, job_id: str) -> Optional[PaperCheckJob]: ...
    def claim_paper_check_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        stale_before: Optional[datetime] = None,
    ) -> Optional[PaperCheckJob]: ...
    def complete_paper_check_job(
        self,
        job_id: str,
        *,
        worker_id: Optional[str],
        claimed_at: Optional[datetime],
        result: Dict[str, Any],
    ) -> Optional[PaperCheckJob]: ...
    def fail_or_requeue_paper_check_job(
        self,
        job_id: str,
        *,
        worker_id: Optional[str],
        claimed_at: Optional[datetime],
        error_message: str,
        retryable: bool,
    ) -> Optional[PaperCheckJob]: ...
    def find_reusable_paper_check_job(
        self,
        *,
        user_id: int,
        fingerprint: str,
    ) -> Optional[PaperCheckJob]: ...
    def count_active_jobs_for_user(self, user_id: int) -> int: ...
    def get_paper_check_job_metrics(self, timeout_seconds: int) -> Dict[str, Any]: ...
    def create_paper_comparison(
        self,
        *,
        id: str,
        user_id: int,
        paper_ids: List[int],
        optional_context: Optional[str] = None,
        fingerprint: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> PaperComparison: ...
    def get_paper_comparison(self, comparison_id: str) -> Optional[PaperComparison]: ...
    def find_paper_comparison_by_fingerprint(self, fingerprint: str) -> Optional[PaperComparison]: ...
    def create_research_report(
        self,
        *,
        id: str,
        user_id: int,
        paper_ids: List[int],
        topic: Optional[str] = None,
        fingerprint: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> ResearchReport: ...
    def get_research_report(self, report_id: str) -> Optional[ResearchReport]: ...
    def find_research_report_by_fingerprint(self, fingerprint: str) -> Optional[ResearchReport]: ...

    def list_pending_jobs_for_dispatch(
        self,
        *,
        older_than_seconds: int,
        queue_partition: Optional[int] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[PaperCheckJob]: ...
    def count_jobs_by_status(
        self,
        *,
        statuses: Sequence[str],
        queue_partition: Optional[int] = None,
        job_type: Optional[str] = None,
    ) -> int: ...
    def list_user_jobs(
        self, user_id: int, *, limit: Optional[int] = None
    ) -> list[PaperCheckJob]: ...
    def create_data_rights_request(
        self,
        *,
        user_id: Optional[int],
        email: str,
        request_type: str,
        jurisdiction: Optional[str] = None,
        details: Optional[str] = None,
        status: str = "submitted",
        resolved_at: Optional[datetime] = None,
    ) -> DataRightsRequest: ...
    def list_data_rights_requests_for_user(
        self,
        user_id: int,
        *,
        limit: Optional[int] = None,
    ) -> list[DataRightsRequest]: ...
    def count_users(self) -> int: ...
    def count_workspaces(self) -> int: ...
    def count_papers(self) -> int: ...
    def count_chats(self) -> int: ...
    def count_documents_for_user(self, user_id: int) -> int: ...
    def delete_user_account(self, user_id: int) -> None: ...
    def delete_workspace_graph(self, workspace_id: int) -> None: ...


class FirebaseResearchRepository:
    def __init__(self):
        self.db = _firestore_client()
        self.users = self.db.collection("users")
        self.workspaces = self.db.collection("workspaces")
        self.papers = self.db.collection("papers")
        self.chats = self.db.collection("chats")
        self.search_history = self.db.collection("search_history")
        self.user_session_state = self.db.collection("user_session_state")
        self.workspace_documents = self.db.collection("workspace_documents")
        self.workspace_files = self.db.collection("workspace_files")
        self.paper_check_jobs = self.db.collection("paper_check_jobs")
        self.paper_comparisons = self.db.collection("paper_comparisons")
        self.research_reports = self.db.collection("research_reports")
        self.data_rights_requests = self.db.collection("data_rights_requests")
        self.counters = self.db.collection("_counters")

    def _next_id(self, key: str) -> int:
        counter_ref = self.counters.document(key)
        transaction = self.db.transaction()

        @firestore.transactional
        def increment(transaction_obj, reference):
            snapshot = reference.get(transaction=transaction_obj)
            current = 0
            if snapshot.exists:
                current = int((snapshot.to_dict() or {}).get("value") or 0)
            next_value = current + 1
            transaction_obj.set(reference, {"value": next_value}, merge=True)
            return next_value

        return int(increment(transaction, counter_ref))

    @staticmethod
    def _workspace_from_doc(doc: Dict[str, Any]) -> Workspace:
        return Workspace(
            id=int(doc["id"]),
            name=str(doc.get("name") or ""),
            description=doc.get("description"),
            user_id=int(doc.get("user_id") or 0),
            created_at=doc.get("created_at") or _utcnow(),
        )

    @staticmethod
    def _user_from_doc(doc: Dict[str, Any]) -> User:
        raw_role = str(doc.get("role") or "user").strip().lower()
        role = raw_role if raw_role in ("user", "pro", "admin") else "user"
        return User(
            id=int(doc["id"]) if doc.get("id") is not None else None,
            email=str(doc.get("email") or ""),
            hashed_password=doc.get("hashed_password"),
            google_id=doc.get("google_id"),
            google_email=doc.get("google_email"),
            name=doc.get("name"),
            profile_pic=doc.get("profile_pic"),
            is_active=bool(doc.get("is_active", True)),
            is_verified=bool(doc.get("is_verified", False)),
            verification_token=doc.get("verification_token"),
            verification_token_expires=doc.get("verification_token_expires"),
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
            role=role,
            is_pro=bool(doc.get("is_pro", False)) or role in ("pro", "admin"),
            feature_flags=dict(doc.get("feature_flags") or {}),
            has_completed_onboarding=bool(doc.get("has_completed_onboarding", False)),
        )

    @staticmethod
    def _user_doc_from_snapshot(snapshot: Any) -> Dict[str, Any]:
        doc = snapshot.to_dict() or {}
        if doc.get("id") is None:
            snapshot_id = _coerce_int(getattr(snapshot, "id", None), 0)
            if snapshot_id > 0:
                doc["id"] = snapshot_id
        return doc

    @staticmethod
    def _paper_from_doc(doc: Dict[str, Any]) -> Paper:
        return Paper(
            id=int(doc["id"]),
            title=str(doc.get("title") or ""),
            authors=str(doc.get("authors") or ""),
            abstract=str(doc.get("abstract") or ""),
            url=doc.get("url"),
            doi=doc.get("doi"),
            bibcode=doc.get("bibcode"),
            source=doc.get("source"),
            pdf_url=doc.get("pdf_url"),
            institutional_url=doc.get("institutional_url"),
            access_type=doc.get("access_type"),
            full_text_available=bool(doc.get("full_text_available", False)),
            workspace_id=int(doc.get("workspace_id") or 0),
        )

    @staticmethod
    def _chat_from_doc(doc: Dict[str, Any]) -> Chat:
        return Chat(
            id=int(doc["id"]),
            message=str(doc.get("message") or ""),
            response=str(doc.get("response") or ""),
            workspace_id=int(doc.get("workspace_id") or 0),
            timestamp=doc.get("timestamp") or _utcnow(),
        )

    @staticmethod
    def _search_history_from_doc(doc: Dict[str, Any]) -> SearchHistory:
        return SearchHistory(
            id=int(doc["id"]) if doc.get("id") is not None else None,
            user_id=int(doc.get("user_id") or 0),
            query=str(doc.get("query") or ""),
            source=str(doc.get("source") or "global_merged"),
            result_count=int(doc.get("result_count") or 0),
            filters_json=doc.get("filters_json"),
            created_at=doc.get("created_at") or _utcnow(),
        )

    @staticmethod
    def _state_from_doc(doc: Dict[str, Any]) -> UserSessionState:
        return UserSessionState(
            id=int(doc["id"]) if doc.get("id") is not None else None,
            user_id=int(doc.get("user_id") or 0),
            page_path=str(doc.get("page_path") or "/home"),
            workspace_id=doc.get("workspace_id"),
            last_query=doc.get("last_query"),
            draft_text=doc.get("draft_text"),
            extra_json=doc.get("extra_json"),
            updated_at=doc.get("updated_at") or _utcnow(),
        )

    @staticmethod
    def _document_from_doc(doc: Dict[str, Any]) -> WorkspaceDocument:
        return WorkspaceDocument(
            id=int(doc["id"]) if doc.get("id") is not None else None,
            workspace_id=int(doc.get("workspace_id") or 0),
            user_id=int(doc.get("user_id") or 0),
            title=str(doc.get("title") or "Research Notes"),
            content=str(doc.get("content") or ""),
            version=int(doc.get("version") or 1),
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
        )

    @staticmethod
    def _workspace_file_from_doc(doc: Dict[str, Any]) -> WorkspaceFile:
        return WorkspaceFile(
            id=int(doc["id"]) if doc.get("id") is not None else None,
            workspace_id=int(doc.get("workspace_id") or 0),
            user_id=int(doc.get("user_id") or 0),
            kind=str(doc.get("kind") or ""),
            filename=str(doc.get("filename") or ""),
            storage_bucket=str(doc.get("storage_bucket") or ""),
            storage_path=str(doc.get("storage_path") or ""),
            content_type=doc.get("content_type"),
            size_bytes=int(doc.get("size_bytes") or 0),
            download_url=doc.get("download_url"),
            paper_id=int(doc["paper_id"]) if doc.get("paper_id") is not None else None,
            created_at=doc.get("created_at") or _utcnow(),
        )

    @staticmethod
    def _paper_check_job_from_doc(doc: Dict[str, Any]) -> PaperCheckJob:
        return PaperCheckJob(
            job_id=str(doc.get("job_id") or ""),
            user_id=int(doc.get("user_id") or 0),
            paper_id=int(doc["paper_id"]) if doc.get("paper_id") is not None else None,
            fingerprint=str(doc.get("fingerprint") or "") or None,
            queue_partition=(
                int(doc.get("queue_partition"))
                if doc.get("queue_partition") is not None
                else None
            ),
            priority=_normalize_job_priority(doc.get("priority")),
            job_type=_normalize_job_type(doc.get("job_type")),
            status=str(doc.get("status") or "pending"),
            input_data=dict(doc.get("input") or {}),
            result=dict(doc.get("result") or {}) if isinstance(doc.get("result"), dict) else doc.get("result"),
            error=str(doc.get("error") or "") or None,
            retryable=bool(doc.get("retryable", False)),
            retry_count=max(0, int(doc.get("retry_count") or 0)),
            max_retries=max(0, int(2 if doc.get("max_retries") is None else doc.get("max_retries"))),
            claimed_by=str(doc.get("claimed_by") or "") or None,
            claimed_at=doc.get("claimed_at"),
            processing_started_at=doc.get("processing_started_at"),
            processing_completed_at=doc.get("processing_completed_at"),
            latency_ms=(
                max(0, int(doc.get("latency_ms")))
                if doc.get("latency_ms") is not None
                else None
            ),
            attempt_history=[
                dict(item)
                for item in (doc.get("attempt_history") or [])
                if isinstance(item, dict)
            ],
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
        )

    @staticmethod
    def _data_rights_from_doc(doc: Dict[str, Any]) -> DataRightsRequest:
        return DataRightsRequest(
            id=int(doc["id"]) if doc.get("id") is not None else None,
            user_id=int(doc["user_id"]) if doc.get("user_id") is not None else None,
            email=str(doc.get("email") or ""),
            request_type=str(doc.get("request_type") or ""),
            jurisdiction=doc.get("jurisdiction"),
            details=doc.get("details"),
            status=str(doc.get("status") or "submitted"),
            submitted_at=doc.get("submitted_at") or _utcnow(),
            resolved_at=doc.get("resolved_at"),
        )

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        snapshot = self.users.document(str(user_id)).get()
        if not snapshot.exists:
            return None
        doc = self._user_doc_from_snapshot(snapshot)
        try:
            return self._user_from_doc(doc)
        except Exception:
            logging.getLogger(__name__).warning(
                "Skipping malformed user record for id=%s", user_id, exc_info=True
            )
            return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        normalized = _normalize_email_key(email)
        if not normalized:
            return None
        return next(iter(self.list_users_for_normalized_email(normalized)), None)

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        target = str(google_id or "").strip()
        if not target:
            return None
        fallback_user: Optional[User] = None
        for snapshot in self.users.where(
            filter=FieldFilter("google_id", "==", target)
        ).stream():
            doc = self._user_doc_from_snapshot(snapshot)
            try:
                candidate = self._user_from_doc(doc)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Skipping malformed Google-linked user for google_id=%s",
                    target,
                    exc_info=True,
                )
                continue
            if _coerce_int(getattr(candidate, "id", None), 0) > 0:
                return candidate
            if fallback_user is None:
                fallback_user = candidate
        return fallback_user

    def get_user_by_verification_token(self, token: str) -> Optional[User]:
        value = str(token or "").strip()
        if not value:
            return None
        for snapshot in self.users.where(
            filter=FieldFilter("verification_token", "==", value)
        ).stream():
            doc = self._user_doc_from_snapshot(snapshot)
            try:
                return self._user_from_doc(doc)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Skipping malformed verification-token user", exc_info=True
                )
                continue
        return None

    def list_users_for_normalized_email(self, normalized_email: str) -> list[User]:
        normalized = _normalize_email_key(normalized_email)
        if not normalized:
            return []
        docs: list[Dict[str, Any]] = []
        seen_keys: set[str] = set()
        for snapshot in self.users.where(
            filter=FieldFilter("email", "==", normalized)
        ).stream():
            doc = self._user_doc_from_snapshot(snapshot)
            doc_id = _coerce_int(doc.get("id"), 0)
            dedupe_key = str(doc_id or getattr(snapshot, "id", ""))
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            docs.append(doc)
        for snapshot in self.users.where(
            filter=FieldFilter("google_email", "==", normalized)
        ).stream():
            doc = self._user_doc_from_snapshot(snapshot)
            doc_id = _coerce_int(doc.get("id"), 0)
            dedupe_key = str(doc_id or getattr(snapshot, "id", ""))
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            docs.append(doc)
        docs.sort(key=lambda doc: _coerce_int(doc.get("id"), 0))
        users: list[User] = []
        for doc in docs:
            try:
                users.append(self._user_from_doc(doc))
            except Exception:
                logging.getLogger(__name__).warning(
                    "Skipping malformed user record while listing email=%s",
                    normalized,
                    exc_info=True,
                )
        return users

    def list_users(
        self,
        *,
        query: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[User]:
        docs = [self._user_doc_from_snapshot(snapshot) for snapshot in self.users.stream()]
        trimmed = str(query or "").strip().lower()
        if trimmed:
            docs = [
                doc
                for doc in docs
                if trimmed in str(doc.get("email") or "").lower()
                or trimmed in str(doc.get("name") or "").lower()
            ]
        docs.sort(
            key=lambda doc: (
                -(doc.get("created_at") or _utcnow()).timestamp(),
                -_coerce_int(doc.get("id"), 0),
            )
        )
        docs = docs[max(0, int(offset)) :]
        if limit is not None:
            docs = docs[: max(0, int(limit))]
        users: list[User] = []
        for doc in docs:
            try:
                users.append(self._user_from_doc(doc))
            except Exception:
                logging.getLogger(__name__).warning(
                    "Skipping malformed user record while listing users",
                    exc_info=True,
                )
        return users

    def create_user(
        self,
        *,
        email: str,
        hashed_password: Optional[str] = None,
        google_id: Optional[str] = None,
        google_email: Optional[str] = None,
        name: Optional[str] = None,
        profile_pic: Optional[str] = None,
        is_active: bool = True,
        is_verified: bool = False,
        verification_token: Optional[str] = None,
        verification_token_expires: Optional[datetime] = None,
        has_completed_onboarding: bool = False,
    ) -> User:
        now = _utcnow()
        user = User(
            id=self._next_id("user_id"),
            email=_normalize_email_key(email),
            hashed_password=hashed_password,
            google_id=google_id,
            google_email=_normalize_email_key(google_email) if google_email else None,
            name=name,
            profile_pic=profile_pic,
            is_active=is_active,
            is_verified=is_verified,
            verification_token=verification_token,
            verification_token_expires=verification_token_expires,
            created_at=now,
            updated_at=now,
            has_completed_onboarding=bool(has_completed_onboarding),
        )
        self.users.document(str(user.id)).set(asdict(user))
        return user

    def merge_user_accounts(self, primary_user_id: int, secondary_user_id: int) -> None:
        if primary_user_id == secondary_user_id:
            return
        secondary = self.get_user_by_id(secondary_user_id)
        if secondary is None:
            return
        for snapshot in self.workspaces.where(
            filter=FieldFilter("user_id", "==", secondary_user_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            doc["user_id"] = primary_user_id
            snapshot.reference.set(doc)
        for collection in (
            self.search_history,
            self.workspace_documents,
            self.workspace_files,
            self.paper_check_jobs,
            self.data_rights_requests,
        ):
            for snapshot in collection.where(
                filter=FieldFilter("user_id", "==", secondary_user_id)
            ).stream():
                doc = snapshot.to_dict() or {}
                doc["user_id"] = primary_user_id
                snapshot.reference.set(doc)
        secondary_state = self.get_session_state_for_user(secondary_user_id)
        primary_state = self.get_session_state_for_user(primary_user_id)
        if secondary_state and not primary_state:
            secondary_state.user_id = primary_user_id
            self.save(secondary_state)
        elif secondary_state and primary_state:
            primary_updated = primary_state.updated_at or datetime(
                1970, 1, 1, tzinfo=timezone.utc
            )
            secondary_updated = secondary_state.updated_at or datetime(
                1970, 1, 1, tzinfo=timezone.utc
            )
            if secondary_updated > primary_updated:
                primary_state.page_path = secondary_state.page_path
                primary_state.workspace_id = secondary_state.workspace_id
                primary_state.last_query = secondary_state.last_query
                primary_state.draft_text = secondary_state.draft_text
                primary_state.extra_json = secondary_state.extra_json
                primary_state.updated_at = secondary_state.updated_at
                self.save(primary_state)
            if secondary_state.id is not None:
                self.user_session_state.document(str(secondary_state.id)).delete()
        self.users.document(str(secondary_user_id)).delete()

    def list_workspaces_for_user(self, user_id: int) -> list[Workspace]:
        paper_counts: Dict[int, int] = {}
        for snapshot in self.papers.where(
            filter=FieldFilter("user_id", "==", user_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            workspace_id = doc.get("workspace_id")
            if workspace_id is None:
                continue
            workspace_key = int(workspace_id)
            paper_counts[workspace_key] = paper_counts.get(workspace_key, 0) + 1

        docs = [
            (snapshot.to_dict() or {})
            for snapshot in self.workspaces.where(
                filter=FieldFilter("user_id", "==", user_id)
            ).stream()
        ]
        docs.sort(
            key=lambda doc: (
                -paper_counts.get(int(doc.get("id") or 0), 0),
                -(doc.get("created_at") or _utcnow()).timestamp(),
            )
        )
        return [self._workspace_from_doc(doc) for doc in docs]

    def find_workspace_for_user(
        self, workspace_id: int, user_id: int
    ) -> Optional[Workspace]:
        for snapshot in self.workspaces.where(
            filter=FieldFilter("user_id", "==", user_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            if int(doc.get("id") or 0) == workspace_id:
                return self._workspace_from_doc(doc)
        return None

    def find_workspace_by_name_for_user(
        self, user_id: int, name: str
    ) -> Optional[Workspace]:
        normalized = (name or "").strip()
        if not normalized:
            return None
        for snapshot in self.workspaces.where(
            filter=FieldFilter("user_id", "==", user_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            if str(doc.get("name") or "").strip().lower() == normalized.lower():
                return self._workspace_from_doc(doc)
        return None

    def create_workspace(
        self, user_id: int, name: str, description: Optional[str] = None
    ) -> Workspace:
        workspace = Workspace(
            id=self._next_id("workspace_id"),
            name=name,
            description=description,
            user_id=user_id,
        )
        self.workspaces.document(str(workspace.id)).set(asdict(workspace))
        return workspace

    def get_or_create_default_workspace(self, user_id: int) -> Workspace:
        existing = self.find_workspace_by_name_for_user(user_id, "Default Workspace")
        if existing:
            return existing
        return self.create_workspace(
            user_id=user_id,
            name="Default Workspace",
            description="Automatically created workspace for quick imports.",
        )

    def workspace_exists_for_user(self, workspace_id: int, user_id: int) -> bool:
        return self.find_workspace_for_user(workspace_id, user_id) is not None

    def list_papers_for_workspace(
        self,
        workspace_id: int,
        paper_ids: Optional[Sequence[int]] = None,
    ) -> list[Paper]:
        allowed_ids = {int(paper_id) for paper_id in paper_ids} if paper_ids else None
        docs: list[Dict[str, Any]] = []
        for snapshot in self.papers.where(
            filter=FieldFilter("workspace_id", "==", workspace_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            doc_id = int(doc.get("id") or 0)
            if allowed_ids is not None and doc_id not in allowed_ids:
                continue
            docs.append(doc)
        return [self._paper_from_doc(doc) for doc in docs]

    def create_paper(
        self,
        workspace_id: int,
        title: str,
        authors: str,
        abstract: str,
        url: Optional[str] = None,
        pdf_url: Optional[str] = None,
    ) -> Paper:
        paper = Paper(
            id=self._next_id("paper_id"),
            title=title,
            authors=authors,
            abstract=abstract,
            url=url,
            pdf_url=pdf_url,
            workspace_id=workspace_id,
        )
        self.papers.document(str(paper.id)).set(asdict(paper))
        return paper

    def find_paper_for_user(self, paper_id: int, user_id: int) -> Optional[Paper]:
        snapshot = self.papers.document(str(paper_id)).get()
        if not snapshot.exists:
            return None
        doc = snapshot.to_dict() or {}
        workspace_id = int(doc.get("workspace_id") or 0)
        if not self.workspace_exists_for_user(workspace_id, user_id):
            return None
        return self._paper_from_doc(doc)

    def delete_paper_for_user(self, paper_id: int, user_id: int) -> bool:
        paper = self.find_paper_for_user(int(paper_id), int(user_id))
        if not paper:
            return False
        self.papers.document(str(int(paper_id))).delete()
        for snapshot in self.workspace_files.where(
            filter=FieldFilter("paper_id", "==", int(paper_id))
        ).stream():
            doc = snapshot.to_dict() or {}
            workspace_id = int(doc.get("workspace_id") or 0)
            owner_id = int(doc.get("user_id") or 0)
            if workspace_id == int(paper.workspace_id) and owner_id == int(user_id):
                snapshot.reference.delete()
        return True

    def list_chats_for_workspace(
        self,
        workspace_id: int,
        *,
        ascending: bool = True,
        limit: Optional[int] = None,
    ) -> list[Chat]:
        docs = [
            (snapshot.to_dict() or {})
            for snapshot in self.chats.where(
                filter=FieldFilter("workspace_id", "==", workspace_id)
            ).stream()
        ]
        docs.sort(
            key=lambda doc: doc.get("timestamp") or _utcnow(), reverse=not ascending
        )
        if limit is not None:
            docs = docs[: max(0, int(limit))]
        return [self._chat_from_doc(doc) for doc in docs]

    def create_chat(self, workspace_id: int, message: str, response: str) -> Chat:
        chat = Chat(
            id=self._next_id("chat_id"),
            message=message,
            response=response,
            workspace_id=workspace_id,
        )
        self.chats.document(str(chat.id)).set(asdict(chat))
        return chat

    def list_search_history_for_user(
        self,
        user_id: int,
        *,
        limit: Optional[int] = None,
    ) -> list[SearchHistory]:
        docs = [
            (snapshot.to_dict() or {})
            for snapshot in self.search_history.where(
                filter=FieldFilter("user_id", "==", user_id)
            ).stream()
        ]
        docs.sort(key=lambda doc: doc.get("created_at") or _utcnow(), reverse=True)
        if limit is not None:
            docs = docs[: max(0, int(limit))]
        return [self._search_history_from_doc(doc) for doc in docs]

    def count_search_history_for_user(self, user_id: int) -> int:
        return len(self.list_search_history_for_user(user_id))

    def record_search_history(
        self,
        *,
        user_id: int,
        query: str,
        source: str,
        result_count: int,
        filters_json: Optional[str] = None,
        dedupe_seconds: int = 240,
        max_items: int = 250,
    ) -> SearchHistory:
        trimmed_query = (query or "").strip()
        if not trimmed_query:
            raise ValueError("query is required")
        now_utc = _utcnow()
        recent = self.list_search_history_for_user(user_id, limit=max(1, max_items))
        latest = next((row for row in recent if row.source == source), None)
        if latest and latest.query.strip().lower() == trimmed_query.lower():
            created = latest.created_at or now_utc
            if abs((now_utc - created).total_seconds()) <= max(1, int(dedupe_seconds)):
                latest.result_count = max(0, int(result_count or 0))
                latest.filters_json = filters_json
                latest.created_at = now_utc
                self.save(latest)
                target = latest
            else:
                target = SearchHistory(
                    id=self._next_id("search_history_id"),
                    user_id=user_id,
                    query=trimmed_query[:300],
                    source=source,
                    result_count=max(0, int(result_count or 0)),
                    filters_json=filters_json,
                    created_at=now_utc,
                )
                self.search_history.document(str(target.id)).set(asdict(target))
        else:
            target = SearchHistory(
                id=self._next_id("search_history_id"),
                user_id=user_id,
                query=trimmed_query[:300],
                source=source,
                result_count=max(0, int(result_count or 0)),
                filters_json=filters_json,
                created_at=now_utc,
            )
            self.search_history.document(str(target.id)).set(asdict(target))

        current = self.list_search_history_for_user(user_id, limit=max_items + 25)
        for stale in current[max(0, int(max_items)) :]:
            if stale.id is not None:
                self.search_history.document(str(stale.id)).delete()
        return target

    def delete_search_history(self, user_id: int, item_id: Optional[int] = None) -> int:
        deleted = 0
        if item_id is not None:
            snapshot = self.search_history.document(str(item_id)).get()
            if not snapshot.exists:
                return 0
            doc = snapshot.to_dict() or {}
            if int(doc.get("user_id") or 0) != user_id:
                return 0
            snapshot.reference.delete()
            return 1
        for snapshot in self.search_history.where(
            filter=FieldFilter("user_id", "==", user_id)
        ).stream():
            snapshot.reference.delete()
            deleted += 1
        return deleted

    def get_session_state_for_user(self, user_id: int) -> Optional[UserSessionState]:
        for snapshot in self.user_session_state.where(
            filter=FieldFilter("user_id", "==", user_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            return self._state_from_doc(doc)
        return None

    def create_session_state(self, user_id: int) -> UserSessionState:
        state = UserSessionState(id=self._next_id("session_state_id"), user_id=user_id)
        self.user_session_state.document(str(state.id)).set(asdict(state))
        return state

    def save(self, instance: object) -> object:
        if isinstance(instance, User):
            resolved_user_id = _coerce_int(getattr(instance, "id", None), 0)
            if resolved_user_id <= 0:
                created = self.create_user(
                    email=instance.email,
                    hashed_password=instance.hashed_password,
                    google_id=instance.google_id,
                    google_email=instance.google_email,
                    name=instance.name,
                    profile_pic=instance.profile_pic,
                    is_active=instance.is_active,
                    is_verified=instance.is_verified,
                    verification_token=instance.verification_token,
                    verification_token_expires=instance.verification_token_expires,
                )
                instance.id = created.id
                instance.created_at = created.created_at
                instance.updated_at = created.updated_at
            else:
                instance.id = resolved_user_id
            instance.email = _normalize_email_key(instance.email)
            if instance.google_email:
                instance.google_email = _normalize_email_key(instance.google_email)
            instance.updated_at = _utcnow()
            self.users.document(str(instance.id)).set(asdict(instance))
            return instance
        if isinstance(instance, SearchHistory):
            if instance.id is None:
                instance.id = self._next_id("search_history_id")
            self.search_history.document(str(instance.id)).set(asdict(instance))
            return instance
        if isinstance(instance, UserSessionState):
            if instance.id is None:
                instance.id = self._next_id("session_state_id")
            payload = asdict(instance)
            self.user_session_state.document(str(instance.id)).set(payload)
            return instance
        if isinstance(instance, Paper):
            payload = asdict(instance)
            self.papers.document(str(instance.id)).set(payload)
            return instance
        if isinstance(instance, WorkspaceDocument):
            if instance.id is None:
                instance.id = self._next_id("workspace_document_id")
            payload = asdict(instance)
            self.workspace_documents.document(str(instance.id)).set(payload)
            return instance
        if isinstance(instance, WorkspaceFile):
            if instance.id is None:
                instance.id = self._next_id("workspace_file_id")
            payload = asdict(instance)
            self.workspace_files.document(str(instance.id)).set(payload)
            return instance
        if isinstance(instance, DataRightsRequest):
            if instance.id is None:
                instance.id = self._next_id("data_rights_request_id")
            payload = asdict(instance)
            self.data_rights_requests.document(str(instance.id)).set(payload)
            return instance
        raise TypeError(
            f"Firebase repository cannot persist instance type {type(instance)!r}"
        )

    def get_docspace_document(
        self, workspace_id: int, user_id: int
    ) -> Optional[WorkspaceDocument]:
        for snapshot in self.workspace_documents.where(
            filter=FieldFilter("workspace_id", "==", workspace_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            if int(doc.get("user_id") or 0) == user_id:
                return self._document_from_doc(doc)
        return None

    def list_workspace_documents_for_user(
        self, user_id: int
    ) -> list[WorkspaceDocument]:
        docs = [
            (snapshot.to_dict() or {})
            for snapshot in self.workspace_documents.where(
                filter=FieldFilter("user_id", "==", user_id)
            ).stream()
        ]
        docs.sort(key=lambda doc: doc.get("updated_at") or _utcnow(), reverse=True)
        return [self._document_from_doc(doc) for doc in docs]

    def create_docspace_document(
        self,
        workspace_id: int,
        user_id: int,
        title: str,
        content: str = "",
        version: int = 1,
    ) -> WorkspaceDocument:
        now = _utcnow()
        document = WorkspaceDocument(
            id=self._next_id("workspace_document_id"),
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            content=content,
            version=version,
            created_at=now,
            updated_at=now,
        )
        self.workspace_documents.document(str(document.id)).set(asdict(document))
        return document

    def create_workspace_file(
        self,
        workspace_id: int,
        user_id: int,
        kind: str,
        filename: str,
        storage_bucket: str,
        storage_path: str,
        content_type: Optional[str] = None,
        size_bytes: int = 0,
        download_url: Optional[str] = None,
        paper_id: Optional[int] = None,
    ) -> WorkspaceFile:
        record = WorkspaceFile(
            id=self._next_id("workspace_file_id"),
            workspace_id=workspace_id,
            user_id=user_id,
            kind=kind,
            filename=filename,
            storage_bucket=storage_bucket,
            storage_path=storage_path,
            content_type=content_type,
            size_bytes=size_bytes,
            download_url=download_url,
            paper_id=paper_id,
        )
        self.workspace_files.document(str(record.id)).set(asdict(record))
        return record

    def list_workspace_files_for_workspace(
        self, workspace_id: int, user_id: int
    ) -> list[WorkspaceFile]:
        docs = []
        for snapshot in self.workspace_files.where(
            filter=FieldFilter("workspace_id", "==", workspace_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            if int(doc.get("user_id") or 0) != user_id:
                continue
            docs.append(doc)
        docs.sort(key=lambda doc: doc.get("created_at") or _utcnow(), reverse=True)
        return [self._workspace_file_from_doc(doc) for doc in docs]

    def get_workspace_file_for_user(
        self, file_id: int, workspace_id: int, user_id: int
    ) -> Optional[WorkspaceFile]:
        snapshot = self.workspace_files.document(str(file_id)).get()
        if not snapshot.exists:
            return None
        doc = snapshot.to_dict() or {}
        if (
            int(doc.get("workspace_id") or 0) != workspace_id
            or int(doc.get("user_id") or 0) != user_id
        ):
            return None
        return self._workspace_file_from_doc(doc)

    def get_workspace_file_for_paper(
        self, paper_id: int, workspace_id: int, user_id: int
    ) -> Optional[WorkspaceFile]:
        docs = []
        for snapshot in self.workspace_files.where(
            filter=FieldFilter("paper_id", "==", paper_id)
        ).stream():
            doc = snapshot.to_dict() or {}
            if (
                int(doc.get("workspace_id") or 0) != workspace_id
                or int(doc.get("user_id") or 0) != user_id
            ):
                continue
            docs.append(doc)
        docs.sort(key=lambda doc: doc.get("created_at") or _utcnow(), reverse=True)
        if not docs:
            return None
        return self._workspace_file_from_doc(docs[0])

    def create_data_rights_request(
        self,
        *,
        user_id: Optional[int],
        email: str,
        request_type: str,
        jurisdiction: Optional[str] = None,
        details: Optional[str] = None,
        status: str = "submitted",
        resolved_at: Optional[datetime] = None,
    ) -> DataRightsRequest:
        row = DataRightsRequest(
            id=self._next_id("data_rights_request_id"),
            user_id=user_id,
            email=_normalize_email_key(email),
            request_type=request_type,
            jurisdiction=jurisdiction,
            details=details,
            status=status,
            submitted_at=_utcnow(),
            resolved_at=resolved_at,
        )
        self.data_rights_requests.document(str(row.id)).set(asdict(row))
        return row

    def create_paper_check_job(
        self,
        *,
        job_id: str,
        user_id: int,
        paper_id: Optional[int],
        fingerprint: Optional[str] = None,
        queue_partition: Optional[int] = None,
        priority: str = "normal",
        job_type: str = "fast",
        input_data: Dict[str, Any],
        status: str = "pending",
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        retryable: bool = False,
        retry_count: int = 0,
        max_retries: int = 2,
        claimed_by: Optional[str] = None,
        claimed_at: Optional[datetime] = None,
        processing_started_at: Optional[datetime] = None,
        processing_completed_at: Optional[datetime] = None,
        latency_ms: Optional[int] = None,
        attempt_history: Optional[List[Dict[str, Any]]] = None,
    ) -> PaperCheckJob:
        now = _utcnow()
        record = PaperCheckJob(
            job_id=str(job_id),
            user_id=int(user_id),
            paper_id=int(paper_id) if paper_id is not None else None,
            fingerprint=str(fingerprint or "") or None,
            queue_partition=(
                max(0, int(queue_partition))
                if queue_partition is not None
                else None
            ),
            priority=_normalize_job_priority(priority),
            job_type=_normalize_job_type(job_type),
            status=_normalize_job_status(status or "pending"),
            input_data=dict(input_data or {}),
            result=result,
            error=error,
            retryable=bool(retryable),
            retry_count=max(0, int(retry_count or 0)),
            max_retries=max(0, int(2 if max_retries is None else max_retries)),
            claimed_by=str(claimed_by or "") or None,
            claimed_at=claimed_at,
            processing_started_at=processing_started_at,
            processing_completed_at=processing_completed_at,
            latency_ms=max(0, int(latency_ms)) if latency_ms is not None else None,
            attempt_history=[dict(item) for item in (attempt_history or []) if isinstance(item, dict)],
            created_at=now,
            updated_at=now,
        )
        self.paper_check_jobs.document(record.job_id).set(
            {
                "job_id": record.job_id,
                "user_id": record.user_id,
                "paper_id": record.paper_id,
                "fingerprint": record.fingerprint,
                "queue_partition": record.queue_partition,
                "priority": record.priority,
                "job_type": record.job_type,
                "status": record.status,
                "input": record.input_data,
                "result": record.result,
                "error": record.error,
                "retryable": record.retryable,
                "retry_count": record.retry_count,
                "max_retries": record.max_retries,
                "claimed_by": record.claimed_by,
                "claimed_at": record.claimed_at,
                "processing_started_at": record.processing_started_at,
                "processing_completed_at": record.processing_completed_at,
                "latency_ms": record.latency_ms,
                "attempt_history": record.attempt_history,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }
        )
        return record

    def get_paper_check_job(self, job_id: str) -> Optional[PaperCheckJob]:
        snapshot = self.paper_check_jobs.document(str(job_id)).get()
        if not snapshot.exists:
            return None
        return self._paper_check_job_from_doc(snapshot.to_dict() or {})

    def update_paper_check_job(
        self,
        job_id: str,
        updates: Dict[str, Any],
    ) -> Optional[PaperCheckJob]:
        current = self.get_paper_check_job(job_id)
        if current is None:
            return None

        payload: Dict[str, Any] = {}
        for key, value in (updates or {}).items():
            if key == "input_data":
                payload["input"] = dict(value or {})
            elif key in {"result"} and value is not None:
                payload[key] = value
            elif key in {"status", "error"}:
                if key == "status" and value is not None:
                    payload[key] = _normalize_job_status(value)
                else:
                    payload[key] = value
            elif key == "retryable":
                payload[key] = bool(value)
            elif key in {"retry_count", "max_retries"} and value is not None:
                payload[key] = max(0, int(value))
            elif key == "claimed_by":
                payload[key] = str(value or "") or None
            elif key == "claimed_at":
                payload[key] = value
            elif key == "fingerprint":
                payload[key] = str(value or "") or None
            elif key == "queue_partition":
                payload[key] = max(0, int(value)) if value is not None else None
            elif key == "priority":
                payload[key] = _normalize_job_priority(value)
            elif key == "job_type":
                payload[key] = _normalize_job_type(value)
            elif key in {"processing_started_at", "processing_completed_at"}:
                payload[key] = value
            elif key == "latency_ms":
                payload[key] = max(0, int(value)) if value is not None else None
            elif key == "attempt_history":
                payload[key] = [dict(item) for item in (value or []) if isinstance(item, dict)]
        if "status" in payload:
            _validate_job_transition(current.status, str(payload["status"]))
        payload["updated_at"] = _utcnow()
        self.paper_check_jobs.document(str(job_id)).set(payload, merge=True)
        return self.get_paper_check_job(job_id)

    def update_job_status(
        self,
        job_id: str,
        updates: Dict[str, Any],
    ) -> Optional[PaperCheckJob]:
        return self.update_paper_check_job(job_id, updates)

    @staticmethod
    def _paper_comparison_from_doc(doc: Dict[str, Any]) -> PaperComparison:
        return PaperComparison(
            id=str(doc["id"]),
            user_id=int(doc.get("user_id") or 0),
            paper_ids=[int(pid) for pid in (doc.get("paper_ids") or [])],
            optional_context=doc.get("optional_context"),
            fingerprint=doc.get("fingerprint"),
            result=doc.get("result"),
            created_at=doc.get("created_at") or _utcnow(),
        )

    def create_paper_comparison(
        self,
        *,
        id: str,
        user_id: int,
        paper_ids: List[int],
        optional_context: Optional[str] = None,
        fingerprint: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> PaperComparison:
        now = _utcnow()
        record = PaperComparison(
            id=id,
            user_id=int(user_id),
            paper_ids=[int(pid) for pid in paper_ids],
            optional_context=optional_context,
            fingerprint=fingerprint,
            result=result,
            created_at=now,
        )
        self.paper_comparisons.document(record.id).set(
            {
                "id": record.id,
                "user_id": record.user_id,
                "paper_ids": record.paper_ids,
                "optional_context": record.optional_context,
                "fingerprint": record.fingerprint,
                "result": record.result,
                "created_at": record.created_at,
            }
        )
        return record

    def get_paper_comparison(self, comparison_id: str) -> Optional[PaperComparison]:
        snapshot = self.paper_comparisons.document(str(comparison_id)).get()
        if not snapshot.exists:
            return None
        return self._paper_comparison_from_doc(snapshot.to_dict() or {})

    def find_paper_comparison_by_fingerprint(self, fingerprint: str) -> Optional[PaperComparison]:
        if not filter:
            for snapshot in self.paper_comparisons.where(
                filter=FieldFilter("fingerprint", "==", str(fingerprint))
            ).limit(1).stream():
                return self._paper_comparison_from_doc(snapshot.to_dict() or {})
            return None
        filter_obj = FieldFilter("fingerprint", "==", str(fingerprint))
        query = self.paper_comparisons.where(filter=filter_obj).limit(1)
        for snapshot in query.stream():
            return self._paper_comparison_from_doc(snapshot.to_dict() or {})
        return None

    @staticmethod
    def _same_claim_time(left: Optional[datetime], right: Optional[datetime]) -> bool:
        if left is None and right is None:
            return True
        if left is None or right is None:
            return False
        if left.tzinfo is None:
            left = left.replace(tzinfo=timezone.utc)
        if right.tzinfo is None:
            right = right.replace(tzinfo=timezone.utc)
        return abs((left - right).total_seconds()) < 0.001

    @staticmethod
    def _start_attempt_history(
        history: Sequence[Dict[str, Any]] | None,
        *,
        started_at: datetime,
        worker_id: str,
    ) -> list[Dict[str, Any]]:
        attempts = [dict(item) for item in (history or []) if isinstance(item, dict)]
        attempts.append(
            {
                "started_at": started_at,
                "ended_at": None,
                "status": "running",
                "worker_id": worker_id,
            }
        )
        return attempts

    @staticmethod
    def _finish_attempt_history(
        history: Sequence[Dict[str, Any]] | None,
        *,
        ended_at: datetime,
        status: str,
    ) -> list[Dict[str, Any]]:
        attempts = [dict(item) for item in (history or []) if isinstance(item, dict)]
        if not attempts:
            attempts.append(
                {
                    "started_at": ended_at,
                    "ended_at": ended_at,
                    "status": status,
                }
            )
            return attempts
        attempts[-1]["ended_at"] = ended_at
        attempts[-1]["status"] = status
        return attempts

    @staticmethod
    def _compute_latency_ms(started_at: Optional[datetime], ended_at: datetime) -> Optional[int]:
        if started_at is None:
            return None
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if ended_at.tzinfo is None:
            ended_at = ended_at.replace(tzinfo=timezone.utc)
        return max(0, int((ended_at - started_at).total_seconds() * 1000))

    def claim_next_job(self, worker_id: str) -> Optional[PaperCheckJob]:
        worker_token = str(worker_id or "").strip()
        if not worker_token:
            raise ValueError("worker_id is required")

        if firestore is None:
            docs = [
                snapshot.to_dict() or {}
                for snapshot in self.paper_check_jobs.where(
                    filter=FieldFilter("status", "==", "pending")
                ).stream()
            ]
            docs.sort(key=lambda doc: doc.get("created_at") or _utcnow())
            for doc in docs:
                now = _utcnow()
                claimed = self.update_job_status(
                    str(doc.get("job_id") or ""),
                    {
                        "status": "running",
                        "claimed_by": worker_token,
                        "claimed_at": now,
                        "processing_started_at": now,
                        "processing_completed_at": None,
                        "latency_ms": None,
                        "attempt_history": self._start_attempt_history(
                            doc.get("attempt_history") or [],
                            started_at=now,
                            worker_id=worker_token,
                        ),
                        "error": None,
                        "retryable": False,
                    },
                )
                if claimed is not None and claimed.status == "running" and claimed.claimed_by == worker_token:
                    return claimed
            return None

        candidate_query = self.paper_check_jobs.where(
            filter=FieldFilter("status", "==", "pending")
        ).order_by("created_at").limit(5)

        for snapshot in candidate_query.stream():
            reference = snapshot.reference
            transaction = self.db.transaction()

            @firestore.transactional
            def claim(transaction_obj, doc_ref):
                current = doc_ref.get(transaction=transaction_obj)
                if not current.exists:
                    return None
                doc = current.to_dict() or {}
                if _normalize_job_status(doc.get("status") or "pending") != "pending":
                    return None
                now = _utcnow()
                transaction_obj.set(
                    doc_ref,
                    {
                        "status": "running",
                        "claimed_by": worker_token,
                        "claimed_at": now,
                        "processing_started_at": now,
                        "processing_completed_at": None,
                        "latency_ms": None,
                        "attempt_history": self._start_attempt_history(
                            doc.get("attempt_history") or [],
                            started_at=now,
                            worker_id=worker_token,
                        ),
                        "error": None,
                        "retryable": False,
                        "updated_at": now,
                    },
                    merge=True,
                )
                doc.update(
                    {
                        "status": "running",
                        "claimed_by": worker_token,
                        "claimed_at": now,
                        "processing_started_at": now,
                        "processing_completed_at": None,
                        "latency_ms": None,
                        "attempt_history": self._start_attempt_history(
                            doc.get("attempt_history") or [],
                            started_at=now,
                            worker_id=worker_token,
                        ),
                        "error": None,
                        "retryable": False,
                        "updated_at": now,
                    }
                )
                return doc

            claimed = claim(transaction, reference)
            if claimed is None:
                continue
            return self._paper_check_job_from_doc(claimed)
        return None

    def get_stuck_jobs(self, timeout_seconds: int) -> list[PaperCheckJob]:
        cutoff = _utcnow() - timedelta(seconds=max(1, int(timeout_seconds or 1)))
        try:
            docs = [
                snapshot.to_dict() or {}
                for snapshot in self.paper_check_jobs.where(
                    filter=FieldFilter("status", "==", "running")
                ).where(
                    filter=FieldFilter("claimed_at", "<", cutoff)
                ).stream()
            ]
        except Exception:
            docs = [
                snapshot.to_dict() or {}
                for snapshot in self.paper_check_jobs.where(
                    filter=FieldFilter("status", "==", "running")
                ).stream()
            ]
        stale = []
        for doc in docs:
            claimed_at = doc.get("claimed_at")
            if claimed_at is None:
                stale.append(doc)
                continue
            if claimed_at.tzinfo is None:
                claimed_at = claimed_at.replace(tzinfo=timezone.utc)
            if claimed_at < cutoff:
                stale.append(doc)
        stale.sort(key=lambda doc: doc.get("claimed_at") or doc.get("updated_at") or _utcnow())
        return [self._paper_check_job_from_doc(doc) for doc in stale]

    def reset_job(self, job_id: str) -> Optional[PaperCheckJob]:
        return self.update_job_status(
            job_id,
            {
                "status": "pending",
                "claimed_by": None,
                "claimed_at": None,
                "processing_started_at": None,
                "processing_completed_at": None,
                "latency_ms": None,
                "retryable": False,
                "result": None,
            },
        )

    def requeue_paper_check_job(self, job_id: str) -> Optional[PaperCheckJob]:
        current = self.get_paper_check_job(job_id)
        if current is None:
            return None
        now = _utcnow()
        payload = {
            "status": "pending",
            "claimed_by": None,
            "claimed_at": None,
            "processing_started_at": None,
            "processing_completed_at": None,
            "latency_ms": None,
            "retryable": False,
            "error": None,
            "result": None,
            "updated_at": now,
        }

        if firestore is None:
            self.paper_check_jobs.document(str(job_id)).set(payload, merge=True)
            return self.get_paper_check_job(job_id)

        reference = self.paper_check_jobs.document(str(job_id))
        transaction = self.db.transaction()

        @firestore.transactional
        def requeue(transaction_obj, doc_ref):
            snapshot = doc_ref.get(transaction=transaction_obj)
            if not snapshot.exists:
                return None
            doc = snapshot.to_dict() or {}
            transaction_obj.set(doc_ref, payload, merge=True)
            doc.update(payload)
            return doc

        updated = requeue(transaction, reference)
        if updated is None:
            return None
        return self._paper_check_job_from_doc(updated)

    def claim_paper_check_job(
        self,
        job_id: str,
        *,
        worker_id: str,
        stale_before: Optional[datetime] = None,
    ) -> Optional[PaperCheckJob]:
        worker_token = str(worker_id or "").strip()
        if not worker_token:
            raise ValueError("worker_id is required")

        if firestore is None:
            current = self.get_paper_check_job(job_id)
            if current is None:
                return None
            if current.status in {"completed", "failed"}:
                return current
            updated_at = current.updated_at or current.claimed_at or current.created_at or _utcnow()
            can_claim = current.status == "pending" or (
                current.status == "running"
                and stale_before is not None
                and updated_at <= stale_before
            )
            if not can_claim:
                return current
            now = _utcnow()
            return self.update_paper_check_job(
                job_id,
                {
                    "status": "running",
                    "claimed_by": worker_token,
                    "claimed_at": now,
                    "error": None,
                    "retryable": False,
                    "result": None,
                    "processing_started_at": now,
                    "processing_completed_at": None,
                    "latency_ms": None,
                    "attempt_history": self._start_attempt_history(
                        current.attempt_history,
                        started_at=now,
                        worker_id=worker_token,
                    ),
                },
            )

        reference = self.paper_check_jobs.document(str(job_id))
        transaction = self.db.transaction()

        @firestore.transactional
        def claim(transaction_obj, doc_ref):
            snapshot = doc_ref.get(transaction=transaction_obj)
            if not snapshot.exists:
                return None
            doc = snapshot.to_dict() or {}
            status = _normalize_job_status(doc.get("status") or "pending")
            updated_at = doc.get("updated_at") or doc.get("claimed_at") or doc.get("created_at") or _utcnow()
            if status in {"completed", "failed"}:
                return doc
            can_claim = status == "pending" or (
                status == "running"
                and stale_before is not None
                and updated_at <= stale_before
            )
            if not can_claim:
                return doc
            now = _utcnow()
            transaction_obj.set(
                doc_ref,
                {
                    "status": "running",
                    "claimed_by": worker_token,
                    "claimed_at": now,
                    "error": None,
                    "retryable": False,
                    "result": None,
                    "processing_started_at": now,
                    "processing_completed_at": None,
                    "latency_ms": None,
                    "attempt_history": self._start_attempt_history(
                        doc.get("attempt_history") or [],
                        started_at=now,
                        worker_id=worker_token,
                    ),
                    "updated_at": now,
                },
                merge=True,
            )
            doc.update(
                {
                    "status": "running",
                    "claimed_by": worker_token,
                    "claimed_at": now,
                    "error": None,
                    "retryable": False,
                    "result": None,
                    "processing_started_at": now,
                    "processing_completed_at": None,
                    "latency_ms": None,
                    "attempt_history": self._start_attempt_history(
                        doc.get("attempt_history") or [],
                        started_at=now,
                        worker_id=worker_token,
                    ),
                    "updated_at": now,
                }
            )
            return doc

        claimed = claim(transaction, reference)
        if claimed is None:
            return None
        return self._paper_check_job_from_doc(claimed)

    def complete_paper_check_job(
        self,
        job_id: str,
        *,
        worker_id: Optional[str],
        claimed_at: Optional[datetime],
        result: Dict[str, Any],
    ) -> Optional[PaperCheckJob]:
        current = self.get_paper_check_job(job_id)
        if current is None:
            return None
        if current.status == "completed":
            return current

        worker_token = str(worker_id or "").strip() or None
        if firestore is None:
            if current.status != "running":
                return current
            if worker_token and current.claimed_by != worker_token:
                return current
            if claimed_at is not None and not self._same_claim_time(current.claimed_at, claimed_at):
                return current
            now = _utcnow()
            return self.update_job_status(
                job_id,
                {
                    "status": "completed",
                    "result": result,
                    "error": None,
                    "retryable": False,
                    "processing_completed_at": now,
                    "latency_ms": self._compute_latency_ms(
                        current.processing_started_at or current.claimed_at,
                        now,
                    ),
                    "attempt_history": self._finish_attempt_history(
                        current.attempt_history,
                        ended_at=now,
                        status="completed",
                    ),
                },
            )

        reference = self.paper_check_jobs.document(str(job_id))
        transaction = self.db.transaction()

        @firestore.transactional
        def complete(transaction_obj, doc_ref):
            snapshot = doc_ref.get(transaction=transaction_obj)
            if not snapshot.exists:
                return None
            doc = snapshot.to_dict() or {}
            if str(doc.get("status") or "") == "completed":
                return doc
            if str(doc.get("status") or "") != "running":
                return doc
            current_claimed_by = str(doc.get("claimed_by") or "") or None
            current_claimed_at = doc.get("claimed_at")
            if worker_token and current_claimed_by != worker_token:
                return doc
            if claimed_at is not None and not self._same_claim_time(current_claimed_at, claimed_at):
                return doc
            now = _utcnow()
            transaction_obj.set(
                doc_ref,
                {
                    "status": "completed",
                    "result": result,
                    "error": None,
                    "retryable": False,
                    "processing_completed_at": now,
                    "latency_ms": self._compute_latency_ms(
                        doc.get("processing_started_at") or current_claimed_at,
                        now,
                    ),
                    "attempt_history": self._finish_attempt_history(
                        doc.get("attempt_history") or [],
                        ended_at=now,
                        status="completed",
                    ),
                    "updated_at": now,
                },
                merge=True,
            )
            doc.update(
                {
                    "status": "completed",
                    "result": result,
                    "error": None,
                    "retryable": False,
                    "processing_completed_at": now,
                    "latency_ms": self._compute_latency_ms(
                        doc.get("processing_started_at") or current_claimed_at,
                        now,
                    ),
                    "attempt_history": self._finish_attempt_history(
                        doc.get("attempt_history") or [],
                        ended_at=now,
                        status="completed",
                    ),
                    "updated_at": now,
                }
            )
            return doc

        completed = complete(transaction, reference)
        if completed is None:
            return None
        return self._paper_check_job_from_doc(completed)

    def fail_or_requeue_paper_check_job(
        self,
        job_id: str,
        *,
        worker_id: Optional[str],
        claimed_at: Optional[datetime],
        error_message: str,
        retryable: bool,
    ) -> Optional[PaperCheckJob]:
        current = self.get_paper_check_job(job_id)
        if current is None:
            return None

        worker_token = str(worker_id or "").strip() or None
        if firestore is None:
            if current.status != "running":
                return current
            if worker_token and current.claimed_by != worker_token:
                return current
            if claimed_at is not None and not self._same_claim_time(current.claimed_at, claimed_at):
                return current
            next_retry_count = current.retry_count + 1 if retryable else current.retry_count
            should_retry = bool(retryable) and next_retry_count <= current.max_retries
            now = _utcnow()
            if should_retry:
                return self.update_job_status(
                    job_id,
                    {
                        "status": "pending",
                        "error": str(error_message or "Paper check failed."),
                        "retryable": True,
                        "retry_count": next_retry_count,
                        "claimed_by": None,
                        "claimed_at": None,
                        "processing_started_at": None,
                        "processing_completed_at": None,
                        "latency_ms": None,
                        "attempt_history": self._finish_attempt_history(
                            current.attempt_history,
                            ended_at=now,
                            status="retry_pending",
                        ),
                        "result": None,
                    },
                )
            return self.update_job_status(
                job_id,
                {
                    "status": "failed",
                    "error": str(error_message or "Paper check failed."),
                    "retryable": bool(retryable),
                    "retry_count": next_retry_count,
                    "claimed_by": None,
                    "claimed_at": None,
                    "processing_completed_at": now,
                    "latency_ms": self._compute_latency_ms(
                        current.processing_started_at or current.claimed_at,
                        now,
                    ),
                    "attempt_history": self._finish_attempt_history(
                        current.attempt_history,
                        ended_at=now,
                        status="failed",
                    ),
                    "result": None,
                },
            )

        reference = self.paper_check_jobs.document(str(job_id))
        transaction = self.db.transaction()

        @firestore.transactional
        def fail_or_requeue(transaction_obj, doc_ref):
            snapshot = doc_ref.get(transaction=transaction_obj)
            if not snapshot.exists:
                return None
            doc = snapshot.to_dict() or {}
            if str(doc.get("status") or "") != "running":
                return doc
            current_claimed_by = str(doc.get("claimed_by") or "") or None
            current_claimed_at = doc.get("claimed_at")
            if worker_token and current_claimed_by != worker_token:
                return doc
            if claimed_at is not None and not self._same_claim_time(current_claimed_at, claimed_at):
                return doc
            current_retry_count = max(0, int(doc.get("retry_count") or 0))
            raw_max_retries = doc.get("max_retries")
            max_retries = max(0, int(2 if raw_max_retries is None else raw_max_retries))
            next_retry_count = current_retry_count + 1 if retryable else current_retry_count
            should_retry = bool(retryable) and next_retry_count <= max_retries
            now = _utcnow()
            payload = {
                "status": "pending" if should_retry else "failed",
                "error": str(error_message or "Paper check failed."),
                "retryable": bool(retryable),
                "retry_count": next_retry_count,
                "claimed_by": None,
                "claimed_at": None,
                "processing_started_at": None if should_retry else doc.get("processing_started_at"),
                "processing_completed_at": None if should_retry else now,
                "latency_ms": None
                if should_retry
                else self._compute_latency_ms(doc.get("processing_started_at") or current_claimed_at, now),
                "attempt_history": self._finish_attempt_history(
                    doc.get("attempt_history") or [],
                    ended_at=now,
                    status="retry_pending" if should_retry else "failed",
                ),
                "result": None,
                "updated_at": now,
            }
            transaction_obj.set(doc_ref, payload, merge=True)
            doc.update(payload)
            return doc

        updated = fail_or_requeue(transaction, reference)
        if updated is None:
            return None
        return self._paper_check_job_from_doc(updated)

    def find_reusable_paper_check_job(
        self,
        *,
        user_id: int,
        fingerprint: str,
    ) -> Optional[PaperCheckJob]:
        target_fingerprint = str(fingerprint or "").strip()
        if not target_fingerprint:
            return None
        docs = [
            snapshot.to_dict() or {}
            for snapshot in self.paper_check_jobs.where(
                filter=FieldFilter("user_id", "==", int(user_id))
            ).where(
                filter=FieldFilter("fingerprint", "==", target_fingerprint)
            ).stream()
        ]
        rows = [self._paper_check_job_from_doc(doc) for doc in docs]
        reusable = [row for row in rows if row.status in {"pending", "running", "completed"}]
        if not reusable:
            return None
        completed = [row for row in reusable if row.status == "completed" and row.result]
        if completed:
            completed.sort(key=lambda row: row.processing_completed_at or row.updated_at or row.created_at, reverse=True)
            return completed[0]
        reusable.sort(key=lambda row: row.created_at or _utcnow(), reverse=True)
        return reusable[0]

    def count_active_jobs_for_user(self, user_id: int) -> int:
        count = 0
        for snapshot in self.paper_check_jobs.where(
            filter=FieldFilter("user_id", "==", int(user_id))
        ).stream():
            status = str((snapshot.to_dict() or {}).get("status") or "")
            if status in {"pending", "running"}:
                count += 1
        return count

    def get_paper_check_job_metrics(self, timeout_seconds: int) -> Dict[str, Any]:
        docs = [snapshot.to_dict() or {} for snapshot in self.paper_check_jobs.stream()]
        total_jobs_created = len(docs)
        jobs_completed = 0
        jobs_failed = 0
        jobs_pending = 0
        jobs_running = 0
        total_latency = 0
        latency_samples = 0
        retries_used = 0
        deduped_completed = 0
        pending_by_priority: Dict[str, int] = {"high": 0, "normal": 0, "low": 0}
        pending_by_type: Dict[str, int] = {"fast": 0, "heavy": 0}
        for doc in docs:
            status = str(doc.get("status") or "")
            if status == "completed":
                jobs_completed += 1
                if doc.get("fingerprint"):
                    deduped_completed += 1
            elif status == "failed":
                jobs_failed += 1
            elif status == "pending":
                jobs_pending += 1
                priority = _normalize_job_priority(doc.get("priority"))
                pending_by_priority[priority] = int(pending_by_priority.get(priority, 0) + 1)
                job_type = _normalize_job_type(doc.get("job_type"))
                pending_by_type[job_type] = int(pending_by_type.get(job_type, 0) + 1)
            elif status == "running":
                jobs_running += 1
            if doc.get("latency_ms") is not None:
                total_latency += max(0, int(doc.get("latency_ms") or 0))
                latency_samples += 1
            retries_used += max(0, int(doc.get("retry_count") or 0))
        retry_jobs = sum(1 for doc in docs if max(0, int(doc.get("retry_count") or 0)) > 0)
        avg_latency = round(total_latency / latency_samples, 2) if latency_samples > 0 else 0.0
        retry_rate = round((retry_jobs / total_jobs_created), 4) if total_jobs_created > 0 else 0.0
        return {
            "total_jobs_created": total_jobs_created,
            "jobs_completed": jobs_completed,
            "jobs_failed": jobs_failed,
            "jobs_pending": jobs_pending,
            "jobs_running": jobs_running,
            "avg_latency_ms": avg_latency,
            "retry_rate": retry_rate,
            "total_retries": retries_used,
            "stuck_job_count": len(self.get_stuck_jobs(timeout_seconds)),
            "completed_with_fingerprint": deduped_completed,
            "pending_by_priority": pending_by_priority,
            "pending_by_type": pending_by_type,
        }

    def list_pending_jobs_for_dispatch(
        self,
        *,
        older_than_seconds: int,
        queue_partition: Optional[int] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[PaperCheckJob]:
        cutoff = _utcnow() - timedelta(seconds=max(0, int(older_than_seconds or 0)))
        target_partition = max(0, int(queue_partition)) if queue_partition is not None else None
        target_job_type = _normalize_job_type(job_type) if job_type is not None else None
        docs: list[dict[str, Any]]
        try:
            query = self.paper_check_jobs.where(
                filter=FieldFilter("status", "==", "pending")
            )
            if target_partition is not None:
                query = query.where(
                    filter=FieldFilter("queue_partition", "==", target_partition)
                )
            if target_job_type is not None:
                query = query.where(
                    filter=FieldFilter("job_type", "==", target_job_type)
                )
            query = query.where(
                filter=FieldFilter("updated_at", "<=", cutoff)
            )
            docs = [snapshot.to_dict() or {} for snapshot in query.stream()]
        except Exception:
            docs = [
                snapshot.to_dict() or {}
                for snapshot in self.paper_check_jobs.where(
                    filter=FieldFilter("status", "==", "pending")
                ).stream()
            ]
        filtered = []
        for doc in docs:
            if target_partition is not None and int(doc.get("queue_partition") or -1) != target_partition:
                continue
            if target_job_type is not None and _normalize_job_type(doc.get("job_type")) != target_job_type:
                continue
            updated_at = doc.get("updated_at") or doc.get("created_at") or _utcnow()
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if updated_at <= cutoff:
                filtered.append(doc)
        filtered.sort(
            key=lambda doc: (
                -_JOB_PRIORITY_ORDER[_normalize_job_priority(doc.get("priority"))],
                doc.get("updated_at") or doc.get("created_at") or _utcnow(),
            )
        )
        if limit is not None:
            filtered = filtered[: max(0, int(limit))]
        return [self._paper_check_job_from_doc(doc) for doc in filtered]

    def count_jobs_by_status(
        self,
        *,
        statuses: Sequence[str],
        queue_partition: Optional[int] = None,
        job_type: Optional[str] = None,
    ) -> int:
        target_statuses = {_normalize_job_status(value) for value in statuses if value}
        if not target_statuses:
            return 0
        target_partition = max(0, int(queue_partition)) if queue_partition is not None else None
        target_job_type = _normalize_job_type(job_type) if job_type is not None else None
        count = 0
        for snapshot in self.paper_check_jobs.stream():
            doc = snapshot.to_dict() or {}
            status = _normalize_job_status(doc.get("status") or "pending")
            if status not in target_statuses:
                continue
            if target_partition is not None and int(doc.get("queue_partition") or -1) != target_partition:
                continue
            if target_job_type is not None and _normalize_job_type(doc.get("job_type")) != target_job_type:
                continue
            count += 1
        return count

    def list_user_jobs(
        self, user_id: int, *, limit: Optional[int] = None
    ) -> list[PaperCheckJob]:
        docs = [
            (snapshot.to_dict() or {})
            for snapshot in self.paper_check_jobs.where(
                filter=FieldFilter("user_id", "==", int(user_id))
            ).stream()
        ]
        docs.sort(key=lambda doc: doc.get("created_at") or _utcnow(), reverse=True)
        if limit is not None:
            docs = docs[: max(0, int(limit))]
        return [self._paper_check_job_from_doc(doc) for doc in docs]

    def list_data_rights_requests_for_user(
        self,
        user_id: int,
        *,
        limit: Optional[int] = None,
    ) -> list[DataRightsRequest]:
        docs = [
            (snapshot.to_dict() or {})
            for snapshot in self.data_rights_requests.where(
                filter=FieldFilter("user_id", "==", user_id)
            ).stream()
        ]
        docs.sort(key=lambda doc: doc.get("submitted_at") or _utcnow(), reverse=True)
        if limit is not None:
            docs = docs[: max(0, int(limit))]
        return [self._data_rights_from_doc(doc) for doc in docs]

    def count_users(self) -> int:
        return sum(1 for _ in self.users.stream())

    def count_workspaces(self) -> int:
        return sum(1 for _ in self.workspaces.stream())

    def count_papers(self) -> int:
        return sum(1 for _ in self.papers.stream())

    def count_chats(self) -> int:
        return sum(1 for _ in self.chats.stream())

    def count_documents_for_user(self, user_id: int) -> int:
        return len(self.list_workspace_documents_for_user(user_id))

    def delete_user_account(self, user_id: int) -> None:
        for workspace in self.list_workspaces_for_user(user_id):
            self.delete_workspace_graph(workspace.id)
        for collection in (
            self.workspace_documents,
            self.workspace_files,
            self.paper_check_jobs,
            self.search_history,
            self.data_rights_requests,
        ):
            for snapshot in collection.where(
                filter=FieldFilter("user_id", "==", user_id)
            ).stream():
                snapshot.reference.delete()
        state = self.get_session_state_for_user(user_id)
        if state and state.id is not None:
            self.user_session_state.document(str(state.id)).delete()
        self.users.document(str(user_id)).delete()

    def delete_workspace_graph(self, workspace_id: int) -> None:
        for collection in (
            self.papers,
            self.chats,
            self.workspace_documents,
            self.workspace_files,
        ):
            for snapshot in collection.where(
                filter=FieldFilter("workspace_id", "==", workspace_id)
            ).stream():
                snapshot.reference.delete()
        self.workspaces.document(str(workspace_id)).delete()


def get_research_repository() -> ResearchRepository:
    """
    Resolve the active ResearchRepository.

    Local/dev safety:
    - If Firestore credentials are missing/misconfigured, we fall back to an
      in-memory repository so the backend can still run without 500s.

    Production:
    - Set USE_FIRESTORE=true (default) and configure Firebase Admin / ADC.
    """
    use_firestore = str(os.getenv("USE_FIRESTORE", "true") or "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
    )
    if use_firestore:
        try:
            return FirebaseResearchRepository()  # type: ignore[return-value]
        except Exception as exc:  # pragma: no cover
            logging.getLogger(__name__).warning(
                "Falling back to InMemoryResearchRepository: %s", exc
            )
    return get_in_memory_repository()


class InMemoryResearchRepository:
    """
    Minimal in-memory ResearchRepository implementation for local development.

    Designed to prevent runtime crashes when Firestore credentials are not set.
    Not intended for production use.
    """

    def __init__(self):
        self.db = None
        self._lock = Lock()
        self._counters: Dict[str, int] = {}
        self._users: Dict[int, User] = {}
        self._workspaces: Dict[int, Workspace] = {}
        self._papers: Dict[int, Paper] = {}
        self._paper_comparisons: Dict[str, PaperComparison] = {}
        self._research_reports: Dict[str, ResearchReport] = {}
        self._user_session_state: Dict[int, UserSessionState] = {}
        self._workspace_documents: Dict[int, WorkspaceDocument] = {}

    def _next_id(self, key: str) -> int:
        with self._lock:
            self._counters[key] = int(self._counters.get(key, 0)) + 1
            return int(self._counters[key])

    # --- Users ---------------------------------------------------------------
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self._users.get(int(user_id))

    def get_user_by_email(self, email: str) -> Optional[User]:
        needle = _normalize_email_key(email)
        if not needle:
            return None
        for user in self._users.values():
            if _normalize_email_key(user.email) == needle:
                return user
        for user in self._users.values():
            if _normalize_email_key(user.google_email or "") == needle:
                return user
        return None

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        needle = str(google_id or "").strip()
        if not needle:
            return None
        for user in self._users.values():
            if str(user.google_id or "").strip() == needle:
                return user
        return None

    def get_user_by_verification_token(self, token: str) -> Optional[User]:
        needle = str(token or "").strip()
        if not needle:
            return None
        for user in self._users.values():
            if str(user.verification_token or "").strip() == needle:
                return user
        return None

    def list_users_for_normalized_email(self, normalized_email: str) -> list[User]:
        needle = _normalize_email_key(normalized_email)
        if not needle:
            return []
        results: list[User] = []
        for user in self._users.values():
            if _normalize_email_key(user.email) == needle or _normalize_email_key(user.google_email or "") == needle:
                results.append(user)
        results.sort(key=lambda u: int(u.id or 0))
        return results

    def list_users(self, *, query: Optional[str] = None, limit: Optional[int] = None, offset: int = 0) -> list[User]:
        items = list(self._users.values())
        needle = str(query or "").strip().lower()
        if needle:
            items = [u for u in items if needle in str(u.email or "").lower() or needle in str(u.name or "").lower()]
        items.sort(key=lambda u: (-(u.created_at or _utcnow()).timestamp(), -int(u.id or 0)))
        items = items[max(0, int(offset)) :]
        if limit is not None:
            items = items[: max(0, int(limit))]
        return items

    def create_user(
        self,
        *,
        email: str,
        hashed_password: Optional[str] = None,
        google_id: Optional[str] = None,
        google_email: Optional[str] = None,
        name: Optional[str] = None,
        profile_pic: Optional[str] = None,
        is_active: bool = True,
        is_verified: bool = False,
        verification_token: Optional[str] = None,
        verification_token_expires: Optional[datetime] = None,
        has_completed_onboarding: bool = False,
    ) -> User:
        now = _utcnow()
        user = User(
            id=self._next_id("user_id"),
            email=_normalize_email_key(email),
            hashed_password=hashed_password,
            google_id=google_id,
            google_email=_normalize_email_key(google_email) if google_email else None,
            name=name,
            profile_pic=profile_pic,
            is_active=bool(is_active),
            is_verified=bool(is_verified),
            verification_token=verification_token,
            verification_token_expires=verification_token_expires,
            role="user",
            created_at=now,
            updated_at=now,
            has_completed_onboarding=bool(has_completed_onboarding),
        )
        self._users[int(user.id)] = user
        return user

    def merge_user_accounts(self, primary_user_id: int, secondary_user_id: int) -> None:
        if primary_user_id == secondary_user_id:
            return
        secondary = self._users.pop(int(secondary_user_id), None)
        if secondary is None:
            return
        for ws in self._workspaces.values():
            if int(ws.user_id) == int(secondary_user_id):
                ws.user_id = int(primary_user_id)
        for state in self._user_session_state.values():
            if int(state.user_id) == int(secondary_user_id):
                state.user_id = int(primary_user_id)

    # --- Workspaces / Papers -------------------------------------------------
    def list_workspaces_for_user(self, user_id: int) -> list[Workspace]:
        items = [ws for ws in self._workspaces.values() if int(ws.user_id) == int(user_id)]
        items.sort(key=lambda ws: (-(ws.created_at or _utcnow()).timestamp(), -int(ws.id or 0)))
        return items

    def find_workspace_for_user(self, workspace_id: int, user_id: int) -> Optional[Workspace]:
        ws = self._workspaces.get(int(workspace_id))
        if ws and int(ws.user_id) == int(user_id):
            return ws
        return None

    def find_workspace_by_name_for_user(self, user_id: int, name: str) -> Optional[Workspace]:
        needle = str(name or "").strip().lower()
        if not needle:
            return None
        for ws in self._workspaces.values():
            if int(ws.user_id) == int(user_id) and str(ws.name or "").strip().lower() == needle:
                return ws
        return None

    def create_workspace(self, user_id: int, name: str, description: Optional[str] = None) -> Workspace:
        ws = Workspace(
            id=self._next_id("workspace_id"),
            name=str(name or "").strip(),
            description=description,
            user_id=int(user_id),
            created_at=_utcnow(),
        )
        self._workspaces[int(ws.id)] = ws
        return ws

    def get_or_create_default_workspace(self, user_id: int) -> Workspace:
        existing = self.find_workspace_by_name_for_user(int(user_id), "Default Workspace")
        if existing:
            return existing
        return self.create_workspace(int(user_id), "Default Workspace", "Auto-created default workspace.")

    def workspace_exists_for_user(self, workspace_id: int, user_id: int) -> bool:
        return self.find_workspace_for_user(int(workspace_id), int(user_id)) is not None

    def list_papers_for_workspace(self, workspace_id: int, paper_ids: Optional[Sequence[int]] = None) -> list[Paper]:
        allowed = {int(pid) for pid in paper_ids} if paper_ids else None
        items = [p for p in self._papers.values() if int(p.workspace_id) == int(workspace_id)]
        if allowed is not None:
            items = [p for p in items if int(p.id) in allowed]
        items.sort(key=lambda p: int(p.id or 0))
        return items

    def find_paper_for_user(self, paper_id: int, user_id: int) -> Optional[Paper]:
        paper = self._papers.get(int(paper_id))
        if not paper:
            return None
        if not self.workspace_exists_for_user(int(paper.workspace_id), int(user_id)):
            return None
        return paper

    def delete_paper_for_user(self, paper_id: int, user_id: int) -> bool:
        paper = self.find_paper_for_user(int(paper_id), int(user_id))
        if not paper:
            return False
        self._papers.pop(int(paper_id), None)
        return True

    def create_paper(
        self,
        workspace_id: int,
        title: str,
        authors: str,
        abstract: str,
        url: Optional[str] = None,
        pdf_url: Optional[str] = None,
    ) -> Paper:
        paper = Paper(
            id=self._next_id("paper_id"),
            title=str(title or ""),
            authors=str(authors or ""),
            abstract=str(abstract or ""),
            url=url,
            pdf_url=pdf_url,
            workspace_id=int(workspace_id),
        )
        self._papers[int(paper.id)] = paper
        return paper

    # --- Comparisons / Reports (caching) ------------------------------------
    def create_paper_comparison(
        self,
        *,
        id: str,
        user_id: int,
        paper_ids: List[int],
        optional_context: Optional[str] = None,
        fingerprint: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> PaperComparison:
        record = PaperComparison(
            id=str(id),
            user_id=int(user_id),
            paper_ids=[int(pid) for pid in (paper_ids or [])],
            optional_context=optional_context,
            fingerprint=fingerprint,
            result=result,
            created_at=_utcnow(),
        )
        self._paper_comparisons[record.id] = record
        return record

    def get_paper_comparison(self, comparison_id: str) -> Optional[PaperComparison]:
        return self._paper_comparisons.get(str(comparison_id))

    def find_paper_comparison_by_fingerprint(self, fingerprint: str) -> Optional[PaperComparison]:
        needle = str(fingerprint or "").strip()
        if not needle:
            return None
        for item in self._paper_comparisons.values():
            if str(item.fingerprint or "") == needle:
                return item
        return None

    def create_research_report(
        self,
        *,
        id: str,
        user_id: int,
        paper_ids: List[int],
        topic: Optional[str] = None,
        fingerprint: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> ResearchReport:
        record = ResearchReport(
            id=str(id),
            user_id=int(user_id),
            paper_ids=[int(pid) for pid in (paper_ids or [])],
            topic=topic,
            fingerprint=fingerprint,
            result=result,
            created_at=_utcnow(),
        )
        self._research_reports[record.id] = record
        return record

    def get_research_report(self, report_id: str) -> Optional[ResearchReport]:
        return self._research_reports.get(str(report_id))

    def find_research_report_by_fingerprint(self, fingerprint: str) -> Optional[ResearchReport]:
        needle = str(fingerprint or "").strip()
        if not needle:
            return None
        for item in self._research_reports.values():
            if str(item.fingerprint or "") == needle:
                return item
        return None

    # --- Docspace used for "save to workspace" ------------------------------
    def get_docspace_document(self, workspace_id: int, user_id: int) -> Optional[WorkspaceDocument]:
        for doc in self._workspace_documents.values():
            if int(doc.workspace_id) == int(workspace_id) and int(doc.user_id) == int(user_id):
                return doc
        return None

    def list_workspace_documents_for_user(self, user_id: int) -> list[WorkspaceDocument]:
        docs = [d for d in self._workspace_documents.values() if int(d.user_id) == int(user_id)]
        docs.sort(key=lambda d: (d.updated_at or _utcnow()), reverse=True)
        return docs

    def create_docspace_document(
        self,
        workspace_id: int,
        user_id: int,
        title: str,
        content: str = "",
        version: int = 1,
    ) -> WorkspaceDocument:
        now = _utcnow()
        doc = WorkspaceDocument(
            id=self._next_id("workspace_document_id"),
            workspace_id=int(workspace_id),
            user_id=int(user_id),
            title=str(title or "Research Notes"),
            content=str(content or ""),
            version=int(version or 1),
            created_at=now,
            updated_at=now,
        )
        self._workspace_documents[int(doc.id)] = doc
        return doc

    def save(self, instance: object) -> object:
        # Keep save conservative; only support document/user/session updates used by UI.
        if isinstance(instance, User):
            resolved_user_id = _coerce_int(getattr(instance, "id", None), 0)
            if resolved_user_id <= 0:
                created = self.create_user(
                    email=instance.email,
                    hashed_password=instance.hashed_password,
                    google_id=instance.google_id,
                    google_email=instance.google_email,
                    name=instance.name,
                    profile_pic=instance.profile_pic,
                    is_active=instance.is_active,
                    is_verified=instance.is_verified,
                    verification_token=instance.verification_token,
                    verification_token_expires=instance.verification_token_expires,
                    has_completed_onboarding=bool(
                        getattr(instance, "has_completed_onboarding", False)
                    ),
                )
                instance.id = created.id
                instance.created_at = created.created_at
                instance.updated_at = created.updated_at
                return instance
            instance.id = resolved_user_id
            instance.updated_at = _utcnow()
            self._users[int(instance.id)] = instance
            return instance
        if isinstance(instance, UserSessionState) and instance.id is not None:
            instance.updated_at = _utcnow()
            self._user_session_state[int(instance.id)] = instance
            return instance
        if isinstance(instance, WorkspaceDocument) and instance.id is not None:
            self._workspace_documents[int(instance.id)] = instance
            return instance
        return instance


_IN_MEMORY_REPO: Optional[InMemoryResearchRepository] = None


def get_in_memory_repository() -> InMemoryResearchRepository:
    global _IN_MEMORY_REPO
    if _IN_MEMORY_REPO is None:
        _IN_MEMORY_REPO = InMemoryResearchRepository()
    return _IN_MEMORY_REPO
