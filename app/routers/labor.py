from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from app.routers.auth_deps import RoleChecker
from app.services.labor_service import LaborService

router = APIRouter(prefix="/labor", tags=["Labor Guide"])

@router.get(
    "/decode",
    response_model=Dict[str, Any],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def decode_vin(vin: str = Query(..., min_length=17, max_length=17)):
    """Mock VIN decoder to get vehicle spec configuration for labor lookups"""
    result = await LaborService.decode_vin(vin)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get(
    "/lookup",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def lookup_labor(
    query: str = Query(..., min_length=2),
    vin: str = Query(..., min_length=17, max_length=17)
):
    """Mock standard labor time guide lookup (e.g., MOTOR/ProDemand)"""
    return await LaborService.lookup_labor(query, vin)
