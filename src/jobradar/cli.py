# cli.py

from adapters.persistence import raw_postings
from adapters.persistence.db import SessionLocal
from adapters.sources import remotive
from domain import normalize


def main():
    jobs = remotive.fetch_jobs()
    with SessionLocal() as session:
        raw_postings.save_many(session, source_id=1, jobs=jobs)
        session.commit()
        for title, company in raw_postings.fetch_all(session):
            print(f"{normalize.company(company)} | {normalize.title(title)}")


if __name__ == "__main__":
    main()
