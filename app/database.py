from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession  # Core Async SQLAlchemy database connection and session management
from sqlalchemy.orm import DeclarativeBase  # Base class for mapping database tables to Python classes
from app.config import settings  # Application configurations (database URL, environment, etc.)
from sqlalchemy.pool import NullPool  # Connection pool type that does not store connections (used for testing isolation)

# 1. DATABASE ENGINE SETUP
# The engine is the core manager that handles connections to our PostgreSQL database.
# If we are in "testing" mode, we use NullPool (which doesn't keep connections open in a pool) 
# to avoid database locking issues between multiple test cases.
poolclass = NullPool if settings.ENVIRONMENT == "testing" else None

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # If True, prints all executed SQL queries to the console (good for debugging)
    future=True,          # Uses SQLAlchemy 2.0 style features
    poolclass=poolclass
)

# 2. SESSION MAKER
# The sessionmaker acts as a factory to create new database session objects.
# We configure it to return 'AsyncSession' objects for asynchronous database operations.
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False  # Keeps object attributes loaded even after a database commit
)

# 3. BASE DECLARATIVE MODEL
# All our database models (like User, Customer, Visit) will inherit from this class.
# This registers the models with SQLAlchemy's ORM system.
class Base(DeclarativeBase):
    pass


# 4. DATABASE SESSION INJECTION DEPENDENCY
# This generator function is used as a FastAPI dependency (using Depends(get_db)).
# It automatically provides a new, isolated database session for each incoming API request,
# and automatically commits the transaction when the request succeeds, or rolls it back if it fails.
async def get_db():
    async with async_session() as session:
        try:
            # yield hands control back to the FastAPI route handler so it can run its database queries.
            yield session
            # If the route handler executed successfully without errors, we save the changes to the database.
            await session.commit()
        except Exception:
            # If any exception occurs during the request, we discard all database changes made during this request.
            await session.rollback()
            raise
        finally:
            # We always close the database session to release the connection back to the pool.
            await session.close()
