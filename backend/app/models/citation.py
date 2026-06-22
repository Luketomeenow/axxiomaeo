from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CitationRecord(Base):
    __tablename__ = "citation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[str] = mapped_column(String(50), ForeignKey("brands.id"))
    query: Mapped[str] = mapped_column(Text)
    query_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_cited: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_mentioned: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_url_cited: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    visibility_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_runs: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)
    parent_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    funnel_stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    competitor_cited: Mapped[str | None] = mapped_column(String(200), nullable=True)
    citation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audit_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
