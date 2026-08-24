import hashlib
import json

import httpx
import psycopg
from psycopg.types.json import Jsonb


def main():
    connection_string = "postgresql://jobradar:local@localhost:5433/jobradar"

    response = httpx.get(
        "https://remotive.com/api/remote-jobs?category=software-dev",
        timeout=10.0,
    )
    response.raise_for_status()

    jobs = response.json()["jobs"]

    conn = psycopg.connect(connection_string)

    try:
        with conn.cursor() as cur:
            for job in jobs:
                payload = Jsonb(job)
                content_hash = hashlib.sha256(
                    json.dumps(job, sort_keys=True).encode()
                ).hexdigest()
                
                cur.execute(
                    """
                    INSERT INTO raw_postings
                        (source_id, external_id, payload_json, fetched_at, content_hash)
                    VALUES
                        (%s, %s, %s, NOW(), %s)
                    """,
                    (
                        1,
                        str(job["id"]),
                        payload,
                        content_hash,
                    ),
                )
        conn.commit()
        
        with conn.cursor() as cur:
                    cur.execute("SELECT payload_json->>'title', payload_json->'company_name' FROM raw_postings")
                    rows = cur.fetchall()
                    
                    for title, company in rows:
                        title_norm = title.strip().lower()
                        company_norm = company.strip().lower()
                        print(f"Title: {title_norm}")
                        print(f"Company: {company_norm}")

    finally:
        conn.close()

if __name__ == "__main__":
    main()