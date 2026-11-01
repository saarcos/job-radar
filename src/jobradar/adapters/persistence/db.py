import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from jobradar.config import get_settings

logger = logging.getLogger(__name__)

# How long a connection attempt waits for an unreachable database. Also used by
# migrations/env.py: on Windows, psycopg does not notice a refused connection
# and would otherwise hang instead of failing.
CONNECT_TIMEOUT_SECONDS = 3


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        str(get_settings().database_url),
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine())


# Yields one Session and closes it afterwards; api/dependencies.py uses it per request.
# Nothing is committed here; uncommitted work is rolled back on close.
def get_session() -> Iterator[Session]:
    session_factory = get_sessionmaker()
    with session_factory() as session:
        yield session


def ping(session: Session) -> bool:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Only database errors mean "unavailable"; any other exception is a bug
        # and must propagate instead of being reported as a down database.
        logger.exception("Database ping failed")
        return False
    return True
