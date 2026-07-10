from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Technician, Bay
from app.schemas.schemas import TechnicianCreate, BayCreate


class ResourceService:
    @staticmethod
    async def create_technician(db: AsyncSession, payload: TechnicianCreate) -> Technician:
        if payload.tech_id is not None:
            ex_res = await db.execute(select(Technician).where(Technician.tech_id == payload.tech_id))
            if ex_res.scalar_one_or_none():
                raise ValueError(f"Technician with ID {payload.tech_id} already exists.")

        kwargs = {
            "name": payload.name,
            "hourly_rate": payload.hourly_rate
        }
        if payload.tech_id is not None:
            kwargs["tech_id"] = payload.tech_id
            
        tech = Technician(**kwargs)
        db.add(tech)
        await db.flush()
        return tech

    @staticmethod
    async def create_bay(db: AsyncSession, payload: BayCreate) -> Bay:
        bay = Bay(
            bay_type=payload.bay_type,
            status=payload.status,
            current_work_order_id=payload.current_work_order_id,
            held_until=payload.held_until
        )
        db.add(bay)
        await db.flush()
        return bay
