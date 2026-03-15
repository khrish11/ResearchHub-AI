from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)
    google_email = Column(String, nullable=True)
    name = Column(String, nullable=True)
    profile_pic = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    verification_token_expires = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    workspaces = relationship("Workspace", back_populates="owner")
    search_history = relationship("SearchHistory", back_populates="user")
    session_state = relationship("UserSessionState", back_populates="user", uselist=False)
    documents = relationship("WorkspaceDocument", back_populates="owner")
    data_rights_requests = relationship("DataRightsRequest", back_populates="user")
    refresh_sessions = relationship("RefreshSession", back_populates="user")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), default=utc_now)

    owner = relationship("User", back_populates="workspaces")
    papers = relationship("Paper", back_populates="workspace")
    chats = relationship("Chat", back_populates="workspace")
    document = relationship("WorkspaceDocument", back_populates="workspace", uselist=False)


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    authors = Column(String)
    abstract = Column(Text)
    url = Column(String, nullable=True)
    doi = Column(String, nullable=True)
    bibcode = Column(String, nullable=True)
    source = Column(String, nullable=True)
    pdf_url = Column(String, nullable=True)
    institutional_url = Column(String, nullable=True)
    access_type = Column(String, nullable=True)
    full_text_available = Column(Boolean, default=False)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))

    workspace = relationship("Workspace", back_populates="papers")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text)
    response = Column(Text)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    timestamp = Column(DateTime(timezone=True), default=utc_now)

    workspace = relationship("Workspace", back_populates="chats")


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    query = Column(String, index=True)
    source = Column(String, default="global_merged")
    result_count = Column(Integer, default=0)
    filters_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    user = relationship("User", back_populates="search_history")


class UserSessionState(Base):
    __tablename__ = "user_session_state"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True)
    page_path = Column(String, default="/home")
    workspace_id = Column(Integer, nullable=True)
    last_query = Column(String, nullable=True)
    draft_text = Column(Text, nullable=True)
    extra_json = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="session_state")


class WorkspaceDocument(Base):
    __tablename__ = "workspace_documents"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    title = Column(String, default="Research Notes")
    content = Column(Text, default="")
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    workspace = relationship("Workspace", back_populates="document")
    owner = relationship("User", back_populates="documents")


class WorkspaceFile(Base):
    __tablename__ = "workspace_files"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=True, index=True)
    kind = Column(String, index=True)
    filename = Column(String)
    storage_bucket = Column(String)
    storage_path = Column(String, unique=True, index=True)
    download_url = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)


class DataRightsRequest(Base):
    __tablename__ = "data_rights_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    email = Column(String, index=True)
    request_type = Column(String, index=True)
    jurisdiction = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    status = Column(String, default="submitted", index=True)
    submitted_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="data_rights_requests")


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token_hash = Column(String, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    replaced_by_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    user = relationship("User", back_populates="refresh_sessions")
