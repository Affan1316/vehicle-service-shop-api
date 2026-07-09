from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import User
from app.schemas.schemas import UserCreate
from app.security import get_password_hash, verify_password
from jose import jwt, JWTError
from app.config import settings


class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, payload: UserCreate) -> User:
        """Register a new user account with hashed password."""
        # Check if username or email already registered
        res = await db.execute(select(User).where(
            (User.username == payload.username) | (User.email == payload.email)
        ))
        if res.scalar_one_or_none():
            raise ValueError("Username or email already registered.")

        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            role=payload.role,
            customer_id=payload.customer_id,
            tech_id=payload.tech_id
        )
        db.add(user)
        await db.flush()
        return user

    @staticmethod
    async def authenticate_user(db: AsyncSession, username: str, password: str) -> User:
        """Authenticate user and return the active User object."""
        res = await db.execute(select(User).where(User.username == username))
        user = res.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Incorrect username or password")

        if not user.is_active:
            raise ValueError("User account is inactive")

        return user

    @staticmethod
    async def refresh_user_token(db: AsyncSession, refresh_token: str) -> User:
        """Validate refresh token and return the User object."""
        try:
            decoded = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username: str = decoded.get("sub")
            token_type: str = decoded.get("type")

            if username is None or token_type != "refresh":
                raise ValueError("Could not validate credentials")
        except JWTError:
            raise ValueError("Could not validate credentials")

        res = await db.execute(select(User).where(User.username == username))
        user = res.scalar_one_or_none()
        if user is None or not user.is_active:
            raise ValueError("Could not validate credentials")

        return user
