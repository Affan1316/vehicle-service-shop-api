from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth_deps import RoleChecker
from app.services.accounting_service import AccountingService

router = APIRouter(prefix="/accounting", tags=["Accounting & Sync"])

@router.get(
    "/qbo/status",
    response_model=Dict[str, Any],
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def get_qbo_status():
    """Get the current QuickBooks Online connection status and sync logs."""
    return await AccountingService.get_connection_status()

@router.post(
    "/qbo/connect",
    response_model=Dict[str, Any],
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def connect_qbo():
    """Simulate OAuth2 connection to QuickBooks Online."""
    return await AccountingService.connect_qbo()

@router.post(
    "/qbo/disconnect",
    response_model=Dict[str, Any],
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def disconnect_qbo():
    """Simulate disconnecting from QuickBooks Online."""
    return await AccountingService.disconnect_qbo()

@router.post(
    "/qbo/sync",
    response_model=Dict[str, Any],
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def sync_qbo_ledger(db: AsyncSession = Depends(get_db)):
    """Manually trigger a sync of local ledger data to QuickBooks Online."""
    try:
        return await AccountingService.sync_ledger(db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
