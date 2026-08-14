import datetime
import decimal
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload

from app.models.models import Payment, Invoice, Technician, LaborEntry, LineItem
from app.schemas.schemas import (
    DailyRevenueReport, RevenueByMethod,
    OutstandingARReport, OutstandingARItem,
    TechProductivityReport, TechProductivityItem
)


class ReportingService:
    @staticmethod
    async def daily_revenue(db: AsyncSession, target_date: datetime.date) -> DailyRevenueReport:
        """
        Calculates total revenue collected on a specific date, broken down by payment method.
        """
        # Group payments by method for the target date
        stmt = (
            select(
                Payment.method,
                func.coalesce(func.sum(Payment.amount), decimal.Decimal("0.00")).label("total"),
                func.count(Payment.payment_id).label("count")
            )
            .where(func.date(Payment.collected_at) == target_date)
            .group_by(Payment.method)
        )
        res = await db.execute(stmt)
        rows = res.all()

        breakdown = [
            RevenueByMethod(
                method=row.method,
                total=row.total,
                count=row.count
            )
            for row in rows
        ]

        total_revenue = sum((b.total for b in breakdown), decimal.Decimal("0.00"))

        # Distinct invoices paid on that date
        inv_stmt = (
            select(func.count(distinct(Payment.invoice_id)))
            .where(func.date(Payment.collected_at) == target_date)
        )
        inv_res = await db.execute(inv_stmt)
        invoice_count = inv_res.scalar() or 0

        return DailyRevenueReport(
            date=target_date,
            total_revenue=total_revenue,
            invoice_count=invoice_count,
            breakdown_by_method=breakdown
        )

    @staticmethod
    async def outstanding_ar(db: AsyncSession) -> OutstandingARReport:
        """
        Retrieves all unpaid/partially-paid invoices (issued or disputed) with aging metrics.
        """
        stmt = (
            select(Invoice)
            .options(
                selectinload(Invoice.customer),
                selectinload(Invoice.payments)
            )
            .where(Invoice.status.in_(["issued", "disputed"]))
            .order_by(Invoice.issued_at.asc())
        )
        res = await db.execute(stmt)
        invoices = res.scalars().all()

        today = datetime.date.today()
        items: List[OutstandingARItem] = []
        total_outstanding = decimal.Decimal("0.00")

        for inv in invoices:
            balance = inv.total_balance
            if balance > 0:
                issued_date = inv.issued_at.date() if isinstance(inv.issued_at, datetime.datetime) else inv.issued_at
                days_out = max((today - issued_date).days, 0)

                items.append(
                    OutstandingARItem(
                        invoice_id=inv.invoice_id,
                        customer_name=inv.customer.name if inv.customer else "Unknown",
                        customer_id=inv.customer_id,
                        amount_due=inv.amount_due,
                        tax_amount=inv.tax_amount or decimal.Decimal("0.00"),
                        total_balance=balance,
                        issued_at=inv.issued_at,
                        days_outstanding=days_out
                    )
                )
                total_outstanding += balance

        return OutstandingARReport(
            total_outstanding=total_outstanding,
            invoice_count=len(items),
            items=items
        )

    @staticmethod
    async def tech_productivity(
        db: AsyncSession,
        start_date: datetime.date,
        end_date: datetime.date
    ) -> TechProductivityReport:
        """
        Computes technician labor hours, billed labor value, and completed line item counts in date range.
        """
        # Fetch all technicians
        tech_res = await db.execute(select(Technician).order_by(Technician.name.asc()))
        techs = tech_res.scalars().all()

        items: List[TechProductivityItem] = []

        for tech in techs:
            # Query labor entries for this tech within date range
            labor_stmt = (
                select(
                    func.coalesce(func.sum(LaborEntry.hours), decimal.Decimal("0.00")).label("total_hours"),
                    func.count(distinct(LaborEntry.line_item_id)).label("items_count")
                )
                .where(
                    LaborEntry.tech_id == tech.tech_id,
                    LaborEntry.work_date >= start_date,
                    LaborEntry.work_date <= end_date
                )
            )
            labor_res = await db.execute(labor_stmt)
            row = labor_res.one()

            total_hours = row.total_hours
            labor_value = (total_hours * tech.hourly_rate).quantize(decimal.Decimal("0.01"))

            # Count line items completed by this tech in range
            completed_stmt = (
                select(func.count(distinct(LineItem.line_item_id)))
                .join(LaborEntry, LaborEntry.line_item_id == LineItem.line_item_id)
                .where(
                    LaborEntry.tech_id == tech.tech_id,
                    LaborEntry.work_date >= start_date,
                    LaborEntry.work_date <= end_date,
                    LineItem.status == "completed"
                )
            )
            completed_res = await db.execute(completed_stmt)
            line_items_completed = completed_res.scalar() or 0

            items.append(
                TechProductivityItem(
                    tech_id=tech.tech_id,
                    name=tech.name,
                    total_hours=total_hours,
                    total_labor_value=labor_value,
                    line_items_completed=line_items_completed
                )
            )

        return TechProductivityReport(
            start_date=start_date,
            end_date=end_date,
            technicians=items
        )
