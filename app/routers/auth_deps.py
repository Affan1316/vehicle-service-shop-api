from typing import List  # Python type helper to annotate list variables
from fastapi import Depends, HTTPException, status  # Depends for Dependency Injection, HTTPException for throwing errors, status for HTTP status codes
from fastapi.security import OAuth2PasswordBearer  # Standard FastAPI security flow helper to read bearer tokens
from jose import jwt, JWTError  # JWT helper to decode tokens and catch token validation errors
from sqlalchemy.ext.asyncio import AsyncSession  # Type annotation for async database sessions
from sqlalchemy import select  # SQLAlchemy query builder helper to select records

from app.database import get_db  # Generator dependency yielding database sessions
from app.config import settings  # Application settings containing JWT signature keys
from app.models.models import User  # User database model representing credentials
from app.schemas.schemas import TokenData  # Pydantic schema model representing validated token payloads

# 1. OAUTH2 SECURITY SCHEME
# The OAuth2PasswordBearer dependency defines where the client must request the auth token.
# When a client sends a request to a protected endpoint, it must include an
#  "Authorization: Bearer <TOKEN>" header.
# OAuth2PasswordBearer automatically extracts the token string from that header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# 2. RETRIEVE CURRENT LOGGED IN USER
# This async dependency extracts the token, decodes it, verifies the signature and expiration,
# queries the database to verify the user exists, and returns the User object.
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency to retrieve and validate the authenticated user from the JWT token.
    Raises HTTP 401 Unauthorized if the token is expired, invalid, or belongs to a non-existent
    user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode and verify the token signature using the secret key
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        token_type: str = payload.get("type")

        # Verify mandatory claims and ensure this is an 'access' token (not a 'refresh' token)
        if username is None or role is None or token_type != "access":
            raise credentials_exception

        token_data = TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception

    # Query the user from the database to ensure their account is still active and valid
    res = await db.execute(select(User).where(User.username == token_data.username))
    user = res.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return user

# 3. ROLE-BASED ACCESS CONTROL (RBAC) DEPENDENCY CLASS
# Since routes need different allowed roles (e.g., only managers can create technicians),
# this class acts as a dynamic dependency factory.
# Usage: dependencies=[Depends(RoleChecker(["manager"]))]
class RoleChecker:
    """ FastAPI dependency to enforce Role-Based Access Control (RBAC) on endpoints. """
    def __init__(self, allowed_roles: List[str]):
        # Save the list of roles that are allowed to call the decorated endpoint
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)):
        # When FastAPI calls the dependency, this __call__ method executes.
        # If the currently logged-in user's role is not in the allowed list, block them with 403 Forbidden.
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {self.allowed_roles}."
            )
        return current_user
