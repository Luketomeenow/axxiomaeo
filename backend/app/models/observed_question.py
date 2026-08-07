from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ObservedQuestion(Base):
    """A real customer question observed outside the platform — pushed by the
    Foundry ghl-agent from GoHighLevel calls/chats/forms. The highest-trust
    demand signal we have: literal human phrasing, not assumed queries.
    Feeds the citation audit (query_source="ghl") and topic discovery
    (source="observed_demand")."""

    __tablename__ = "observed_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[str] = mapped_column(String(50), ForeignKey("brands.id"))
    question: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # call | chat | form
    asked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Idempotency key from the pushing agent (e.g. GHL conversation id) so
    # re-pushes of the same conversation don't duplicate.
    external_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
