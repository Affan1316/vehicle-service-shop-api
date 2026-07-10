import asyncio
import decimal
import uuid
from sqlalchemy import select

from app.database import async_session
from app.models.models import Technician, Bay, Vendor, Payer, Part

async def seed_technicians(session):
    print("Seeding Technicians...")
    # Generate deterministic UUIDs for idempotent seeding
    technicians = [
        {"tech_id": uuid.uuid5(uuid.NAMESPACE_DNS, "tech-1"), "name": "Alice Smith", "hourly_rate": decimal.Decimal("45.00")},
        {"tech_id": uuid.uuid5(uuid.NAMESPACE_DNS, "tech-2"), "name": "Bob Johnson", "hourly_rate": decimal.Decimal("55.00")},
        {"tech_id": uuid.uuid5(uuid.NAMESPACE_DNS, "tech-3"), "name": "Charlie Brown", "hourly_rate": decimal.Decimal("60.00")},
        {"tech_id": uuid.uuid5(uuid.NAMESPACE_DNS, "tech-4"), "name": "Diana Prince", "hourly_rate": decimal.Decimal("50.00")}
    ]
    
    for tech_data in technicians:
        res = await session.execute(select(Technician).where(Technician.tech_id == tech_data["tech_id"]))
        if not res.scalar_one_or_none():
            tech = Technician(**tech_data)
            session.add(tech)
            print(f"  Added technician: {tech_data['name']} ({tech_data['tech_id']})")
        else:
            print(f"  Technician already exists: {tech_data['name']}")

async def seed_bays(session):
    print("Seeding Bays...")
    bays = [
        {"bay_type": "Diagnostics", "status": "available"},
        {"bay_type": "Alignment", "status": "available"},
        {"bay_type": "Heavy Lift", "status": "available"},
        {"bay_type": "General Service", "status": "available"},
        {"bay_type": "Quick Lube", "status": "available"}
    ]
    
    for bay_data in bays:
        res = await session.execute(select(Bay).where(Bay.bay_type == bay_data["bay_type"]))
        if not res.scalar_one_or_none():
            bay = Bay(**bay_data)
            session.add(bay)
            print(f"  Added bay: {bay_data['bay_type']}")
        else:
            print(f"  Bay already exists: {bay_data['bay_type']}")

async def seed_vendors(session):
    print("Seeding Vendors...")
    vendors = [
        {"name": "AutoZone Pro", "vendor_type": "Parts Supplier"},
        {"name": "NAPA Auto Parts", "vendor_type": "Parts Supplier"},
        {"name": "Carquest Auto Parts", "vendor_type": "Parts Supplier"},
        {"name": "Advance Auto Parts", "vendor_type": "Parts Supplier"}
    ]
    
    for vendor_data in vendors:
        res = await session.execute(select(Vendor).where(Vendor.name == vendor_data["name"]))
        if not res.scalar_one_or_none():
            vendor = Vendor(**vendor_data)
            session.add(vendor)
            print(f"  Added vendor: {vendor_data['name']}")
        else:
            print(f"  Vendor already exists: {vendor_data['name']}")

async def seed_payers(session):
    print("Seeding Payers...")
    payers = [
        {"name": "Geico Insurance", "payer_type": "insurer", "contact_info": "claims@geico.com", "billing_terms": "Net 30"},
        {"name": "State Farm Insurance", "payer_type": "insurer", "contact_info": "claims@statefarm.com", "billing_terms": "Net 30"},
        {"name": "CarShield Warranty", "payer_type": "warranty_company", "contact_info": "auth@carshield.com", "billing_terms": "Net 15"},
        {"name": "Adesa Fleet Services", "payer_type": "fleet_account", "contact_info": "fleet@adesa.com", "billing_terms": "Net 45"}
    ]
    
    for payer_data in payers:
        res = await session.execute(select(Payer).where(Payer.name == payer_data["name"]))
        if not res.scalar_one_or_none():
            payer = Payer(**payer_data)
            session.add(payer)
            print(f"  Added payer: {payer_data['name']}")
        else:
            print(f"  Payer already exists: {payer_data['name']}")

async def seed_parts(session):
    print("Seeding Parts Catalog...")
    parts = [
        {"part_number": "OIL-FLTR-01", "category": "Engine Filters", "quantity_on_hand": 150, "is_returnable": True},
        {"part_number": "BRK-PAD-02", "category": "Brakes", "quantity_on_hand": 45, "is_returnable": True},
        {"part_number": "SPK-PLG-03", "category": "Ignition", "quantity_on_hand": 200, "is_returnable": True},
        {"part_number": "WPR-BLD-04", "category": "Accessories", "quantity_on_hand": 80, "is_returnable": True},
        {"part_number": "BAT-12V-05", "category": "Electrical", "quantity_on_hand": 12, "is_returnable": True},
        {"part_number": "ALT-80A-06", "category": "Electrical", "quantity_on_hand": 3, "is_returnable": True},
        {"part_number": "CAB-FLTR-07", "category": "Cabin Filters", "quantity_on_hand": 60, "is_returnable": True},
        {"part_number": "TIRE-215-08", "category": "Tires", "quantity_on_hand": 24, "is_returnable": False},
        {"part_number": "STR-FLTR-09", "category": "Steering", "quantity_on_hand": 5, "is_returnable": True},
        {"part_number": "RAD-HOSE-10", "category": "Cooling", "quantity_on_hand": 15, "is_returnable": True}
    ]
    
    for part_data in parts:
        res = await session.execute(select(Part).where(Part.part_number == part_data["part_number"]))
        if not res.scalar_one_or_none():
            part = Part(**part_data)
            session.add(part)
            print(f"  Added part: {part_data['part_number']} ({part_data['category']})")
        else:
            print(f"  Part already exists: {part_data['part_number']}")

async def run_seed():
    print("--- Starting Idempotent Database Seeding ---")
    async with async_session() as session:
        try:
            await seed_technicians(session)
            await seed_bays(session)
            await seed_vendors(session)
            await seed_payers(session)
            await seed_parts(session)
            await session.commit()
            print("\nDatabase seeding completed successfully!")
        except Exception as e:
            await session.rollback()
            print("\nError occurred during database seeding:", e)
            raise

if __name__ == "__main__":
    asyncio.run(run_seed())
