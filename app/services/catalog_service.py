import uuid
import decimal
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Vendor, Part, PurchaseOrder, PoLineItem
from app.services.inventory_service import InventoryService
from app.services.job_service import JobService
from app.schemas.schemas import LineItemCreate

class CatalogService:
    @staticmethod
    async def search_catalog(query: str) -> List[Dict[str, Any]]:
        """Mock catalog search returning simulated Nexpart/Epicor results."""
        return [
            {
                "catalog_part_id": f"CAT-{uuid.uuid4().hex[:8]}",
                "name": f"{query.title()} - Premium",
                "part_number": f"PRM-{uuid.uuid4().hex[:6].upper()}",
                "description": f"Premium aftermarket {query.lower()} with lifetime warranty.",
                "brand": "ACDelco",
                "cost": 45.00,
                "retail_price": 89.99,
                "availability": "In Stock (Local Store)",
            },
            {
                "catalog_part_id": f"CAT-{uuid.uuid4().hex[:8]}",
                "name": f"{query.title()} - Economy",
                "part_number": f"ECO-{uuid.uuid4().hex[:6].upper()}",
                "description": f"Standard replacement {query.lower()}.",
                "brand": "Duralast",
                "cost": 22.50,
                "retail_price": 49.99,
                "availability": "Out of Stock (2 days)",
            }
        ]

    @staticmethod
    async def import_part(db: AsyncSession, work_order_id: uuid.UUID, part_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mocks the one-click import flow:
        1. Ensure Vendor exists (Mock Vendor)
        2. Create Part
        3. Create PurchaseOrder & PoLineItem
        4. Add LineItem to WorkOrder
        """
        # 1. Get or create mock vendor
        vendor_result = await db.execute(select(Vendor).where(Vendor.name == "Mock Catalog Vendor"))
        vendor = vendor_result.scalars().first()
        if not vendor:
            vendor = Vendor(
                name="Mock Catalog Vendor",
                contact_name="API Integration",
                phone="555-0199",
                email="api@mockcatalog.com",
            )
            db.add(vendor)
            await db.flush()

        # 2. Create the Part
        part = Part(
            part_number=part_data.get("part_number", f"MOCK-{uuid.uuid4().hex[:6]}"),
            name=part_data.get("name", "Imported Part"),
            description=part_data.get("description", ""),
            cost=decimal.Decimal(str(part_data.get("cost", 0.0))),
            retail_price=decimal.Decimal(str(part_data.get("retail_price", 0.0))),
            stock_qty=0,
            reorder_threshold=0
        )
        db.add(part)
        await db.flush()

        # 3. Create PO
        po = PurchaseOrder(
            vendor_id=vendor.vendor_id,
            status="submitted"
        )
        db.add(po)
        await db.flush()

        po_item = PoLineItem(
            po_id=po.po_id,
            part_id=part.part_id,
            qty_ordered=1,
            qty_shipped=0,
            qty_received=0
        )
        db.add(po_item)
        await db.flush()

        # 4. Add to WorkOrder
        li_create = LineItemCreate(
            type="part",
            description=f"{part.name} ({part.part_number})",
            price=part.retail_price,
            part_id=part.part_id
        )
        line_item = await JobService.create_line_item(db, work_order_id, li_create)

        await db.commit()
        await db.refresh(line_item)

        return {
            "purchase_order_id": str(po.po_id),
            "part_id": str(part.part_id),
            "line_item_id": str(line_item.line_item_id)
        }
