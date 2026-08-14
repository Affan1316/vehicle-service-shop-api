from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.models import Customer, Vehicle, Part


class SearchService:
    @staticmethod
    async def search_customers(db: AsyncSession, query: str) -> list[Customer]:
        """Search customers by name, phone, email, or secondary phone (case-insensitive ILIKE)."""
        pattern = f"%{query}%"
        stmt = select(Customer).where(
            or_(
                Customer.name.ilike(pattern),
                Customer.phone.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.secondary_phone.ilike(pattern),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def search_vehicles(db: AsyncSession, query: str) -> list[Vehicle]:
        """Search vehicles by VIN, license plate, or customer name."""
        pattern = f"%{query}%"
        stmt = (
            select(Vehicle)
            .outerjoin(Customer, Vehicle.customer_id == Customer.customer_id)
            .where(
                or_(
                    Vehicle.vin.ilike(pattern),
                    Vehicle.license_plate.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def search_parts(db: AsyncSession, query: str) -> list[Part]:
        """Search parts by name, part number, or category."""
        pattern = f"%{query}%"
        stmt = select(Part).where(
            or_(
                Part.name.ilike(pattern),
                Part.part_number.ilike(pattern),
                Part.category.ilike(pattern),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
