from sqlalchemy import select

from jobradar.adapters.persistence.models import Source


def get_or_create_source_id(session, slug: str) -> int:
    source = session.scalar(select(Source).where(Source.slug == slug))
    if source is None:
        source = Source(slug=slug)
        session.add(source)
        session.flush()
    return source.id
