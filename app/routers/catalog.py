import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.routers.auth_deps import RoleChecker
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/catalog", tags=["Catalog"])

class CatalogImportRequest(BaseModel):
    work_order_id: uuid.UUID
    part_data: Dict[str, Any]

@router.get(
    "/search",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def search_catalog(query: str = Query(..., min_length=2)):
    """Mock external B2B parts catalog search (e.g. Nexpart/Epicor)"""
    return await CatalogService.search_catalog(query)

@router.post(
    "/import",
    response_model=Dict[str, Any],
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def import_part_to_work_order(payload: CatalogImportRequest, db: AsyncSession = Depends(get_db)):
    """
    Imports a part from the mock catalog directly to a Work Order.
    This creates a Part, a PurchaseOrder (submitted state), a PoLineItem, and a Work Order LineItem.
    """
    try:
        return await CatalogService.import_part(db, payload.work_order_id, payload.part_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
