# The only module in api/ that imports from adapters/. Routers depend on the
# functions below and never on the implementations behind them.
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from jobradar.adapters.persistence.db import get_session, ping


def database_is_up(session: Annotated[Session, Depends(get_session)]) -> bool:
    return ping(session)
