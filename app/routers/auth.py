import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    UserCreate, UserResponse, UserUpdate, Token, RefreshTokenRequest,
    PasswordResetRequest, PasswordResetConfirm, AdminPasswordReset, ChangePasswordRequest
)
from app.security import create_access_token, create_refresh_token
from app.rate_limiter import limiter
from app.config import settings
from app.routers.auth_deps import get_current_user, RoleChecker
from app.services import AuthService, EmailService
from app.exceptions import NotFoundError



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


# ================================================================
# PASSWORD RESET & USER ADMINISTRATION (Phase 3)
# ================================================================

@router.post("/forgot-password")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
async def forgot_password(
    request: Request,
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint: Request a password reset email token.
    Always returns success to prevent user enumeration attacks.
    """
    result = await AuthService.request_password_reset(db, payload.email)
    if result:
        user, raw_token = result
        background_tasks.add_task(
            EmailService.send_password_reset,
            user.email,
            user.username,
            raw_token
        )
    return {"message": "If this email is registered, password reset instructions have been sent."}


@router.post("/reset-password")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
async def reset_password(
    request: Request,
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint: Validate token and set new password.
    """
    try:
        await AuthService.confirm_password_reset(db, payload.token, payload.new_password)
        return {"message": "Password has been successfully reset. You may now log in."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Authenticated endpoint: Change current user's password.
    """
    try:
        await AuthService.change_password(db, current_user.user_id, payload.current_password, payload.new_password)
        return {"message": "Password successfully updated."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/users",
    response_model=List[UserResponse],
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def list_users(db: AsyncSession = Depends(get_db)):
    """
    Manager endpoint: List all user accounts in the system.
    """
    return await AuthService.list_users(db)


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Manager endpoint: Update user account profile, role, status, or customer/technician linkage.
    """
    try:
        return await AuthService.update_user(db, user_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/users/{user_id}/reset-password",
    response_model=UserResponse,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def admin_reset_password(
    user_id: uuid.UUID,
    payload: AdminPasswordReset,
    db: AsyncSession = Depends(get_db)
):
    """
    Manager endpoint: Force a password reset for any user.
    """
    try:
        return await AuthService.admin_reset_password(db, user_id, payload.new_password)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

