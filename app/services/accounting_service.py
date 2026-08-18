import asyncio
import datetime
import uuid
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Invoice, PurchaseOrder, LineItem, PartInstance

# In-memory mock state for QBO connection
_qbo_connection_state = {
    "is_connected": False,
    "last_sync_time": None,
    "company_name": None,
    "sync_logs": []
}

class AccountingService:
    
    @staticmethod
    async def get_connection_status() -> Dict[str, Any]:
        return _qbo_connection_state
        
    @staticmethod
    async def connect_qbo() -> Dict[str, Any]:
        """Mock OAuth2 connection flow to QuickBooks Online."""
        _qbo_connection_state["is_connected"] = True
        _qbo_connection_state["company_name"] = "Mock Auto Shop LLC"
        _qbo_connection_state["sync_logs"].insert(0, f"[{datetime.datetime.now().isoformat()}] Successfully connected to QuickBooks Online.")
        return _qbo_connection_state
        
    @staticmethod
    async def disconnect_qbo() -> Dict[str, Any]:
        """Mock OAuth2 disconnect flow."""
        _qbo_connection_state["is_connected"] = False
        _qbo_connection_state["company_name"] = None
        _qbo_connection_state["sync_logs"].insert(0, f"[{datetime.datetime.now().isoformat()}] Disconnected from QuickBooks Online.")
        return _qbo_connection_state
        
    @staticmethod
    async def sync_ledger(db: AsyncSession) -> Dict[str, Any]:
        """
        Simulates syncing the local ledger to QBO.
        - Unsynced paid invoices -> QBO Sales Receipts
        - Unsynced received POs -> QBO Bills
        """
        if not _qbo_connection_state.get("is_connected"):
            raise ValueError("Not connected to QuickBooks Online.")
            
        logs = []
        now_str = datetime.datetime.now().isoformat()
        
        # 1. Sync Invoices (Mock: Just find paid invoices)
        invoices_res = await db.execute(select(Invoice).where(Invoice.status == "paid").limit(5))
        invoices = invoices_res.scalars().all()
        for inv in invoices:
            logs.append(f"[{now_str}] Pushed Invoice #{inv.invoice_id} to QBO as Sales Receipt. Amount: ${inv.amount_due}")
            
        # 2. Sync POs (Mock: Find received POs)
        pos_res = await db.execute(select(PurchaseOrder).where(PurchaseOrder.status == "received").limit(5))
        pos = pos_res.scalars().all()
        for po in pos:
            logs.append(f"[{now_str}] Pushed PurchaseOrder #{po.po_id} to QBO as Bill.")
            
        if not logs:
            logs.append(f"[{now_str}] Ledger sync completed. No new items to sync.")
            
        _qbo_connection_state["sync_logs"] = logs + _qbo_connection_state.get("sync_logs", [])
        _qbo_connection_state["sync_logs"] = _qbo_connection_state["sync_logs"][:50] # Keep last 50
        _qbo_connection_state["last_sync_time"] = now_str
        
        return {
            "status": "success",
            "synced_items_count": len(invoices) + len(pos),
            "logs": logs
        }
