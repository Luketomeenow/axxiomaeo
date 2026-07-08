from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CostEvent(Base):
    """One row per billable API call — the billing-grade cost ledger.

    provider: anthropic | ideogram | fal | openai | brightdata
    operation: content_generation | content_correction | content_refresh |
               image_plan | citation_insights | report_summary |
               image_generation | citation_scrape
    Anthropic events carry token counts; image/scrape events carry `units`.
    cost_usd is computed at write time from the configured rates.
    """

    __tablename__ = "cost_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(30))
    operation: Mapped[str] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 5), default=0)
    brand_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
