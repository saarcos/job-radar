# cli.py

from jobradar.adapters.persistence import raw_postings
from jobradar.adapters.persistence.db import SessionLocal
from jobradar.adapters.sources.remotive import RemotiveSource
from jobradar.domain import normalize
from jobradar.domain.ports.job_source import JobSource

SOURCES: list[JobSource] = [RemotiveSource()]


def main():
    with SessionLocal() as session:
        for source in SOURCES:
            jobs = source.fetch()
            raw_postings.save_many(session=session, source_id=1, jobs=jobs)
        session.commit()
        for title, company in raw_postings.fetch_all(session):
            print(f"{normalize.company(company)} | {normalize.title(title)}")


if __name__ == "__main__":
    main()
