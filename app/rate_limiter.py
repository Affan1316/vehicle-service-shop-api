from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

# Initialize the standard slowapi Limiter
# Disable it in the testing environment to prevent tests from failing due to rate limits
limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.ENVIRONMENT != "testing"
)
