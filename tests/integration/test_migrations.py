"""Migrations, run against throwaway databases.

Alembic runs in a subprocess, like in the container and in the acceptance
criteria, pointed at TEST_DATABASE_URL. Every test drops and recreates that
database first, so each one starts from an empty database.
"""

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, Connection, Engine, create_engine, make_url, text
from sqlalchemy.pool import NullPool

from jobradar.adapters.persistence.db import CONNECT_TIMEOUT_SECONDS
from jobradar.adapters.persistence.models import Base

# Where alembic.ini and .env are, whatever directory pytest runs from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

POSTINGS_TABLES = {
    "sources",
    "sync_runs",
    "job_postings",
    "job_posting_sources",
    "search_profiles",
    "applications",
}


class IntegrationSettings(BaseSettings):
    # Read like the app's settings: real environment variables, then .env.
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    test_database_url: PostgresDsn


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    url = make_url(str(IntegrationSettings().test_database_url))
    # The fixtures below DROP this database, so refuse anything that is not
    # plainly a throwaway one, such as the app's own URL pasted by mistake.
    # The pattern also makes the name safe to put in DROP/CREATE DATABASE,
    # which take no bind parameters.
    if not re.fullmatch(r"[a-z0-9_]+_test", url.database or ""):
        pytest.fail(
            "TEST_DATABASE_URL must name a database ending in _test "
            f"(lowercase letters, digits and _), got {url.database!r}",
            pytrace=False,
        )
    return url


def engine_for(url: URL, **kwargs: Any) -> Engine:
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        **kwargs,
    )


def recreate_database(url: URL) -> None:
    """Drop the database that url names, if it exists, and create it empty."""
    # CREATE and DROP DATABASE cannot run inside a transaction, and need a
    # connection to another database: postgres always exists.
    server = engine_for(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with server.connect() as conn:
            # FORCE closes connections left open by an interrupted run.
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        server.dispose()


@contextmanager
def connect(url: URL) -> Iterator[Connection]:
    engine = engine_for(url)
    try:
        with engine.connect() as conn:
            yield conn
    finally:
        engine.dispose()


def alembic(url: URL, *args: str) -> str:
    """Run the alembic CLI against url and return its log."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        # A real environment variable wins over .env in jobradar.config.
        # render_as_string: str(url) would replace the password with ***.
        env={**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # alembic.ini sends Alembic's log to stderr.
    return result.stderr


def tables(url: URL) -> set[str]:
    with connect(url) as conn:
        query = text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return set(conn.scalars(query))


# Constraints and indexes as Postgres itself prints them from its catalog, so
# two databases built from different DDL text print them the same way.
DEFINITIONS = text(
    """
    SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid)
      FROM pg_constraint
     WHERE connamespace = 'public'::regnamespace
       AND conrelid::regclass::text <> 'alembic_version'
    UNION ALL
    SELECT tablename, indexname, indexdef
      FROM pg_indexes
     WHERE schemaname = 'public'
       AND tablename <> 'alembic_version'
    """
)


def definitions(url: URL) -> set[tuple[str, str, str]]:
    with connect(url) as conn:
        return {(table, name, sql) for table, name, sql in conn.execute(DEFINITIONS)}


@pytest.fixture
def empty_database(test_database_url: URL) -> URL:
    recreate_database(test_database_url)
    return test_database_url


@pytest.fixture
def models_database(test_database_url: URL) -> URL:
    """A second database, built from the models with create_all, no Alembic."""
    name = test_database_url.database or ""
    url = test_database_url.set(database=name.removesuffix("_test") + "_models_test")
    recreate_database(url)
    engine = engine_for(url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    return url


def test_upgrade_downgrade_upgrade_from_an_empty_database(empty_database: URL):
    alembic(empty_database, "upgrade", "head")
    assert tables(empty_database) == POSTINGS_TABLES | {"alembic_version"}

    alembic(empty_database, "downgrade", "base")
    assert tables(empty_database) == {"alembic_version"}

    alembic(empty_database, "upgrade", "head")
    assert tables(empty_database) == POSTINGS_TABLES | {"alembic_version"}


def test_upgrade_at_head_does_nothing(empty_database: URL):
    first = alembic(empty_database, "upgrade", "head")
    second = alembic(empty_database, "upgrade", "head")

    # The first assertion keeps the second one from passing just because the
    # log stopped showing upgrades.
    assert "Running upgrade" in first
    assert "Running upgrade" not in second
    with connect(empty_database) as conn:
        assert conn.scalar(text("SELECT count(*) FROM sources")) == 3
        assert conn.scalar(text("SELECT count(*) FROM search_profiles")) == 1


def test_seed_has_the_three_sources_and_the_default_profile(empty_database: URL):
    alembic(empty_database, "upgrade", "head")

    with connect(empty_database) as conn:
        sources = conn.execute(
            text("SELECT slug, name, enabled, priority FROM sources ORDER BY priority")
        ).all()
        default_profiles = conn.execute(
            text(
                "SELECT name, include_keywords, exclude_keywords, exclude_seniority,"
                " languages, max_age_days, source_slugs"
                " FROM search_profiles WHERE is_default"
            )
        ).all()

    assert sources == [
        ("getonboard", "Get on Board", True, 0),
        ("weworkremotely", "We Work Remotely", True, 1),
        ("remotive", "Remotive", True, 2),
    ]
    # The default profile of IMPLEMENTATION.md §6.
    assert default_profiles == [
        (
            "Backend / Fullstack",
            [
                "python",
                "fastapi",
                "django",
                "flask",
                "backend",
                "node",
                "typescript",
                "react",
                "fullstack",
                "full-stack",
            ],
            [
                "sales",
                "marketing",
                "designer",
                "recruiter",
                "copywriter",
                "customer support",
                "data entry",
            ],
            [
                "staff",
                "principal",
                "director",
                "head of",
                "vp",
                "manager",
                "architect",
                "lead",
            ],
            None,
            30,
            None,
        )
    ]


def test_migrations_and_models_define_the_same_constraints_and_indexes(
    empty_database: URL, models_database: URL
):
    # alembic check does not compare a check constraint's condition nor a
    # partial index's WHERE; comparing Postgres's own definitions does.
    alembic(empty_database, "upgrade", "head")

    migrated = definitions(empty_database)

    assert migrated, "no constraints or indexes found: wrong database?"
    assert migrated == definitions(models_database)
