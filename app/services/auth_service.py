import uuid
import secrets
import datetime
import decimal
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import User, Customer, Technician, PasswordResetToken
from app.schemas.schemas import UserCreate, UserUpdate
from app.security import get_password_hash, verify_password
from app.exceptions import NotFoundError
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

        new_customer_id = payload.customer_id
        new_tech_id = payload.tech_id

        if payload.role == "customer" and not new_customer_id:
            customer = Customer(
                name=payload.username,
                customer_type="individual",
                tax_exempt=False
            )
            db.add(customer)
            await db.flush()
            new_customer_id = customer.customer_id

        elif payload.role == "technician" and not new_tech_id:
            tech = Technician(
                name=payload.username,
                hourly_rate=decimal.Decimal("50.00")
            )
            db.add(tech)
            await db.flush()
            new_tech_id = tech.tech_id

        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=get_password_hash(payload.password),
            role=payload.role,
            customer_id=new_customer_id,
            tech_id=new_tech_id
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

    # --- PASSWORD RESET & USER MANAGEMENT METHODS ---

    @staticmethod
    async def request_password_reset(db: AsyncSession, email: str) -> Optional[Tuple[User, str]]:
        """
        Creates a time-limited password reset token for the given email.
        Returns (user, raw_token) or None if user not found.
        """
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if not user or not user.is_active:
            return None

        raw_token = secrets.token_urlsafe(32)
        token_hash = get_password_hash(raw_token)
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

        reset_record = PasswordResetToken(
            user_id=user.user_id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.add(reset_record)
        await db.flush()
        return user, raw_token

    @staticmethod
    async def confirm_password_reset(db: AsyncSession, token: str, new_password: str) -> User:
        """
        Validates token, consumes it, and updates the user's password.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = (
            select(PasswordResetToken)
            .where(
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at >= now
            )
        )
        res = await db.execute(stmt)
        tokens = res.scalars().all()

        matching_token = None
        for t in tokens:
            if verify_password(token, t.token_hash):
                matching_token = t
                break

        if not matching_token:
            raise ValueError("Invalid or expired password reset token.")

        # Fetch user
        user_res = await db.execute(select(User).where(User.user_id == matching_token.user_id))
        user = user_res.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found.")

        # Mark token used & update password
        matching_token.used_at = now
        user.password_hash = get_password_hash(new_password)
        await db.flush()
        return user

    @staticmethod
    async def admin_reset_password(db: AsyncSession, user_id: uuid.UUID, new_password: str) -> User:
        """
        Manager override: forces a password reset for any user.
        """
        res = await db.execute(select(User).where(User.user_id == user_id))
        user = res.scalar_one_or_none()
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found.")

        user.password_hash = get_password_hash(new_password)
        await db.flush()
        return user

    @staticmethod
    async def change_password(
        db: AsyncSession,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str
    ) -> User:
        """
        Authenticated self-service password change.
        """
        res = await db.execute(select(User).where(User.user_id == user_id))
        user = res.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found.")

        if not verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect.")

        user.password_hash = get_password_hash(new_password)
        await db.flush()
        return user

    @staticmethod
    async def update_user(db: AsyncSession, user_id: uuid.UUID, payload: UserUpdate) -> User:
        """
        Admin update of user profile fields (role, active status, customer/tech linkage).
        """
        res = await db.execute(select(User).where(User.user_id == user_id))
        user = res.scalar_one_or_none()
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found.")

        if payload.email is not None:
            # Check unique email
            email_check = await db.execute(
                select(User).where(User.email == payload.email, User.user_id != user_id)
            )
            if email_check.scalar_one_or_none():
                raise ValueError("Email already in use by another user.")
            user.email = payload.email

        if payload.role is not None:
            user.role = payload.role
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.customer_id is not None:
            user.customer_id = payload.customer_id
        if payload.tech_id is not None:
            user.tech_id = payload.tech_id

        await db.flush()
        return user

    @staticmethod
    async def list_users(db: AsyncSession) -> List[User]:
        """
        Lists all users in the system ordered by username.
        """
        res = await db.execute(select(User).order_by(User.username.asc()))
        return list(res.scalars().all())

