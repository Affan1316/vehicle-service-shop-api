from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserResponse, Token, RefreshTokenRequest
from app.security import get_password_hash, verify_password, create_access_token, create_refresh_token
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

@router.post("/token", response_model=Token)
@limiter.limit(f"{settings.RATE_LIMIT_AUTH}/minute")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    """Authenticate user and return a JWT access token."""
    res = await db.execute(select(User).where(User.username == form_data.username))
    user = res.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User account is inactive"
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
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        from jose import jwt, JWTError
        from app.config import settings
        
        decoded = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = decoded.get("sub")
        token_type: str = decoded.get("type")
        
        if username is None or token_type != "refresh":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception

    # Query the user from the database
    res = await db.execute(select(User).where(User.username == username))
    user = res.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception

    new_access = create_access_token(data={"sub": user.username, "role": user.role})
    new_refresh = create_refresh_token(data={"sub": user.username})
    return Token(access_token=new_access, refresh_token=new_refresh, token_type="bearer")

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user."""
    return current_user
