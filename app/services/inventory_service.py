import uuid
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Part, Vendor, PurchaseOrder, PoLineItem, PartInstance
from app.schemas.schemas import (
    PartCreate, PartUpdate,
    VendorCreate, VendorUpdate,
    PurchaseOrderCreate, PurchaseOrderUpdate,
    PartInstanceUpdate
)

class InventoryService:
    @staticmethod
    async def create_part(db: AsyncSession, payload: PartCreate) -> Part:
        part = Part(
            part_number=payload.part_number,
            category=payload.category,
            quantity_on_hand=payload.quantity_on_hand,
            is_returnable=payload.is_returnable
        )
        db.add(part)
        await db.flush()
        return part

    @staticmethod
    async def get_part(db: AsyncSession, part_id: uuid.UUID) -> Part:
        res = await db.execute(select(Part).where(Part.part_id == part_id))
        part = res.scalar_one_or_none()
        if not part:
            raise ValueError(f"Part with ID {part_id} not found.")
        return part

    @staticmethod
    async def create_vendor(db: AsyncSession, payload: VendorCreate) -> Vendor:
        vendor = Vendor(
            name=payload.name,
            vendor_type=payload.vendor_type
        )
        db.add(vendor)
        await db.flush()
        return vendor

    @staticmethod
    async def create_purchase_order(db: AsyncSession, payload: PurchaseOrderCreate, line_items_payload: list) -> PurchaseOrder:
        po = PurchaseOrder(
            vendor_id=payload.vendor_id,
            status=payload.status,
            submitted_at=payload.submitted_at or datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(po)
        await db.flush()

        for item_data in line_items_payload:
            po_item = PoLineItem(
                po_id=po.po_id,
                part_id=item_data["part_id"],
                qty_ordered=item_data["qty_ordered"],
                qty_shipped=item_data.get("qty_shipped", 0),
                qty_received=item_data.get("qty_received", 0)
            )
            db.add(po_item)
            await db.flush()

            # Create physical PartInstance entries in 'ordered' status
            for _ in range(item_data["qty_ordered"]):
                pi = PartInstance(
                    part_id=item_data["part_id"],
                    status="ordered",
                    po_line_item_id=po_item.po_line_item_id
                )
                db.add(pi)

        await db.flush()
        return po

    @staticmethod
    async def update_part_instance(db: AsyncSession, instance_id: uuid.UUID, payload: PartInstanceUpdate) -> PartInstance:
        res = await db.execute(select(PartInstance).where(PartInstance.part_instance_id == instance_id))
        instance = res.scalar_one_or_none()
        if not instance:
            raise ValueError(f"PartInstance with ID {instance_id} not found.")

        if payload.status is not None:
            # Handle inventory stock updates when status changes
            old_status = instance.status
            new_status = payload.status
            instance.status = new_status

            # If received, increment catalog part stock
            if new_status == "received" and old_status != "received":
                part_res = await db.execute(select(Part).where(Part.part_id == instance.part_id))
                part = part_res.scalar_one()
                part.quantity_on_hand += 1
                instance.received_at = datetime.datetime.now(datetime.timezone.utc)

            # If installed, link and decrement catalog stock (if not already done during receive)
            if new_status == "installed" and old_status != "installed":
                part_res = await db.execute(select(Part).where(Part.part_id == instance.part_id))
                part = part_res.scalar_one()
                # Only decrement if transitioning from non-received directly, or if we track actual on-hand parts
                if old_status == "received":
                    part.quantity_on_hand = max(0, part.quantity_on_hand - 1)
                instance.installed_at = datetime.datetime.now(datetime.timezone.utc)
                
            # If rejected or returned, reverse the received increment
            if new_status in ("rejected", "returned") and old_status == "received":
                part_res = await db.execute(select(Part).where(Part.part_id == instance.part_id))
                part = part_res.scalar_one()
                part.quantity_on_hand = max(0, part.quantity_on_hand - 1)

        if payload.serial_or_lot_number is not None:
            instance.serial_or_lot_number = payload.serial_or_lot_number
        if payload.line_item_id is not None:
            instance.line_item_id = payload.line_item_id
        if payload.rejection_reason is not None:
            instance.rejection_reason = payload.rejection_reason

        await db.flush()
        return instance
