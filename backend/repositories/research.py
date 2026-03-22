from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional, Protocol, Sequence

from fastapi import Depends, HTTPException


try:
    from google.cloud import firestore
    from google.oauth2 import service_account
except Exception:  # pragma: no cover - optional until Firebase path is enabled
    firestore = None
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
        )

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
        return self._user_from_doc(snapshot.to_dict() or {})

    def get_user_by_email(self, email: str) -> Optional[User]:
        normalized = _normalize_email_key(email)
        if not normalized:
            return None
        return next(iter(self.list_users_for_normalized_email(normalized)), None)

    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        target = str(google_id or "").strip()
        if not target:
            return None
        for snapshot in self.users.where("google_id", "==", target).stream():
            return self._user_from_doc(snapshot.to_dict() or {})
        return None

    def get_user_by_verification_token(self, token: str) -> Optional[User]:
        value = str(token or "").strip()
        if not value:
            return None
        for snapshot in self.users.where("verification_token", "==", value).stream():
            return self._user_from_doc(snapshot.to_dict() or {})
        return None

    def list_users_for_normalized_email(self, normalized_email: str) -> list[User]:
        normalized = _normalize_email_key(normalized_email)
        if not normalized:
            return []
        docs: list[Dict[str, Any]] = []
        seen_ids: set[int] = set()
        for snapshot in self.users.where("email", "==", normalized).stream():
            doc = snapshot.to_dict() or {}
            doc_id = int(doc.get("id") or 0)
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            docs.append(doc)
        for snapshot in self.users.where("google_email", "==", normalized).stream():
            doc = snapshot.to_dict() or {}
            doc_id = int(doc.get("id") or 0)
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            docs.append(doc)
        docs.sort(key=lambda doc: int(doc.get("id") or 0))
        return [self._user_from_doc(doc) for doc in docs]

    def list_users(
        self,
        *,
        query: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[User]:
        docs = [(snapshot.to_dict() or {}) for snapshot in self.users.stream()]
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
                -int(doc.get("id") or 0),
            )
        )
        docs = docs[max(0, int(offset)) :]
        if limit is not None:
            docs = docs[: max(0, int(limit))]
        return [self._user_from_doc(doc) for doc in docs]

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
            "user_id", "==", secondary_user_id
        ).stream():
            doc = snapshot.to_dict() or {}
            doc["user_id"] = primary_user_id
            snapshot.reference.set(doc)
        for collection in (
            self.search_history,
            self.workspace_documents,
            self.workspace_files,
            self.data_rights_requests,
        ):
            for snapshot in collection.where(
                "user_id", "==", secondary_user_id
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
        for snapshot in self.papers.where("user_id", "==", user_id).stream():
            doc = snapshot.to_dict() or {}
            workspace_id = doc.get("workspace_id")
            if workspace_id is None:
                continue
            workspace_key = int(workspace_id)
            paper_counts[workspace_key] = paper_counts.get(workspace_key, 0) + 1

        docs = [
            (snapshot.to_dict() or {})
            for snapshot in self.workspaces.where("user_id", "==", user_id).stream()
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
        for snapshot in self.workspaces.where("user_id", "==", user_id).stream():
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
        for snapshot in self.workspaces.where("user_id", "==", user_id).stream():
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
        for snapshot in self.papers.where("workspace_id", "==", workspace_id).stream():
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
                "workspace_id", "==", workspace_id
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
            for snapshot in self.search_history.where("user_id", "==", user_id).stream()
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
        for snapshot in self.search_history.where("user_id", "==", user_id).stream():
            snapshot.reference.delete()
            deleted += 1
        return deleted

    def get_session_state_for_user(self, user_id: int) -> Optional[UserSessionState]:
        for snapshot in self.user_session_state.where(
            "user_id", "==", user_id
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
            if instance.id is None:
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
                return instance
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
            "workspace_id", "==", workspace_id
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
                "user_id", "==", user_id
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
            "workspace_id", "==", workspace_id
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
        for snapshot in self.workspace_files.where("paper_id", "==", paper_id).stream():
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

    def list_data_rights_requests_for_user(
        self,
        user_id: int,
        *,
        limit: Optional[int] = None,
    ) -> list[DataRightsRequest]:
        docs = [
            (snapshot.to_dict() or {})
            for snapshot in self.data_rights_requests.where(
                "user_id", "==", user_id
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
            self.search_history,
            self.data_rights_requests,
        ):
            for snapshot in collection.where("user_id", "==", user_id).stream():
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
                "workspace_id", "==", workspace_id
            ).stream():
                snapshot.reference.delete()
        self.workspaces.document(str(workspace_id)).delete()


def get_research_repository() -> ResearchRepository:
    return FirebaseResearchRepository()  # type: ignore[return-value]
