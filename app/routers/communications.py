from pydantic import BaseModel, Field
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import Customer, User, CommunicationLog
from app.routers.auth_deps import RoleChecker


from app.services.communication_service import CommunicationService
from app.exceptions import NotFoundError

router = APIRouter()

class SendMessageRequest(BaseModel):
    body: str = Field(..., max_length=1000)


@router.post("/customers/{customer_id}/communications", status_code=status.HTTP_201_CREATED)
async def send_customer_message(
    customer_id: uuid.UUID,
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Send an SMS message to a customer and log it in the timeline.
    """
    res = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
    customer = res.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    if not customer.phone:
        raise HTTPException(status_code=400, detail="Customer does not have a phone number on file")
        
    # Send SMS
    success = CommunicationService.send_sms(customer.phone, payload.body)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send SMS")
        
    log = CommunicationLog(

        customer_id=customer_id,
        type="sms",
        body=payload.body,
        status="sent"
    )
    db.add(log)
    await db.commit()
    
    return {"status": "success", "message": "Message sent"}
