from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean
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
    competitor_cited: Mapped[str | None] = mapped_column(String(200), nullable=True)
    citation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
