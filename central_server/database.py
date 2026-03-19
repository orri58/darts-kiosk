"""
Central License Server — Database Configuration
Separate SQLite database for the central server.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

SERVER_DATA_DIR = Path(os.environ.get("CENTRAL_DATA_DIR", "")) or (Path(__file__).resolve().parent / "data")
SERVER_DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = SERVER_DATA_DIR / "central_licenses.sqlite"

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
SYNC_DATABASE_URL = f"sqlite:///{DB_PATH}"

async_engine = create_async_engine(DATABASE_URL, echo=False, future=True)
sync_engine = create_engine(SYNC_DATABASE_URL, echo=False, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession,
    expire_on_commit=False, autocommit=False, autoflush=False,
)

Base = declarative_base()


async def get_db():
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
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
