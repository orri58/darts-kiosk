"""
SQLite Database Configuration with SQLAlchemy
Designed for migration to PostgreSQL later
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

# Database path from environment or default
DATA_DIR = Path(os.environ.get('DATA_DIR', '/app/data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite+aiosqlite:///{DATA_DIR}/db.sqlite')
SYNC_DATABASE_URL = os.environ.get('SYNC_DATABASE_URL', f'sqlite:///{DATA_DIR}/db.sqlite')

# Async engine for FastAPI
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# Sync engine for Alembic migrations
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    future=True
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Sync session factory (for migrations)
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db():
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
