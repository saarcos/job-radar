import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from jobradar.adapters.persistence.models import RawPosting


def compute_content_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def save_many(session, source_id: int, jobs: list[dict]) -> None:
    rows = [
        {
            "source_id": source_id,
            "external_id": str(job["id"]),
            "payload_json": job,
            "content_hash": compute_content_hash(job),
        }
        for job in jobs
    ]

    stmt = insert(RawPosting).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["source_id", "external_id"],
        set_={
            "payload_json": stmt.excluded.payload_json,
            "content_hash": stmt.excluded.content_hash,
            "fetched_at": func.now(),
        },
        where=RawPosting.content_hash.is_distinct_from(stmt.excluded.content_hash),
    )
    session.execute(stmt)


def fetch_all(session):
    postings = session.scalars(select(RawPosting)).all()
    return [(p.payload_json["title"], p.payload_json["company_name"]) for p in postings]
