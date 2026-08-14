import logging
import uuid
from email.message import EmailMessage
import aiosmtplib

from app.config import settings

logger = logging.getLogger("auto_shop.email")


class EmailService:
    @staticmethod
    async def send_email(to_email: str, subject: str, html_body: str) -> bool:
        """
        Sends an email asynchronously via SMTP.
        If EMAIL_ENABLED is False or to_email is empty, logs and returns True (no-op).
        """
        if not settings.EMAIL_ENABLED:
            logger.info("EMAIL_ENABLED is False. Skipping email to '%s' (Subject: '%s').", to_email, subject)
            return True

        if not to_email or "@" not in to_email:
            logger.warning("Invalid or empty recipient email '%s'. Skipping send.", to_email)
            return False

        message = EmailMessage()
        message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(html_body, subtype="html")

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER if settings.SMTP_USER else None,
                password=settings.SMTP_PASSWORD if settings.SMTP_PASSWORD else None,
                start_tls=settings.SMTP_USE_TLS,
                timeout=10
            )
            logger.info("Successfully sent email to '%s' (Subject: '%s')", to_email, subject)
            return True
        except Exception as e:
            logger.error("Failed to send email to '%s': %s", to_email, str(e), exc_info=True)
            return False

    @classmethod
    async def send_quote_ready(
        cls,
        to_email: str,
        customer_name: str,
        quote_id: uuid.UUID,
        total_amount: float
    ) -> bool:
        """
        Notifies customer that their service quote/estimate is ready for review.
        """
        subject = f"Your Service Estimate is Ready — {settings.SHOP_NAME}"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
            <h2 style="color: #1e293b;">{settings.SHOP_NAME}</h2>
            <p>Dear {customer_name},</p>
            <p>Your repair estimate (Quote #{str(quote_id)[:8].upper()}) has been prepared and is ready for your review.</p>
            <div style="background-color: #f1f5f9; padding: 15px; border-radius: 6px; margin: 20px 0;">
                <p style="margin: 0; font-size: 16px;"><strong>Estimated Total:</strong> ${total_amount:,.2f}</p>
            </div>
            <p>You can review, approve, or decline your estimate online or contact our service advisors directly.</p>
            <p>Thank you for choosing {settings.SHOP_NAME}!</p>
            <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;" />
            <p style="font-size: 12px; color: #64748b;">{settings.SHOP_NAME} • {settings.SHOP_ADDRESS} • {settings.SHOP_PHONE}</p>
        </div>
        """
        return await cls.send_email(to_email, subject, body)

    @classmethod
    async def send_vehicle_ready(
        cls,
        to_email: str,
        customer_name: str,
        vehicle_info: str,
        work_order_id: uuid.UUID
    ) -> bool:
        """
        Notifies customer that their vehicle repairs are completed and ready for pickup.
        """
        subject = f"Your Vehicle is Ready for Pickup! — {settings.SHOP_NAME}"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
            <h2 style="color: #1e293b;">{settings.SHOP_NAME}</h2>
            <p>Dear {customer_name},</p>
            <p>Great news! All scheduled services and repairs for your <strong>{vehicle_info}</strong> (Work Order #{str(work_order_id)[:8].upper()}) have been completed.</p>
            <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0;">
                <p style="margin: 0; color: #065f46; font-weight: bold;">Your vehicle has passed quality inspection and is ready for pickup.</p>
            </div>
            <p>Please stop by during our business hours to settle your invoice and pick up your keys.</p>
            <p>Thank you for your business!</p>
            <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;" />
            <p style="font-size: 12px; color: #64748b;">{settings.SHOP_NAME} • {settings.SHOP_ADDRESS} • {settings.SHOP_PHONE}</p>
        </div>
        """
        return await cls.send_email(to_email, subject, body)

    @classmethod
    async def send_appointment_reminder(
        cls,
        to_email: str,
        customer_name: str,
        appointment_date: str,
        vehicle_info: str
    ) -> bool:
        """
        Sends an appointment confirmation / reminder to the customer.
        """
        subject = f"Appointment Confirmation — {settings.SHOP_NAME}"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
            <h2 style="color: #1e293b;">{settings.SHOP_NAME}</h2>
            <p>Dear {customer_name},</p>
            <p>This is a confirmation for your upcoming vehicle service appointment:</p>
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 6px; margin: 20px 0;">
                <p style="margin: 0 0 8px 0;"><strong>Date & Time:</strong> {appointment_date}</p>
                <p style="margin: 0;"><strong>Vehicle:</strong> {vehicle_info}</p>
            </div>
            <p>If you need to reschedule or cancel, please contact us ahead of time.</p>
            <p>We look forward to serving you!</p>
            <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;" />
            <p style="font-size: 12px; color: #64748b;">{settings.SHOP_NAME} • {settings.SHOP_ADDRESS} • {settings.SHOP_PHONE}</p>
        </div>
        """
        return await cls.send_email(to_email, subject, body)

    @classmethod
    async def send_password_reset(
        cls,
        to_email: str,
        username: str,
        reset_token: str
    ) -> bool:
        """
        Sends a secure password reset link / token to the user.
        """
        subject = f"Password Reset Request — {settings.SHOP_NAME}"
        body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
            <h2 style="color: #1e293b;">{settings.SHOP_NAME}</h2>
            <p>Hello {username},</p>
            <p>We received a request to reset your password. Use the following reset token to set a new password:</p>
            <div style="background-color: #f1f5f9; padding: 15px; border-radius: 6px; margin: 20px 0; word-break: break-all; font-family: monospace; font-size: 14px;">
                {reset_token}
            </div>
            <p style="color: #ef4444; font-size: 13px;"><strong>Note:</strong> This token expires in 1 hour. If you did not request this, you can safely ignore this email.</p>
            <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;" />
            <p style="font-size: 12px; color: #64748b;">{settings.SHOP_NAME} • {settings.SHOP_ADDRESS} • {settings.SHOP_PHONE}</p>
        </div>
        """
        return await cls.send_email(to_email, subject, body)
