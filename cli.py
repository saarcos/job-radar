# cli.py
import psycopg

from adapters.persistence import raw_postings
from adapters.sources import remotive
from domain import normalize

CONNECTION_STRING = "postgresql://jobradar:local@localhost:5433/jobradar"


def main():
    jobs = remotive.fetch_jobs()
    with psycopg.connect(CONNECTION_STRING) as conn:
        raw_postings.save_many(conn, source_id=1, jobs=jobs)
        for title, company in raw_postings.fetch_all(conn):
            print(f"{normalize.company(company)} | {normalize.title(title)}")


if __name__ == "__main__":
    main()
