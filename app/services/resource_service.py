import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Technician, Bay, Certification
from app.schemas.schemas import TechnicianCreate, BayCreate, BayUpdate, CertificationCreate


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
    async def add_technician_certification(db: AsyncSession, tech_id: uuid.UUID, payload: CertificationCreate) -> Certification:
        # Check if tech exists
        ex_res = await db.execute(select(Technician).where(Technician.tech_id == tech_id))
        if not ex_res.scalar_one_or_none():
            raise ValueError(f"Technician with ID {tech_id} not found.")

        cert = Certification(
            tech_id=tech_id,
            cert_type=payload.cert_type,
            expiry_date=payload.expiry_date
        )
        db.add(cert)
        await db.flush()
        return cert

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

    @staticmethod
    async def update_bay(db: AsyncSession, bay_id: uuid.UUID, payload: BayUpdate) -> Bay:
        res = await db.execute(select(Bay).where(Bay.bay_id == bay_id))
        bay = res.scalar_one_or_none()
        if not bay:
            raise ValueError(f"Bay with ID {bay_id} not found.")

        if payload.status is not None:
            bay.status = payload.status
        if payload.bay_type is not None:
            bay.bay_type = payload.bay_type
        if "current_work_order_id" in payload.model_fields_set:
            bay.current_work_order_id = payload.current_work_order_id
        if "held_until" in payload.model_fields_set:
            bay.held_until = payload.held_until

        await db.flush()
        return bay
