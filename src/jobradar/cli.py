# cli.py

from jobradar.adapters.persistence import raw_postings
from jobradar.adapters.persistence.db import SessionLocal
from jobradar.adapters.persistence.sources import get_or_create_source_id
from jobradar.adapters.sources.remotive import RemotiveSource
from jobradar.adapters.sources.weworkremotely import WeWorkRemotelySource
from jobradar.domain.ports.job_source import JobSource

SOURCES: list[JobSource] = [RemotiveSource(), WeWorkRemotelySource()]


def main():
    with SessionLocal() as session:
        for source in SOURCES:
            source_id = get_or_create_source_id(session=session, slug=source.slug)
            jobs = source.fetch()
            raw_postings.save_many(session=session, source_id=source_id, jobs=jobs)
        session.commit()


if __name__ == "__main__":
    main()
