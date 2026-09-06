from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawJob:
    external_id: str
    payload: dict


class JobSource(Protocol):
    slug: str

    def fetch(self) -> list[RawJob]: ...
