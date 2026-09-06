from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawPosting(Base):
    __tablename__ = "raw_postings"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer)
    external_id: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
