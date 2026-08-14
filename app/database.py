from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings

# 1. DATABASE ENGINE SETUP
# In testing mode, we use NullPool to ensure complete connection isolation between test runs.
# In production/development, we use AsyncAdaptedQueuePool with explicit pooling parameters.
if settings.ENVIRONMENT == "testing":
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        poolclass=NullPool,
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,  # Test connection validity before checkout to eliminate dead sockets
    )

# 2. SESSION MAKER
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 3. BASE DECLARATIVE MODEL
class Base(DeclarativeBase):
    pass

# 4. DATABASE SESSION INJECTION DEPENDENCY
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


async def close_db_engine():
    """Cleanly dispose of connection pool during application shutdown."""
    await engine.dispose()
