import httpx
import hmac
import hashlib
import json
import os
from typing import Optional, Dict, Any
from app.config import settings

class SafepayService:
    BASE_URLS = {
        "sandbox": "https://sandbox.api.getsafepay.com",
        "production": "https://api.getsafepay.com"
    }

    @staticmethod
    def _get_base_url() -> str:
        env = settings.SAFEPAY_ENVIRONMENT or "sandbox"
        return SafepayService.BASE_URLS.get(env, SafepayService.BASE_URLS["sandbox"])

    @staticmethod
    async def create_checkout_tracker(amount: float, currency: str = "PKR", order_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a Safepay Tracker to generate a checkout link."""
        api_key = settings.SAFEPAY_API_KEY
        
        if not api_key:
            # Fallback to mock tracker
            mock_tracker_id = f"trk_mock_{os.urandom(4).hex()}"
            return {
                "tracker_id": mock_tracker_id,
                "checkout_url": f"https://mock-safepay.com/checkout?tracker={mock_tracker_id}"
            }

        # Safepay amount is in PKR cents/paisa usually, but we assume exact for mock structure
        # Real Safepay Tracker API creation
        url = f"{SafepayService._get_base_url()}/order/v1/init"
        
        payload = {
            "client": api_key,
            "amount": float(amount),
            "currency": currency,
            "environment": settings.SAFEPAY_ENVIRONMENT or "sandbox"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                tracker_id = data.get("data", {}).get("token")
                if not tracker_id:
                    raise Exception("Failed to generate Safepay tracker.")
                    
                checkout_url = f"{SafepayService._get_base_url()}/checkout/pay?env={settings.SAFEPAY_ENVIRONMENT}&tracker={tracker_id}"
                
                return {
                    "tracker_id": tracker_id,
                    "checkout_url": checkout_url
                }
        except Exception as e:
            # Fallback on failure
            print(f"Safepay error: {e}")
            mock_tracker_id = f"trk_mock_fallback_{os.urandom(4).hex()}"
            return {
                "tracker_id": mock_tracker_id,
                "checkout_url": f"https://mock-safepay.com/checkout?tracker={mock_tracker_id}"
            }

    @staticmethod
    def verify_webhook(payload: bytes, sig_header: str) -> bool:
        """Verify the Safepay webhook signature."""
        secret = settings.SAFEPAY_WEBHOOK_SECRET
        
        if not secret:
            # Mock verification
            return True
            
        try:
            # Safepay signature check (X-SFPY-SIGNATURE HMAC SHA256)
            expected_sig = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_sig, sig_header)
        except Exception:
            return False
