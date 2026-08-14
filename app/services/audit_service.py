import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import AuditLog


class AuditService:
    @staticmethod
    async def log_create(
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        actor_id: Optional[uuid.UUID] = None,
        actor_username: Optional[str] = None,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Records the creation of a new domain entity.
        """
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="create",
            actor_id=actor_id,
            actor_username=actor_username,
            changes={"initial": initial_data} if initial_data else None
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def log_update(
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        actor_id: Optional[uuid.UUID] = None,
        actor_username: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Records field-level updates to an existing entity (e.g. {"status": {"old": "draft", "new": "approved"}}).
        """
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="update",
            actor_id=actor_id,
            actor_username=actor_username,
            changes=changes
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def log_delete(
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        actor_id: Optional[uuid.UUID] = None,
        actor_username: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        """
        Records the deletion of an entity.
        """
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="delete",
            actor_id=actor_id,
            actor_username=actor_username,
            changes={"details": details} if details else None
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def get_entity_history(
        db: AsyncSession,
        entity_type: str,
        entity_id: str
    ) -> List[AuditLog]:
        """
        Retrieves the chronological audit history for a specific entity.
        """
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == str(entity_id)
            )
            .order_by(AuditLog.timestamp.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_user_activity(
        db: AsyncSession,
        actor_id: uuid.UUID,
        limit: int = 50
    ) -> List[AuditLog]:
        """
        Retrieves recent actions performed by a specific user.
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_recent_logs(
        db: AsyncSession,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Retrieves the most recent system-wide audit entries.
        """
        stmt = (
            select(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())
