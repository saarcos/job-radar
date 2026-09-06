from jobradar.domain.ports.job_source import RawJob


class FakeSource:
    slug = "fake"

    def __init__(self, jobs: list[RawJob]) -> None:
        self._jobs = jobs

    def fetch(self) -> list[RawJob]:
        return self._jobs
