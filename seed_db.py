import asyncio
import decimal
import uuid
from sqlalchemy import select

from app.database import async_session
from app.config import settings
from app.security import get_password_hash
from app.models.models import Technician, Bay, Vendor, Payer, Part, User, CannedService


async def seed_admin_user(session):
    print("Seeding Default Admin User...")
    res = await session.execute(
        select(User).where(User.username == settings.SEED_ADMIN_USERNAME)
    )
    existing = res.scalar_one_or_none()
    if not existing:
        admin_user = User(
            username=settings.SEED_ADMIN_USERNAME,
            email=settings.SEED_ADMIN_EMAIL,
            password_hash=get_password_hash(settings.SEED_ADMIN_PASSWORD),
            role="manager",
            is_active=True,
        )
        session.add(admin_user)
        print(f"  Added admin user: {settings.SEED_ADMIN_USERNAME} ({settings.SEED_ADMIN_EMAIL})")
    else:
        print(f"  Admin user already exists: {settings.SEED_ADMIN_USERNAME}")


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
        {"part_number": "OIL-FLTR-01", "name": "Oil Filter", "description": "Standard spin-on oil filter", "category": "Engine Filters", "cost_price": decimal.Decimal("4.50"), "retail_price": decimal.Decimal("12.99"), "quantity_on_hand": 150, "is_returnable": True},
        {"part_number": "BRK-PAD-02", "name": "Brake Pad Set", "description": "Front ceramic brake pads", "category": "Brakes", "cost_price": decimal.Decimal("22.00"), "retail_price": decimal.Decimal("59.99"), "quantity_on_hand": 45, "is_returnable": True},
        {"part_number": "SPK-PLG-03", "name": "Spark Plug", "description": "Iridium spark plug", "category": "Ignition", "cost_price": decimal.Decimal("3.25"), "retail_price": decimal.Decimal("8.99"), "quantity_on_hand": 200, "is_returnable": True},
        {"part_number": "WPR-BLD-04", "name": "Wiper Blade", "description": "22-inch all-season wiper blade", "category": "Accessories", "cost_price": decimal.Decimal("6.00"), "retail_price": decimal.Decimal("14.99"), "quantity_on_hand": 80, "is_returnable": True},
        {"part_number": "BAT-12V-05", "name": "12V Car Battery", "description": "Group 35 650 CCA battery", "category": "Electrical", "cost_price": decimal.Decimal("65.00"), "retail_price": decimal.Decimal("149.99"), "quantity_on_hand": 12, "is_returnable": True},
        {"part_number": "ALT-80A-06", "name": "Alternator 80A", "description": "80-amp remanufactured alternator", "category": "Electrical", "cost_price": decimal.Decimal("85.00"), "retail_price": decimal.Decimal("219.99"), "quantity_on_hand": 3, "is_returnable": True},
        {"part_number": "CAB-FLTR-07", "name": "Cabin Air Filter", "description": "Multi-stage HEPA cabin air filter", "category": "Cabin Filters", "cost_price": decimal.Decimal("8.00"), "retail_price": decimal.Decimal("19.99"), "quantity_on_hand": 60, "is_returnable": True},
        {"part_number": "TIRE-215-08", "name": "215/60R16 Tire", "description": "All-season touring tire", "category": "Tires", "cost_price": decimal.Decimal("55.00"), "retail_price": decimal.Decimal("129.99"), "quantity_on_hand": 24, "is_returnable": False},
        {"part_number": "STR-FLTR-09", "name": "Steering Filter", "description": "Power steering inline fluid filter", "category": "Steering", "cost_price": decimal.Decimal("12.00"), "retail_price": decimal.Decimal("34.99"), "quantity_on_hand": 5, "is_returnable": True},
        {"part_number": "RAD-HOSE-10", "name": "Radiator Hose", "description": "Upper radiator coolant hose", "category": "Cooling", "cost_price": decimal.Decimal("9.00"), "retail_price": decimal.Decimal("24.99"), "quantity_on_hand": 15, "is_returnable": True}
    ]
    
    for part_data in parts:
        res = await session.execute(select(Part).where(Part.part_number == part_data["part_number"]))
        existing = res.scalar_one_or_none()
        if not existing:
            part = Part(**part_data)
            session.add(part)
            print(f"  Added part: {part_data['part_number']} - {part_data['name']} (${part_data['retail_price']})")
        else:
            existing.name = part_data["name"]
            existing.description = part_data["description"]
            existing.cost_price = part_data["cost_price"]
            existing.retail_price = part_data["retail_price"]
            print(f"  Updated existing part pricing: {part_data['part_number']} - {part_data['name']}")


