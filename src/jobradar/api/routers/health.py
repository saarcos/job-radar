from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from jobradar.api.dependencies import database_is_up

router = APIRouter()


@router.get("/health")
def health(
    response: Response, database_up: Annotated[bool, Depends(database_is_up)]
) -> dict[str, str]:
    if not database_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}
