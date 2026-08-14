import uuid
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.schemas import AuditLogResponse
from app.routers.auth_deps import RoleChecker
from app.services import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Trail & Edit History"])


@router.get(
    "/recent",
    response_model=List[AuditLogResponse],
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def get_recent_audit_logs(
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Manager endpoint: Retrieve the most recent system-wide audit trail entries.
    """
    return await AuditService.get_recent_logs(db, limit=limit)


@router.get(
    "/user/{user_id}",
    response_model=List[AuditLogResponse],
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def get_user_activity_logs(
    user_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Manager endpoint: Retrieve audit history of actions performed by a specific user.
    """
    return await AuditService.get_user_activity(db, actor_id=user_id, limit=limit)


@router.get(
    "/{entity_type}/{entity_id}",
    response_model=List[AuditLogResponse],
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def get_entity_audit_history(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Manager endpoint: Retrieve chronological edit history and changes for a specific entity.
    """
    return await AuditService.get_entity_history(db, entity_type=entity_type, entity_id=entity_id)
