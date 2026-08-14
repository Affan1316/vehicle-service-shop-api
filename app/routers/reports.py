import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.schemas import DailyRevenueReport, OutstandingARReport, TechProductivityReport
from app.routers.auth_deps import RoleChecker
from app.services import ReportingService

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get(
    "/daily-revenue",
    response_model=DailyRevenueReport,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def get_daily_revenue_report(
    date: datetime.date = Query(default_factory=datetime.date.today, description="Report target date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Manager endpoint: Daily collected revenue aggregated by payment method and invoice count.
    """
    return await ReportingService.daily_revenue(db, date)


@router.get(
    "/outstanding-ar",
    response_model=OutstandingARReport,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def get_outstanding_ar_report(
    db: AsyncSession = Depends(get_db)
):
    """
    Manager endpoint: Complete accounts receivable aging report with outstanding balances.
    """
    return await ReportingService.outstanding_ar(db)


@router.get(
    "/tech-productivity",
    response_model=TechProductivityReport,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def get_tech_productivity_report(
    start_date: datetime.date = Query(..., description="Range start date (YYYY-MM-DD)"),
    end_date: datetime.date = Query(default_factory=datetime.date.today, description="Range end date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Manager endpoint: Technician labor hours, billed labor value, and completed items in date range.
    """
    return await ReportingService.tech_productivity(db, start_date, end_date)
