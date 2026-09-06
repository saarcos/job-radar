import httpx

API_URL = "https://remotive.com/api/remote-jobs"
SOURCE_SLUG = "remotive"


def fetch_jobs(category: str = "software-dev") -> list[dict]:
    response = httpx.get(API_URL, params={"category": category}, timeout=10.0)
    response.raise_for_status()
    return response.json()["jobs"]
