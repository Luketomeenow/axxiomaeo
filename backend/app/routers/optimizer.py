from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/optimizer", tags=["optimizer"])


class DecisionRequest(BaseModel):
    note: str | None = None
    # Code changes only: the task for the Claude Code agent, as edited on
    # System Health before approving. Empty keeps the agent's own wording.
    instructions: str | None = None


@router.get("/status")
async def optimizer_status(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Whether the agent can execute changes (GitHub token, workflow on the
    default branch) and proposal counts by status."""
    from app.services.optimizer_service import OptimizerService

    return await OptimizerService(db).status()


@router.get("/proposals")
async def list_proposals(
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Proposals, newest first. In-flight ones are refreshed from GitHub
    (throttled), so the list shows the current run and pull request."""
    from app.services.optimizer_service import OptimizerService

    return {"proposals": await OptimizerService(db).list(limit=limit)}


@router.post("/run")
async def run_analysis(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Analyze the platform now and add new proposals (about a minute)."""
    from app.services.optimizer_service import OptimizerService

    return await OptimizerService(db).generate(trigger="manual")


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: int,
    body: DecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Approve a proposal. A code change starts the Claude Code workflow,
    which opens a pull request; a manual change is marked accepted."""
    from app.services.optimizer_service import OptimizerService

    return await OptimizerService(db).approve(
        proposal_id, user, instructions=body.instructions, note=body.note
    )


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int,
    body: DecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    from app.services.optimizer_service import OptimizerService

    return await OptimizerService(db).reject(proposal_id, user, note=body.note)


@router.post("/proposals/{proposal_id}/done")
async def mark_proposal_done(
    proposal_id: int,
    body: DecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Close an accepted manual change once a person has made it."""
    from app.services.optimizer_service import OptimizerService

    return await OptimizerService(db).mark_done(proposal_id, user, note=body.note)


@router.post("/proposals/{proposal_id}/sync")
async def sync_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Refresh one proposal's run and pull request from GitHub now."""
    from app.services.optimizer_service import OptimizerService, serialize

    service = OptimizerService(db)
    row = await service._get(proposal_id)
    await service.sync(row, force=True)
    return serialize(row)
