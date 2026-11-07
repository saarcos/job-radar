"""ORM models, one module per table.

Alembic finds tables through Base.metadata, and a model class is only
registered there once its module has been imported. Every model is imported
here, so importing the package registers all of them.
"""

from jobradar.adapters.persistence.models.base import Base
from jobradar.adapters.persistence.models.search_profile import SearchProfileRow
from jobradar.adapters.persistence.models.source import SourceRow
from jobradar.adapters.persistence.models.sync_run import SyncRunRow

__all__ = ["Base", "SearchProfileRow", "SourceRow", "SyncRunRow"]
