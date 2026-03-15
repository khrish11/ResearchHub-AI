"""Initial schema with refresh sessions and timezone-aware timestamps.

Revision ID: 20260315_0001
Revises:
Create Date: 2026-03-15 10:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260315_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind: sa.engine.Connection) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    return {str(column["name"]) for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    return {str(index["name"]) for index in sa.inspect(bind).get_indexes(table_name)}


def _ensure_column(bind: sa.engine.Connection, table_name: str, column: sa.Column) -> None:
    if column.name in _column_names(bind, table_name):
        return
    op.add_column(table_name, column)


def _ensure_index(
    bind: sa.engine.Connection,
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if index_name in _index_names(bind, table_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("hashed_password", sa.String(), nullable=True),
            sa.Column("google_id", sa.String(), nullable=True),
            sa.Column("google_email", sa.String(), nullable=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("profile_pic", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("is_verified", sa.Boolean(), nullable=True),
            sa.Column("verification_token", sa.String(), nullable=True),
            sa.Column("verification_token_expires", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    else:
        _ensure_column(bind, "users", sa.Column("google_email", sa.String(), nullable=True))
        _ensure_column(bind, "users", sa.Column("name", sa.String(), nullable=True))
        _ensure_column(bind, "users", sa.Column("profile_pic", sa.String(), nullable=True))
        _ensure_column(bind, "users", sa.Column("is_active", sa.Boolean(), nullable=True))
        _ensure_column(bind, "users", sa.Column("is_verified", sa.Boolean(), nullable=True))
        _ensure_column(bind, "users", sa.Column("verification_token", sa.String(), nullable=True))
        _ensure_column(
            bind,
            "users",
            sa.Column("verification_token_expires", sa.DateTime(timezone=True), nullable=True),
        )
        _ensure_column(bind, "users", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        _ensure_column(bind, "users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    _ensure_index(bind, "users", "ix_users_id", ["id"])
    _ensure_index(bind, "users", "ix_users_email", ["email"], unique=True)
    _ensure_index(bind, "users", "ix_users_google_id", ["google_id"], unique=True)

    if "workspaces" not in tables:
        op.create_table(
            "workspaces",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
    _ensure_index(bind, "workspaces", "ix_workspaces_id", ["id"])
    _ensure_index(bind, "workspaces", "ix_workspaces_name", ["name"])

    if "papers" not in tables:
        op.create_table(
            "papers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("authors", sa.String(), nullable=True),
            sa.Column("abstract", sa.Text(), nullable=True),
            sa.Column("url", sa.String(), nullable=True),
            sa.Column("doi", sa.String(), nullable=True),
            sa.Column("bibcode", sa.String(), nullable=True),
            sa.Column("source", sa.String(), nullable=True),
            sa.Column("pdf_url", sa.String(), nullable=True),
            sa.Column("institutional_url", sa.String(), nullable=True),
            sa.Column("access_type", sa.String(), nullable=True),
            sa.Column("full_text_available", sa.Boolean(), nullable=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
        )
    _ensure_index(bind, "papers", "ix_papers_id", ["id"])
    _ensure_index(bind, "papers", "ix_papers_title", ["title"])

    if "chats" not in tables:
        op.create_table(
            "chats",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("response", sa.Text(), nullable=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        )
    _ensure_index(bind, "chats", "ix_chats_id", ["id"])

    if "search_history" not in tables:
        op.create_table(
            "search_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("query", sa.String(), nullable=True),
            sa.Column("source", sa.String(), nullable=True),
            sa.Column("result_count", sa.Integer(), nullable=True),
            sa.Column("filters_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
    _ensure_index(bind, "search_history", "ix_search_history_id", ["id"])
    _ensure_index(bind, "search_history", "ix_search_history_user_id", ["user_id"])
    _ensure_index(bind, "search_history", "ix_search_history_query", ["query"])
    _ensure_index(bind, "search_history", "ix_search_history_created_at", ["created_at"])

    if "user_session_state" not in tables:
        op.create_table(
            "user_session_state",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("page_path", sa.String(), nullable=True),
            sa.Column("workspace_id", sa.Integer(), nullable=True),
            sa.Column("last_query", sa.String(), nullable=True),
            sa.Column("draft_text", sa.Text(), nullable=True),
            sa.Column("extra_json", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    _ensure_index(bind, "user_session_state", "ix_user_session_state_id", ["id"])
    _ensure_index(bind, "user_session_state", "ix_user_session_state_user_id", ["user_id"], unique=True)

    if "workspace_documents" not in tables:
        op.create_table(
            "workspace_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    _ensure_index(bind, "workspace_documents", "ix_workspace_documents_id", ["id"])
    _ensure_index(bind, "workspace_documents", "ix_workspace_documents_workspace_id", ["workspace_id"], unique=True)
    _ensure_index(bind, "workspace_documents", "ix_workspace_documents_user_id", ["user_id"])

    if "workspace_files" not in tables:
        op.create_table(
            "workspace_files",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=True),
            sa.Column("kind", sa.String(), nullable=True),
            sa.Column("filename", sa.String(), nullable=True),
            sa.Column("storage_bucket", sa.String(), nullable=True),
            sa.Column("storage_path", sa.String(), nullable=True),
            sa.Column("download_url", sa.String(), nullable=True),
            sa.Column("content_type", sa.String(), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
    _ensure_index(bind, "workspace_files", "ix_workspace_files_id", ["id"])
    _ensure_index(bind, "workspace_files", "ix_workspace_files_workspace_id", ["workspace_id"])
    _ensure_index(bind, "workspace_files", "ix_workspace_files_user_id", ["user_id"])
    _ensure_index(bind, "workspace_files", "ix_workspace_files_paper_id", ["paper_id"])
    _ensure_index(bind, "workspace_files", "ix_workspace_files_kind", ["kind"])
    _ensure_index(bind, "workspace_files", "ix_workspace_files_storage_path", ["storage_path"], unique=True)
    _ensure_index(bind, "workspace_files", "ix_workspace_files_created_at", ["created_at"])

    if "data_rights_requests" not in tables:
        op.create_table(
            "data_rights_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("request_type", sa.String(), nullable=True),
            sa.Column("jurisdiction", sa.String(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
    _ensure_index(bind, "data_rights_requests", "ix_data_rights_requests_id", ["id"])
    _ensure_index(bind, "data_rights_requests", "ix_data_rights_requests_user_id", ["user_id"])
    _ensure_index(bind, "data_rights_requests", "ix_data_rights_requests_email", ["email"])
    _ensure_index(bind, "data_rights_requests", "ix_data_rights_requests_request_type", ["request_type"])
    _ensure_index(bind, "data_rights_requests", "ix_data_rights_requests_status", ["status"])
    _ensure_index(bind, "data_rights_requests", "ix_data_rights_requests_submitted_at", ["submitted_at"])

    if "refresh_sessions" not in tables:
        op.create_table(
            "refresh_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("token_hash", sa.String(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("replaced_by_hash", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
    _ensure_index(bind, "refresh_sessions", "ix_refresh_sessions_id", ["id"])
    _ensure_index(bind, "refresh_sessions", "ix_refresh_sessions_user_id", ["user_id"])
    _ensure_index(bind, "refresh_sessions", "ix_refresh_sessions_token_hash", ["token_hash"], unique=True)
    _ensure_index(bind, "refresh_sessions", "ix_refresh_sessions_expires_at", ["expires_at"])
    _ensure_index(bind, "refresh_sessions", "ix_refresh_sessions_revoked_at", ["revoked_at"])
    _ensure_index(bind, "refresh_sessions", "ix_refresh_sessions_created_at", ["created_at"])


def _drop_table_if_exists(table_name: str) -> None:
    bind = op.get_bind()
    if table_name in _table_names(bind):
        op.drop_table(table_name)


def downgrade() -> None:
    _drop_table_if_exists("refresh_sessions")
    _drop_table_if_exists("data_rights_requests")
    _drop_table_if_exists("workspace_files")
    _drop_table_if_exists("workspace_documents")
    _drop_table_if_exists("user_session_state")
    _drop_table_if_exists("search_history")
    _drop_table_if_exists("chats")
    _drop_table_if_exists("papers")
    _drop_table_if_exists("workspaces")
    _drop_table_if_exists("users")
