from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OptimizationProposal(Base):
    """One change the optimization agent proposes, and what became of it.

    Lifecycle: proposed → approved by a person on System Health → for a code
    change, queued → running (the Claude Code workflow in GitHub Actions) →
    pr_open → merged | closed, or failed; for a manual change (a WordPress,
    CallRail or GA4 setting outside this repo), accepted → done. Rejected
    proposals stay so the agent does not propose them again.
    """

    __tablename__ = "optimization_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual | scheduled
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(30), default="pipeline")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    brand_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), default="code")  # code | manual
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_change: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The task handed to the Claude Code agent (code changes). Editable on
    # System Health until the proposal is approved.
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{label, value, source, verified}] — verified = the value was found in
    # the data snapshot the agent was given (the model explains, SQL computes).
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    files_hint: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    branch: Mapped[str | None] = mapped_column(String(200), nullable=True)
    run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    run_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
