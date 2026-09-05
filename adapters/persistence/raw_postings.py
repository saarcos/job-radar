import hashlib
import json

from psycopg.types.json import Jsonb


def compute_content_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def save_many(conn, source_id: int, jobs: list[dict]) -> None:
    with conn.cursor() as cur:
        for job in jobs:
            payload = Jsonb(job)
            content_hash = compute_content_hash(job)
            cur.execute(
                """
                    INSERT INTO raw_postings
                        (source_id, external_id, payload_json, fetched_at, content_hash)
                    VALUES
                        (%s, %s, %s, NOW(), %s)
                    """,
                (source_id, str(job["id"]), payload, content_hash),
            )


def fetch_all(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT payload_json->>'title', payload_json->>'company_name' FROM raw_postings"
        )
        rows = cur.fetchall()
        return rows
