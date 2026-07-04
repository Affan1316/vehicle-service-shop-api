import bcrypt  # Hashing library for securing user passwords
from datetime import datetime, timedelta, timezone  # Utilities for computing token expiration timestamps
from typing import Any, Union  # Type annotations for payload parameters
from jose import jwt, JWTError  # Jose library to generate, decode, and sign JSON Web Tokens (JWT)

from app.config import settings  # App configurations containing JWT keys, expiration times, etc.

# 1. PASSWORD VERIFICATION
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed one using bcrypt directly.
    
    Bcrypt operates on bytes rather than Python strings, so we must encode
    both strings to UTF-8 bytes before comparing them.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        # If bcrypt raises an error (e.g. invalid hash format), return False safely
        return False

# 2. PASSWORD HASHING
def get_password_hash(password: str) -> str:
    """
    Generate a bcrypt hash of the password using bcrypt directly.
    
    A unique random string called a 'salt' is automatically mixed into the password
    before hashing. This ensures that the same password generates a different hash every time,
    preventing rainbow table attacks.
    """
    # bcrypt.gensalt() generates a random salt (uses 12 work rounds by default)
    salt = bcrypt.gensalt()
    # Hash the password bytes and return the result as a decoded UTF-8 string
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

# 3. GENERATE ACCESS JWT TOKEN
def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    """
    Generate a JWT access token containing the payload data.
    
    Access tokens are short-lived tokens (e.g., 15 minutes) used to authenticate API requests.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Update the payload dictionary with expiration time (exp) and token type claims
    to_encode.update({
        "exp": int(expire.timestamp()),
        "type": "access"
    })
    # Cryptographically sign the token using the secret key and signature algorithm
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# 4. GENERATE REFRESH JWT TOKEN
def create_refresh_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    """
    Generate a refresh JWT token with a longer duration.
    
    Refresh tokens are long-lived tokens (e.g., 7 days) stored securely. They are used
    to request new access tokens without asking the user to log in again.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": int(expire.timestamp()),
        "type": "refresh"
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
