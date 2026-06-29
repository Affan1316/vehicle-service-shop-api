from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

from sqlalchemy.pool import NullPool

# Create asynchronous engine
poolclass = NullPool if settings.ENVIRONMENT == "testing" else None

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    poolclass=poolclass
)

# Create sessionmaker for generating async sessions
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Declarative base for SQLAlchemy models
class Base(DeclarativeBase):
    pass


# Dependency to inject DB session into routes
async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
