from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class SchemaJob(Base):
    __tablename__ = "schema_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[str] = mapped_column(String(50), ForeignKey("brands.id"))
    wp_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wp_post_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schema_types: Mapped[list] = mapped_column(JSONB, default=list)
    validation_status: Mapped[str] = mapped_column(String(50), default="pending")
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SchemaDeployment(Base):
    __tablename__ = "schema_deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_id: Mapped[str] = mapped_column(String(50), ForeignKey("brands.id"))
    wp_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wp_post_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schema_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    schema_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending_review")
    reviewer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
