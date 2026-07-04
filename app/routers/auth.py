from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserResponse
from app.security import get_password_hash
from app.rate_limiter import limiter
from app.config import settings
from app.routers.auth_deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
async def register_user(request: Request, payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account with hashed password."""
    # Check if username or email already exists
    res = await db.execute(select(User).where(
        (User.username == payload.username) | (User.email == payload.email)
    ))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered."
        )

    try:
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            role=payload.role,
            customer_id=payload.customer_id,
            tech_id=payload.tech_id
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user."""
    return current_user
