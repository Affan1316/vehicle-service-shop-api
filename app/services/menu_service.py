import uuid
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import CannedService, WorkOrder, LineItem
from app.schemas.schemas import CannedServiceCreate, CannedServiceUpdate
from app.exceptions import NotFoundError


class MenuService:
    @staticmethod
    async def create_canned_service(db: AsyncSession, payload: CannedServiceCreate) -> CannedService:
        """
        Creates a new reusable canned service template.
        """
        svc = CannedService(
            name=payload.name,
            description=payload.description,
            category=payload.category,
            billing_mode=payload.billing_mode,
            default_price=payload.default_price,
            estimated_hours=payload.estimated_hours,
            is_active=payload.is_active
        )
        db.add(svc)
        await db.flush()
        return svc

    @staticmethod
    async def list_canned_services(db: AsyncSession, active_only: bool = True) -> List[CannedService]:
        """
        Lists all canned services, optionally filtered by active status.
        """
        query = select(CannedService).order_by(CannedService.category.asc(), CannedService.name.asc())
        if active_only:
            query = query.where(CannedService.is_active.is_(True))
        res = await db.execute(query)
        return list(res.scalars().all())

    @staticmethod
    async def get_canned_service(db: AsyncSession, service_id: uuid.UUID) -> CannedService:
        """
        Retrieves a single canned service by ID.
        """
        res = await db.execute(select(CannedService).where(CannedService.service_id == service_id))
        svc = res.scalar_one_or_none()
        if not svc:
            raise NotFoundError(f"Canned service with ID {service_id} not found.")
        return svc

    @staticmethod
    async def update_canned_service(
        db: AsyncSession,
        service_id: uuid.UUID,
        payload: CannedServiceUpdate
    ) -> CannedService:
        """
        Updates an existing canned service template.
        """
        svc = await MenuService.get_canned_service(db, service_id)

        if payload.name is not None:
            svc.name = payload.name
        if payload.description is not None:
            svc.description = payload.description
        if payload.category is not None:
            svc.category = payload.category
        if payload.billing_mode is not None:
            svc.billing_mode = payload.billing_mode
        if payload.default_price is not None:
            svc.default_price = payload.default_price
        if payload.estimated_hours is not None:
            svc.estimated_hours = payload.estimated_hours
        if payload.is_active is not None:
            svc.is_active = payload.is_active

        await db.flush()
        return svc

    @staticmethod
    async def apply_to_work_order(
        db: AsyncSession,
        work_order_id: uuid.UUID,
        service_id: uuid.UUID
    ) -> LineItem:
        """
        Instantiates a new LineItem on a WorkOrder pre-filled from a CannedService template.
        """
        svc = await MenuService.get_canned_service(db, service_id)

        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == work_order_id))
        wo = wo_res.scalar_one_or_none()
        if not wo:
            raise NotFoundError(f"WorkOrder with ID {work_order_id} not found.")

        if wo.status in ["closed", "archived"]:
            raise ValueError(f"Cannot add line items to a {wo.status} work order.")

        desc = svc.name
        if svc.description:
            desc = f"{svc.name}: {svc.description}"

        line_item = LineItem(
            work_order_id=work_order_id,
            description=desc,
            billing_mode=svc.billing_mode,
            price=svc.default_price,
            status="not_started"
        )
        db.add(line_item)
        await db.flush()
        return line_item
