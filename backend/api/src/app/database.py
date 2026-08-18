"""PostgreSQL connection and schema setup."""

from __future__ import annotations

import hashlib
import logging
import time
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app.settings import get_settings


logger = logging.getLogger(__name__)

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


class DatabaseUnavailableError(RuntimeError):
    """Raised when PostgreSQL is not configured or cannot be reached."""


def password_hash(password: str) -> str:
    """Return a stable hash for the test user's password."""

    return hashlib.sha256(f"obra-barata:{password}".encode("utf-8")).hexdigest()


def _database_url() -> str:
    database_url = get_settings().DATABASE_URL
    if not database_url:
        raise DatabaseUnavailableError("DATABASE_URL nao configurada.")
    return database_url


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Open a PostgreSQL connection with dict rows."""

    try:
        with psycopg.connect(_database_url(), row_factory=dict_row) as connection:
            yield connection
    except psycopg.OperationalError as exc:
        raise DatabaseUnavailableError("Nao foi possivel conectar ao PostgreSQL.") from exc


def initialize_database(max_attempts: int = 20, delay_seconds: float = 1.0) -> None:
    """Create tables and seed the single test user."""

    if not get_settings().DATABASE_URL:
        logger.info("database_init_skipped reason=missing_DATABASE_URL")
        return

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with get_connection() as connection:
                _create_schema(connection)
                _seed_single_test_user(connection)
                connection.commit()
            logger.info("database_init_done")
            return
        except DatabaseUnavailableError as exc:
            last_error = exc
            logger.warning(
                "database_init_retry attempt=%s max_attempts=%s error=%s",
                attempt,
                max_attempts,
                exc,
            )
            time.sleep(delay_seconds)

    raise DatabaseUnavailableError("PostgreSQL indisponivel na inicializacao.") from last_error


def _create_schema(connection: Connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id UUID PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                project_type TEXT NOT NULL DEFAULT 'Residencial',
                address TEXT NOT NULL DEFAULT '',
                area_built TEXT NOT NULL DEFAULT '',
                finish_profile TEXT NOT NULL DEFAULT 'Medio custo',
                status TEXT NOT NULL DEFAULT 'rascunho',
                upload JSONB,
                material_list JSONB,
                priced_list JSONB,
                removed_material_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_projects_user_updated_at
            ON projects (user_id, updated_at DESC)
            """
        )


def _seed_single_test_user(connection: Connection) -> None:
    settings = get_settings()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO app_users (id, username, password_hash)
            VALUES (%s, %s, %s)
            ON CONFLICT (username)
            DO UPDATE SET password_hash = EXCLUDED.password_hash
            """,
            (TEST_USER_ID, settings.TEST_USERNAME, password_hash(settings.TEST_PASSWORD)),
        )
        cursor.execute(
            "DELETE FROM app_users WHERE username <> %s",
            (settings.TEST_USERNAME,),
        )
