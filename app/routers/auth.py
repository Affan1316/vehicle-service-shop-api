from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserResponse, Token, RefreshTokenRequest
from app.security import create_access_token, create_refresh_token
from app.rate_limiter import limiter
from app.config import settings
from app.routers.auth_deps import get_current_user
from app.services import AuthService

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
async def register_user(request: Request, payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account with hashed password."""
    try:
        return await AuthService.register_user(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# Note: Using form data here (OAuth2 standard) instead of JSON. 
# This is so FastAPI "/docs" login lock button works out-of-box. 
# Do not change to JSON, otherwise testing in Swagger UI becomes pain.
@router.post("/token", response_model=Token)
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return a JWT access token."""
    try:
        user = await AuthService.authenticate_user(db, form_data.username, form_data.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate token with user payload
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username}
    )
    return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")

@router.post("/refresh", response_model=Token)
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
async def refresh_access_token(
    request: Request,
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Validate refresh token and return a new access/refresh token pair."""
    try:
        user = await AuthService.refresh_user_token(db, payload.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_access = create_access_token(data={"sub": user.username, "role": user.role})
    new_refresh = create_refresh_token(data={"sub": user.username})
    return Token(access_token=new_access, refresh_token=new_refresh, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user."""
    return current_user
