import os
from typing import Optional, Any
from app.config import settings

class CommunicationService:
    @staticmethod
    def _get_twilio_client() -> Optional[Any]:
        account_sid = settings.TWILIO_ACCOUNT_SID or "ACmock"
        auth_token = settings.TWILIO_AUTH_TOKEN or "mock_token"
        
        if account_sid == "ACmock":
            return None
            
        try:
            from twilio.rest import Client
            return Client(account_sid, auth_token)
        except Exception:
            return None


    @staticmethod
    def send_sms(to_phone: str, body: str) -> bool:
        """Send an SMS via Twilio. Returns True if successful (or mocked)."""
        client = CommunicationService._get_twilio_client()
        from_phone = settings.TWILIO_FROM_NUMBER or "+1234567890"
        
        if not client:
            # Mock behavior: just pretend we sent it
            print(f"[MOCK SMS] To: {to_phone} | Body: {body}")
            return True
            
        try:
            message = client.messages.create(
                body=body,
                from_=from_phone,
                to=to_phone
            )
            return message.sid is not None
        except Exception as e:
            print(f"Failed to send SMS: {e}")
            return False