async def seed_canned_services(session):
    print("Seeding Canned Service Menu Items...")
    services = [
        {
            "name": "Full Synthetic Oil & Filter Change",
            "description": "Premium full synthetic oil change up to 5 quarts with OEM filter replacement and multi-point inspection.",
            "category": "Maintenance",
            "billing_mode": "flat_rate",
            "default_price": decimal.Decimal("79.99"),
            "estimated_hours": decimal.Decimal("0.50"),
            "is_active": True
        },
        {
            "name": "Comprehensive Multi-Point Inspection",
            "description": "Full 50-point diagnostic inspection including fluids, battery health, tires, brakes, and suspension.",
            "category": "Diagnostics",
            "billing_mode": "flat_rate",
            "default_price": decimal.Decimal("49.99"),
            "estimated_hours": decimal.Decimal("0.75"),
            "is_active": True
        },
        {
            "name": "Front Brake Pad & Rotor Replacement",
            "description": "Replace front brake pads with ceramic compound and machine or replace rotors.",
            "category": "Brakes",
            "billing_mode": "flat_rate",
            "default_price": decimal.Decimal("249.99"),
            "estimated_hours": decimal.Decimal("1.50"),
            "is_active": True
        },
        {
            "name": "4-Wheel Tire Rotation & Computer Balance",
            "description": "Rotate tires according to drive configuration and precision balance all four wheels.",
            "category": "Tires",
            "billing_mode": "flat_rate",
            "default_price": decimal.Decimal("39.99"),
            "estimated_hours": decimal.Decimal("0.50"),
            "is_active": True
        },
        {
            "name": "Cooling System Flush & Fluid Replacement",
            "description": "Evacuate old engine coolant, pressure test system for leaks, and refill with fresh antifreeze.",
            "category": "Cooling",
            "billing_mode": "flat_rate",
            "default_price": decimal.Decimal("129.99"),
            "estimated_hours": decimal.Decimal("1.00"),
            "is_active": True
        },
        {
            "name": "Advanced Electrical Diagnostic (Hourly)",
            "description": "Oscilloscope and scanner diagnosis of complex electrical, CAN bus, or ECU issues.",
            "category": "Electrical",
            "billing_mode": "hourly",
            "default_price": decimal.Decimal("120.00"),
            "estimated_hours": decimal.Decimal("1.00"),
            "is_active": True
        }
    ]

    for s_data in services:
        res = await session.execute(select(CannedService).where(CannedService.name == s_data["name"]))
        existing = res.scalar_one_or_none()
        if not existing:
            srv = CannedService(**s_data)
            session.add(srv)
            print(f"  Added canned service: {s_data['name']} (${s_data['default_price']})")
        else:
            print(f"  Canned service already exists: {s_data['name']}")


async def run_seed():
    print("--- Starting Idempotent Database Seeding ---")
    async with async_session() as session:
        try:
            await seed_admin_user(session)
            await seed_technicians(session)
            await seed_bays(session)
            await seed_vendors(session)
            await seed_payers(session)
            await seed_parts(session)
            await seed_canned_services(session)
            await session.commit()
            print("\nDatabase seeding completed successfully!")
        except Exception as e:
            await session.rollback()
            print("\nError occurred during database seeding:", e)
            raise

if __name__ == "__main__":
    asyncio.run(run_seed())
