import logging
import uuid
import datetime
import decimal
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import NotFoundError, ValidationError, PaymentGatewayError
from app.models.models import Customer, Invoice, Payment

logger = logging.getLogger(__name__)


class StripeService:
    @classmethod
    def _ensure_stripe_configured(cls):
        """Verify that Stripe is enabled and credentials are configured."""
        if not settings.STRIPE_ENABLED or not settings.STRIPE_SECRET_KEY:
            raise PaymentGatewayError("Stripe payment gateway is not enabled or configured.")

    @classmethod
    def _get_stripe(cls):
        """Import and configure the Stripe module with the configured API key."""
        cls._ensure_stripe_configured()
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe

    @classmethod
    async def get_or_create_stripe_customer(
        cls,
        db: AsyncSession,
        customer: Customer
    ) -> Optional[str]:
        """
        Find existing Stripe Customer ID or create a new customer record on Stripe.
        Persists the stripe_customer_id to the database if created.
        """
        if customer.stripe_customer_id:
            return customer.stripe_customer_id

        if not settings.STRIPE_ENABLED or not settings.STRIPE_SECRET_KEY:
            return None

        try:
            stripe = cls._get_stripe()
            stripe_customer = stripe.Customer.create(
                name=customer.name,
                email=customer.email or None,
                phone=customer.phone or None,
                metadata={
                    "customer_id": str(customer.customer_id),
                    "customer_type": customer.customer_type
                }
            )
            customer.stripe_customer_id = stripe_customer.id
            await db.flush()
            logger.info("Created Stripe customer %s for customer_id=%s", stripe_customer.id, customer.customer_id)
            return stripe_customer.id
        except Exception as exc:
            logger.warning("Failed to create Stripe customer for %s: %s", customer.customer_id, exc)
            return None

    @classmethod
    async def create_checkout_session(
        cls,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for the remaining balance on an invoice.
        Returns a dict with session_id, checkout_url, invoice_id, and amount.
        """
        stripe = cls._get_stripe()

        # 1. Fetch invoice with customer and payments loaded
        stmt = (
            select(Invoice)
            .options(
                selectinload(Invoice.customer),
                selectinload(Invoice.payments)
            )
            .where(Invoice.invoice_id == invoice_id)
        )
        res = await db.execute(stmt)
        invoice = res.scalar_one_or_none()

        if not invoice:
            raise NotFoundError(f"Invoice with ID {invoice_id} not found.")

        if invoice.status in ('paid', 'voided', 'credited'):
            raise ValidationError(f"Cannot pay an invoice with status '{invoice.status}'.")

        # 2. Compute outstanding balance due
        balance = invoice.total_balance
        if balance <= decimal.Decimal('0.00'):
            raise ValidationError("Invoice has no remaining balance due.")

        # 3. Get or link Stripe customer if available
        stripe_cust_id = None
        if invoice.customer:
            stripe_cust_id = await cls.get_or_create_stripe_customer(db, invoice.customer)

        # 4. Convert dollar amount to cents (integer)
        amount_cents = int(round(balance * decimal.Decimal('100')))
        effective_success_url = success_url or settings.STRIPE_SUCCESS_URL
        effective_cancel_url = cancel_url or settings.STRIPE_CANCEL_URL

        # 5. Build session parameters
        session_params: Dict[str, Any] = {
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Invoice #{str(invoice_id)[:8]}",
                            "description": f"Payment for repair work order - {settings.SHOP_NAME}"
                        },
                        "unit_amount": amount_cents
                    },
                    "quantity": 1
                }
            ],
            "mode": "payment",
            "client_reference_id": str(invoice_id),
            "metadata": {
                "invoice_id": str(invoice_id),
                "customer_id": str(invoice.customer_id) if invoice.customer_id else ""
            },
            "success_url": effective_success_url,
            "cancel_url": effective_cancel_url
        }

        if stripe_cust_id:
            session_params["customer"] = stripe_cust_id
        elif invoice.customer and invoice.customer.email:
            session_params["customer_email"] = invoice.customer.email

        try:
            session = stripe.checkout.Session.create(**session_params)
            logger.info("Created Stripe Checkout Session %s for invoice_id=%s, amount=$%s", session.id, invoice_id, balance)
            return {
                "session_id": session.id,
                "checkout_url": session.url,
                "invoice_id": invoice_id,
                "amount": balance
            }
        except Exception as exc:
            logger.error("Stripe Checkout Session creation failed: %s", exc)
            raise PaymentGatewayError(f"Stripe Checkout error: {str(exc)}") from exc

    @classmethod
    def process_webhook_event(
        cls,
        payload: bytes,
        sig_header: str
    ) -> Dict[str, Any]:
        """
        Verify Stripe webhook cryptographic signature and construct the event object.
        """
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise PaymentGatewayError("STRIPE_WEBHOOK_SECRET is not configured.")

        stripe = cls._get_stripe()
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except Exception as exc:
            logger.warning("Stripe webhook signature verification failed: %s", exc)
            raise ValidationError(f"Invalid Stripe webhook payload: {str(exc)}") from exc

    @classmethod
    async def handle_checkout_completed(
        cls,
        db: AsyncSession,
        session_data: Dict[str, Any]
    ) -> Optional[Payment]:
        """
        Process `checkout.session.completed` event:
        1. Read invoice_id from session metadata
        2. Verify invoice and avoid duplicate payment creation (idempotency)
        3. Record Payment with stripe tracking IDs
        4. Auto-transition invoice status to 'paid' if total balance is resolved
        """
        metadata = session_data.get("metadata") or {}
        invoice_id_str = metadata.get("invoice_id") or session_data.get("client_reference_id")

        if not invoice_id_str:
            logger.warning("Stripe session %s missing invoice_id metadata.", session_data.get("id"))
            return None

        try:
            invoice_uuid = uuid.UUID(invoice_id_str)
        except ValueError:
            logger.error("Invalid invoice UUID in Stripe session: %s", invoice_id_str)
            return None

        session_id = session_data.get("id")
        payment_intent_id = session_data.get("payment_intent")

        # Check for existing payment with this session_id (idempotency)
        existing_res = await db.execute(
            select(Payment).where(Payment.stripe_checkout_session_id == session_id)
        )
        existing_payment = existing_res.scalar_one_or_none()
        if existing_payment:
            logger.info("Payment for Stripe session %s already recorded.", session_id)
            return existing_payment

        # Load invoice with payments
        inv_res = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.payments))
            .where(Invoice.invoice_id == invoice_uuid)
        )
        invoice = inv_res.scalar_one_or_none()
        if not invoice:
            logger.error("Invoice %s from Stripe webhook not found in database.", invoice_uuid)
            return None

        amount_cents = session_data.get("amount_total", 0)
        amount_dollars = decimal.Decimal(amount_cents) / decimal.Decimal('100')

        payment = Payment(
            invoice_id=invoice.invoice_id,
            amount=amount_dollars,
            method="stripe",
            collected_at=datetime.datetime.now(datetime.timezone.utc),
            stripe_checkout_session_id=session_id,
            stripe_payment_intent_id=payment_intent_id
        )
        db.add(payment)
        await db.flush()

        # Check if invoice is fully paid
        paid_amount = sum(p.amount for p in invoice.payments) + payment.amount
        credit = invoice.credit_amount or decimal.Decimal('0.00')
        tax = invoice.tax_amount or decimal.Decimal('0.00')
        total_with_tax = invoice.amount_due + tax

        if total_with_tax - credit - paid_amount <= 0:
            invoice.status = "paid"
            await db.flush()

        logger.info("Recorded Stripe payment %s for invoice %s ($%s).", payment.payment_id, invoice.invoice_id, amount_dollars)
        return payment

    @classmethod
    async def create_refund(
        cls,
        payment: Payment,
        amount: decimal.Decimal,
        reason: str
    ) -> Optional[str]:
        """
        Issue an online refund via Stripe API for a payment processed through Stripe.
        Returns the Stripe refund ID.
        """
        if not (payment.stripe_payment_intent_id or payment.stripe_charge_id):
            logger.info("Payment %s has no Stripe tracking IDs; skipping online processor refund.", payment.payment_id)
            return None

        if not settings.STRIPE_ENABLED or not settings.STRIPE_SECRET_KEY:
            logger.warning("Stripe is disabled; cannot execute online refund for payment %s.", payment.payment_id)
            return None

        stripe = cls._get_stripe()
        amount_cents = int(round(amount * decimal.Decimal('100')))

        refund_params: Dict[str, Any] = {
            "amount": amount_cents,
            "metadata": {
                "payment_id": str(payment.payment_id),
                "invoice_id": str(payment.invoice_id),
                "reason": reason
            }
        }

        if payment.stripe_payment_intent_id:
            refund_params["payment_intent"] = payment.stripe_payment_intent_id
        elif payment.stripe_charge_id:
            refund_params["charge"] = payment.stripe_charge_id

        try:
            refund = stripe.Refund.create(**refund_params)
            logger.info("Issued Stripe refund %s for payment_id=%s, amount=$%s", refund.id, payment.payment_id, amount)
            return refund.id
        except Exception as exc:
            logger.error("Stripe refund failed for payment_id=%s: %s", payment.payment_id, exc)
            raise PaymentGatewayError(f"Stripe refund error: {str(exc)}") from exc

    @classmethod
    def get_payment_status(
        cls,
        payment_intent_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve live status of a PaymentIntent directly from Stripe.
        """
        stripe = cls._get_stripe()
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                "stripe_status": intent.status,
                "stripe_payment_intent_id": intent.id,
                "amount": decimal.Decimal(intent.amount) / decimal.Decimal('100'),
                "currency": intent.currency
            }
        except Exception as exc:
            logger.error("Failed to retrieve Stripe PaymentIntent %s: %s", payment_intent_id, exc)
            raise PaymentGatewayError(f"Stripe status error: {str(exc)}") from exc
