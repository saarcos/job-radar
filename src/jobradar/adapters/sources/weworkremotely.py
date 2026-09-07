import feedparser

from jobradar.domain.ports.job_source import RawJob

FEED_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"


class WeWorkRemotelySource:
    slug = "weworkremotely"

    def fetch(self) -> list[RawJob]:
        feed = feedparser.parse(FEED_URL)
        return [RawJob(external_id=entry.id, payload=dict(entry)) for entry in feed.entries]
