from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Text, DateTime, ForeignKey, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    wp_url: Mapped[str] = mapped_column(String(500))
    wp_username: Mapped[str] = mapped_column(String(100), default="admin")
    markets: Mapped[list] = mapped_column(JSONB, default=list)
    is_corporate: Mapped[bool] = mapped_column(Boolean, default=False)
    ga4_property_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gsc_site_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_queries: Mapped[list] = mapped_column(JSONB, default=list)
    service_page_urls: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    content_pieces: Mapped[list["ContentPiece"]] = relationship(back_populates="brand")
    drafts: Mapped[list["ContentDraft"]] = relationship(back_populates="brand")
