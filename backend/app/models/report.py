from datetime import datetime, date
from sqlalchemy import Integer, DateTime, Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_month: Mapped[date | None] = mapped_column(Date, nullable=True)
    overall_citation_share: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    ai_referred_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_pieces_published: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_coverage_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    top_performing_queries: Mapped[list] = mapped_column(JSONB, default=list)
    gap_queries: Mapped[list] = mapped_column(JSONB, default=list)
    brand_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    full_report_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
