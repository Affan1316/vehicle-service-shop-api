import io
import uuid
import decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from app.config import settings
from app.models.models import Quote, Invoice, WorkOrder
from app.exceptions import NotFoundError


class PDFService:
    @staticmethod
    def _create_styles():
        styles = getSampleStyleSheet()
        primary_color = colors.HexColor("#1e293b")
        accent_color = colors.HexColor("#2563eb")

        styles.add(ParagraphStyle(
            name="ShopTitle",
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=primary_color
        ))
        styles.add(ParagraphStyle(
            name="DocTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=accent_color,
            alignment=2  # Right aligned
        ))
        styles.add(ParagraphStyle(
            name="MetaText",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569")
        ))
        styles.add(ParagraphStyle(
            name="MetaTextBold",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1e293b")
        ))
        styles.add(ParagraphStyle(
            name="SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=primary_color,
            spaceAfter=6
        ))
        styles.add(ParagraphStyle(
            name="TableHead",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.white
        ))
        styles.add(ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155")
        ))
        styles.add(ParagraphStyle(
            name="TableCellBold",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1e293b")
        ))
        styles.add(ParagraphStyle(
            name="TableCellRight",
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=2,
            textColor=colors.HexColor("#334155")
        ))
        styles.add(ParagraphStyle(
            name="TableCellRightBold",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=2,
            textColor=colors.HexColor("#1e293b")
        ))
        styles.add(ParagraphStyle(
            name="FooterText",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1  # Centered
        ))
        return styles

    @classmethod
    async def generate_quote_pdf(cls, db: AsyncSession, quote_id: uuid.UUID) -> bytes:
        """
        Generates a professional PDF quote document.
        """
        stmt = (
            select(Quote)
            .options(
                selectinload(Quote.customer),
                selectinload(Quote.vehicle),
                selectinload(Quote.work_order).selectinload(WorkOrder.line_items)
            )
            .where(Quote.quote_id == quote_id)
        )
        res = await db.execute(stmt)
        quote = res.scalar_one_or_none()
        if not quote:
            raise NotFoundError(f"Quote with ID {quote_id} not found.")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = cls._create_styles()
        elements = []

        # 1. Header: Shop Info (Left) + Document Meta (Right)
        header_data = [
            [
                Paragraph(f"<b>{settings.SHOP_NAME}</b><br/>{settings.SHOP_ADDRESS}<br/>Phone: {settings.SHOP_PHONE}", styles["MetaText"]),
                Paragraph(f"<b>ESTIMATE / QUOTE</b><br/>Quote #: {str(quote.quote_id)[:8].upper()}<br/>Date: {quote.drafted_at.strftime('%b %d, %Y')}<br/>Valid Until: {quote.valid_until.strftime('%b %d, %Y')}<br/>Status: <b>{quote.status.upper()}</b>", styles["DocTitle"])
            ]
        ]
        header_table = Table(header_data, colWidths=[3.5 * inch, 3.5 * inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=15))

        # 2. Customer & Vehicle Info Grid
        cust = quote.customer
        veh = quote.vehicle
        cust_info = f"<b>Customer:</b> {cust.name if cust else 'N/A'}<br/>"
        if cust and cust.phone:
            cust_info += f"<b>Phone:</b> {cust.phone}<br/>"
        if cust and cust.email:
            cust_info += f"<b>Email:</b> {cust.email}<br/>"
        if cust and cust.billing_address:
            cust_info += f"<b>Address:</b> {cust.billing_address}"

        veh_info = f"<b>Vehicle:</b> {veh.year} {veh.make} {veh.model if veh else 'N/A'}<br/>"
        veh_info += f"<b>VIN:</b> {veh.vin if veh else 'N/A'}<br/>"
        if veh and veh.license_plate:
            veh_info += f"<b>Plate:</b> {veh.license_plate}<br/>"
        if veh and veh.current_mileage:
            veh_info += f"<b>Mileage:</b> {veh.current_mileage:,} mi"

        info_data = [
            [Paragraph(cust_info, styles["MetaText"]), Paragraph(veh_info, styles["MetaText"])]
        ]
        info_table = Table(info_data, colWidths=[3.5 * inch, 3.5 * inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 15))

        # 3. Itemized Services Table
        elements.append(Paragraph("Proposed Services & Parts", styles["SectionHeader"]))

        table_rows = [
            [
                Paragraph("<b>#</b>", styles["TableHead"]),
                Paragraph("<b>Description</b>", styles["TableHead"]),
                Paragraph("<b>Billing</b>", styles["TableHead"]),
                Paragraph("<b>Amount</b>", styles["TableHead"]),
            ]
        ]

        line_items = quote.work_order.line_items if quote.work_order else []
        if line_items:
            for idx, item in enumerate(line_items, 1):
                price_str = f"${item.price:.2f}" if not item.is_complimentary else "COMPLIMENTARY"
                table_rows.append([
                    Paragraph(str(idx), styles["TableCell"]),
                    Paragraph(item.description, styles["TableCell"]),
                    Paragraph(item.billing_mode.replace("_", " ").title(), styles["TableCell"]),
                    Paragraph(price_str, styles["TableCellRight"]),
                ])
        else:
            table_rows.append([
                Paragraph("1", styles["TableCell"]),
                Paragraph("Estimated service package as quoted", styles["TableCell"]),
                Paragraph("Flat Rate", styles["TableCell"]),
                Paragraph(f"${quote.total_amount:.2f}", styles["TableCellRight"]),
            ])

        # Subtotal / Total rows
        table_rows.append([
            "", "", Paragraph("<b>Total Estimated:</b>", styles["TableCellRightBold"]),
            Paragraph(f"<b>${quote.total_amount:.2f}</b>", styles["TableCellRightBold"])
        ])

        items_table = Table(table_rows, colWidths=[0.5 * inch, 4.0 * inch, 1.3 * inch, 1.2 * inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEABOVE', (2, -1), (3, -1), 1, colors.HexColor("#1e293b")),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 20))

        # 4. Terms & Signature Block
        elements.append(Paragraph(
            "<b>Terms & Conditions:</b> This estimate is valid for 30 days from issuance. "
            "Additional repairs not listed above will not be performed without prior customer authorization.",
            styles["MetaText"]
        ))
        elements.append(Spacer(1, 25))

        sig_data = [
            [
                Paragraph("Customer Signature: _______________________", styles["MetaTextBold"]),
                Paragraph("Date: _______________", styles["MetaTextBold"])
            ]
        ]
        sig_table = Table(sig_data, colWidths=[4.5 * inch, 2.5 * inch])
        sig_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        elements.append(sig_table)
        elements.append(Spacer(1, 20))
        elements.append(Paragraph(f"Thank you for choosing {settings.SHOP_NAME}!", styles["FooterText"]))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    async def generate_invoice_pdf(cls, db: AsyncSession, invoice_id: uuid.UUID) -> bytes:
        """
        Generates a comprehensive PDF invoice with tax, credits, payments, and balance breakdown.
        """
        stmt = (
            select(Invoice)
            .options(
                selectinload(Invoice.customer),
                selectinload(Invoice.work_order).selectinload(WorkOrder.vehicle),
                selectinload(Invoice.work_order).selectinload(WorkOrder.line_items),
                selectinload(Invoice.payments)
            )
            .where(Invoice.invoice_id == invoice_id)
        )
        res = await db.execute(stmt)
        invoice = res.scalar_one_or_none()
        if not invoice:
            raise NotFoundError(f"Invoice with ID {invoice_id} not found.")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = cls._create_styles()
        elements = []

        # 1. Header: Shop Info (Left) + Invoice Meta (Right)
        header_data = [
            [
                Paragraph(f"<b>{settings.SHOP_NAME}</b><br/>{settings.SHOP_ADDRESS}<br/>Phone: {settings.SHOP_PHONE}", styles["MetaText"]),
                Paragraph(f"<b>TAX INVOICE</b><br/>Invoice #: {str(invoice.invoice_id)[:8].upper()}<br/>Date: {invoice.issued_at.strftime('%b %d, %Y')}<br/>Status: <b>{invoice.status.upper()}</b>", styles["DocTitle"])
            ]
        ]
        header_table = Table(header_data, colWidths=[3.5 * inch, 3.5 * inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=15))

        # 2. Customer & Vehicle Info Grid
        cust = invoice.customer
        wo = invoice.work_order
        veh = wo.vehicle if wo else None

        cust_info = f"<b>Billed To:</b><br/>{cust.name if cust else 'N/A'}<br/>"
        if cust and cust.phone:
            cust_info += f"Phone: {cust.phone}<br/>"
        if cust and cust.email:
            cust_info += f"Email: {cust.email}<br/>"
        if cust and cust.billing_address:
            cust_info += f"{cust.billing_address}<br/>"
        if cust and cust.tax_exempt:
            cust_info += "<b>Tax Status:</b> Tax-Exempt"

        veh_info = "<b>Vehicle Service Details:</b><br/>"
        if veh:
            veh_info += f"{veh.year} {veh.make} {veh.model}<br/>VIN: {veh.vin}<br/>"
            if veh.license_plate:
                veh_info += f"Plate: {veh.license_plate}<br/>"
            if veh.current_mileage:
                veh_info += f"Mileage: {veh.current_mileage:,} mi<br/>"
        if wo:
            veh_info += f"Work Order #: {str(wo.work_order_id)[:8].upper()}"

        info_data = [
            [Paragraph(cust_info, styles["MetaText"]), Paragraph(veh_info, styles["MetaText"])]
        ]
        info_table = Table(info_data, colWidths=[3.5 * inch, 3.5 * inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 15))

        # 3. Itemized Services Table
        elements.append(Paragraph("Completed Services & Line Items", styles["SectionHeader"]))
        table_rows = [
            [
                Paragraph("<b>#</b>", styles["TableHead"]),
                Paragraph("<b>Description</b>", styles["TableHead"]),
                Paragraph("<b>Billing</b>", styles["TableHead"]),
                Paragraph("<b>Amount</b>", styles["TableHead"]),
            ]
        ]

        line_items = wo.line_items if wo else []
        if line_items:
            for idx, item in enumerate(line_items, 1):
                price_str = f"${item.price:.2f}" if not item.is_complimentary else "COMPLIMENTARY"
                table_rows.append([
                    Paragraph(str(idx), styles["TableCell"]),
                    Paragraph(item.description, styles["TableCell"]),
                    Paragraph(item.billing_mode.replace("_", " ").title(), styles["TableCell"]),
                    Paragraph(price_str, styles["TableCellRight"]),
                ])
        else:
            table_rows.append([
                Paragraph("1", styles["TableCell"]),
                Paragraph("Vehicle service labor & parts (closed work order)", styles["TableCell"]),
                Paragraph("Flat Rate", styles["TableCell"]),
                Paragraph(f"${invoice.amount_due:.2f}", styles["TableCellRight"]),
            ])

        # Financial Summary Rows
        tax_amt = invoice.tax_amount or decimal.Decimal("0.00")
        credit_amt = invoice.credit_amount or decimal.Decimal("0.00")
        paid_amt = sum((p.amount for p in invoice.payments), decimal.Decimal("0.00"))
        balance_due = invoice.total_balance

        table_rows.append(["", "", Paragraph("Subtotal:", styles["TableCellRight"]), Paragraph(f"${invoice.amount_due:.2f}", styles["TableCellRight"])])
        if tax_amt > 0:
            tax_label = f"{settings.TAX_LABEL} ({(invoice.tax_rate or 0)*100:.1f}%):"
            table_rows.append(["", "", Paragraph(tax_label, styles["TableCellRight"]), Paragraph(f"${tax_amt:.2f}", styles["TableCellRight"])])
        if credit_amt > 0:
            table_rows.append(["", "", Paragraph("Credits Applied:", styles["TableCellRight"]), Paragraph(f"-${credit_amt:.2f}", styles["TableCellRight"])])
        if paid_amt > 0:
            table_rows.append(["", "", Paragraph("Payments Received:", styles["TableCellRightBold"]), Paragraph(f"-${paid_amt:.2f}", styles["TableCellRightBold"])])
        table_rows.append(["", "", Paragraph("<b>Balance Due:</b>", styles["TableCellRightBold"]), Paragraph(f"<b>${balance_due:.2f}</b>", styles["TableCellRightBold"])])

        items_table = Table(table_rows, colWidths=[0.5 * inch, 4.0 * inch, 1.3 * inch, 1.2 * inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, len(line_items) if line_items else 1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEABOVE', (2, -1), (3, -1), 1.5, colors.HexColor("#1e293b")),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 15))

        # 4. Payment History (if any)
        if invoice.payments:
            elements.append(Paragraph("Payment Transactions", styles["SectionHeader"]))
            pay_rows = [
                [
                    Paragraph("<b>Date</b>", styles["TableHead"]),
                    Paragraph("<b>Method</b>", styles["TableHead"]),
                    Paragraph("<b>Reference</b>", styles["TableHead"]),
                    Paragraph("<b>Amount</b>", styles["TableHead"]),
                ]
            ]
            for p in invoice.payments:
                ref = f"Ref #{str(p.payment_id)[:8]}"
                if p.refund_amount and p.refund_amount > 0:
                    ref += f" (Refunded: -${p.refund_amount:.2f})"
                pay_rows.append([
                    Paragraph(p.collected_at.strftime('%b %d, %Y %I:%M %p'), styles["TableCell"]),
                    Paragraph(p.method.replace("_", " ").title(), styles["TableCell"]),
                    Paragraph(ref, styles["TableCell"]),
                    Paragraph(f"${p.amount:.2f}", styles["TableCellRight"]),
                ])
            pay_table = Table(pay_rows, colWidths=[2.2 * inch, 1.5 * inch, 2.1 * inch, 1.2 * inch])
            pay_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#475569")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(pay_table)
            elements.append(Spacer(1, 15))

        # 5. Footer & Terms
        elements.append(Paragraph(
            "<b>Warranty & Terms:</b> All repair work is covered by our standard warranty. "
            "Parts and labor warranties are subject to initial terms. Thank you for your business!",
            styles["MetaText"]
        ))
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(f"{settings.SHOP_NAME} • {settings.SHOP_ADDRESS} • {settings.SHOP_PHONE}", styles["FooterText"]))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
