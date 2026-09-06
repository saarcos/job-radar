import httpx

from jobradar.domain.ports.job_source import RawJob

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveSource:
    slug = "remotive"

    def __init__(self, category: str = "software-dev") -> None:
        self.category = category

    def fetch(self) -> list[RawJob]:
        response = httpx.get(API_URL, params={"category": self.category}, timeout=10.0)
        response.raise_for_status()

        return [RawJob(external_id=str(job["id"]), payload=job) for job in response.json()["jobs"]]
