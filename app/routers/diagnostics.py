import uuid
import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Diagnostic, DiagnosticFinding, Visit, DiagnosticTemplate, LineItem, WorkOrder, User
from app.schemas.schemas import (
    DiagnosticCreate, DiagnosticResponse,
    DiagnosticFindingCreate, DiagnosticFindingResponse,
    DiagnosticFindingUpdate,
    QuoteCreate, WorkOrderCreate, LineItemCreate
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

router = APIRouter()

@router.post(
    "/diagnostics",
    response_model=DiagnosticResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_diagnostic(
    payload: DiagnosticCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["technician", "manager", "advisor"]))
):
    if current_user.role == "technician" and current_user.tech_id != payload.tech_id:
        raise HTTPException(status_code=403, detail="Technicians can only assign themselves to a diagnostic.")

    # Check if visit exists
    visit_res = await db.execute(select(Visit).where(Visit.visit_id == payload.visit_id))
    visit = visit_res.scalar_one_or_none()
    if not visit:
        raise HTTPException(status_code=404, detail="Associated customer visit not found.")
        
    if visit.status not in ["checked_in", "in_diagnosis"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot create diagnostic: Visit is currently '{visit.status}', which is invalid for new diagnostics."
        )

    from app.models.models import Technician
    tech_res = await db.execute(
        select(Technician).where(Technician.tech_id == payload.tech_id)
    )
    tech = tech_res.scalar_one_or_none()
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found.")

    try:
        diagnostic = Diagnostic(
            visit_id=payload.visit_id,
            vehicle_id=payload.vehicle_id,
            tech_id=payload.tech_id,
            status="in_progress",
            performed_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(diagnostic)
        await db.flush()

        # Seed from active template if it exists
        template_res = await db.execute(
            select(DiagnosticTemplate)
            .options(selectinload(DiagnosticTemplate.items))
            .where(DiagnosticTemplate.is_active == True)
            .limit(1)
        )
        template = template_res.scalar_one_or_none()
        if template:
            for item in template.items:
                finding = DiagnosticFinding(
                    report_id=diagnostic.report_id,
                    description=item.description,
                    is_critical=False
                )
                db.add(finding)
        
        # Update visit status to 'in_diagnosis'
        visit.status = 'in_diagnosis'
        
        await db.commit()

        # Fetch the complete diagnostic to ensure relationships (like findings) are loaded for serialization
        diag_res = await db.execute(
            select(Diagnostic)
            .options(selectinload(Diagnostic.findings))
            .where(Diagnostic.report_id == diagnostic.report_id)
        )
        return diag_res.scalar_one()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/diagnostics/{report_id}",
    response_model=DiagnosticResponse,
    dependencies=[Depends(RoleChecker(["technician", "manager", "advisor"]))]
)
async def get_diagnostic(report_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Diagnostic)
        .options(selectinload(Diagnostic.findings))
        .where(Diagnostic.report_id == report_id)
    )
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Diagnostic report not found.")
    return report

@router.get(
    "/visits/{visit_id}/diagnostics",
    response_model=List[DiagnosticResponse],
    dependencies=[Depends(RoleChecker(["technician", "manager", "advisor"]))]
)
async def list_visit_diagnostics(visit_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Diagnostic)
        .options(selectinload(Diagnostic.findings))
        .where(Diagnostic.visit_id == visit_id)
    )
    return res.scalars().all()

@router.post(
    "/diagnostics/{report_id}/findings",
    response_model=DiagnosticFindingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["technician", "manager"]))]
)
async def add_diagnostic_finding(
    report_id: uuid.UUID,
    payload: DiagnosticFindingCreate,
    db: AsyncSession = Depends(get_db)
):
    # Verify diagnostic report exists
    res = await db.execute(select(Diagnostic).where(Diagnostic.report_id == report_id))
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Diagnostic report not found.")

    finding = DiagnosticFinding(
        report_id=report_id,
        description=payload.description,
        recommended_service=payload.recommended_service,
        is_critical=payload.is_critical
    )
    db.add(finding)
    await db.flush()
    return finding

@router.put(
    "/diagnostics/findings/{finding_id}",
    response_model=DiagnosticFindingResponse,
    dependencies=[Depends(RoleChecker(["technician", "manager"]))]
)
async def update_diagnostic_finding(
    finding_id: uuid.UUID,
    payload: DiagnosticFindingUpdate,
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(DiagnosticFinding).where(DiagnosticFinding.finding_id == finding_id))
    finding = res.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    if payload.description is not None:
        finding.description = payload.description
    if payload.recommended_service is not None:
        finding.recommended_service = payload.recommended_service
    if payload.is_critical is not None:
        finding.is_critical = payload.is_critical
        
    await db.flush()
    return finding

@router.put(
    "/diagnostics/{report_id}/complete",
    response_model=DiagnosticResponse,
    dependencies=[Depends(RoleChecker(["technician", "manager"]))]
)
async def complete_diagnostic(report_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Diagnostic)
        .options(selectinload(Diagnostic.findings))
        .where(Diagnostic.report_id == report_id)
    )
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Diagnostic report not found.")

    if report.status == "completed":
        raise HTTPException(status_code=400, detail="Diagnostic report is already completed.")

    report.status = "completed"
    
    visit_res = await db.execute(select(Visit).where(Visit.visit_id == report.visit_id))
    visit = visit_res.scalar_one_or_none()
    
    # Only transition Visit and generate drafts if visit is still in checked_in or in_diagnosis
    if visit and visit.status in ["checked_in", "in_diagnosis"]:
        visit.status = 'awaiting_quote'

        # Generate Draft Quote and LineItems
        import decimal
        from app.services.billing_service import BillingService
        from app.services.job_service import JobService

        # 1. Draft Quote
        quote_payload = QuoteCreate(
            customer_id=visit.customer_id,
            vehicle_id=visit.vehicle_id,
            visit_id=visit.visit_id,
            total_amount=decimal.Decimal("0.00"),
            valid_until=datetime.date.today() + datetime.timedelta(days=30),
            status="draft"
        )
        quote = await BillingService.create_quote(db, quote_payload)

        # 2. Draft WorkOrder
        wo_payload = WorkOrderCreate(
            quote_id=quote.quote_id,
            vehicle_id=visit.vehicle_id,
            customer_id=visit.customer_id,
            visit_id=visit.visit_id,
            status="created",
            authorized_amount=decimal.Decimal("0.00")
        )
        wo = await JobService.create_work_order(db, wo_payload)

        # 3. Add $0.00 LineItems for recommended services
        for finding in report.findings:
            if finding.recommended_service:
                li_payload = LineItemCreate(
                    work_order_id=wo.work_order_id,
                    description=finding.recommended_service,
                    billing_mode="flat_rate",
                    price=decimal.Decimal("0.00"),
                    status="not_started"
                )
                await JobService.create_line_item(db, wo.work_order_id, li_payload)

    await db.flush()
    return report
