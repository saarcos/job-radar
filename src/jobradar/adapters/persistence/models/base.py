from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names, so migrations can reference (and later drop)
# constraints by name instead of relying on names Postgres makes up.
# "ck" needs an explicit name on each CheckConstraint, e.g. name="status".
# "uq" and "ix" list every column: uq_job_posting_sources_source_id_external_id.
# Only real columns count: an index on text("started_at DESC") silently drops
# started_at from its name, so build it from the column, started_at.desc().
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Column type for each Python annotation, so models only declare the
    # annotation. Without the str entry, Mapped[str] would be varchar; the
    # schema uses text. ARRAY and JSONB come from the PostgreSQL dialect: the
    # schema targets Postgres only, and its ARRAY has the @> and && operators.
    # bigint is not here: int maps to integer, so bigint columns declare it.
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        str: Text(),
        list[str]: ARRAY(Text()),
        dict[str, Any]: JSONB(),
    }
