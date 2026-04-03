"""
SQLite Database Configuration with SQLAlchemy
Paths are resolved to absolute paths from the project root (parent of backend/),
so the app works regardless of which directory uvicorn is launched from.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Project root = parent of the directory this file lives in (backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_data_dir():
    raw = os.environ.get('DATA_DIR', '')
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()
    return PROJECT_ROOT / 'data'


DATA_DIR = _resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'db').mkdir(parents=True, exist_ok=True)


def _default_sqlite_path() -> Path:
    return DATA_DIR / 'db.sqlite'


def _resolve_sqlite_url(raw_url: str, prefix: str) -> str:
    """Turn a relative sqlite path into an absolute one anchored at PROJECT_ROOT."""
    if not raw_url:
        default_path = _default_sqlite_path()
        default_path.parent.mkdir(parents=True, exist_ok=True)
        return f'{prefix}:///{default_path}'
    # Extract the file path from sqlite:///./relative or sqlite:////absolute
    for tag in (f'{prefix}:///', f'{prefix}://'):
        if raw_url.startswith(tag):
            fpath = raw_url[len(tag):]
            p = Path(fpath)
            if not p.is_absolute():
                p = (PROJECT_ROOT / p).resolve()
                p.parent.mkdir(parents=True, exist_ok=True)
                return f'{tag}{p}'
            return raw_url
    return raw_url


DATABASE_URL = _resolve_sqlite_url(
    os.environ.get('DATABASE_URL', ''),
    'sqlite+aiosqlite'
)
SYNC_DATABASE_URL = _resolve_sqlite_url(
    os.environ.get('SYNC_DATABASE_URL', ''),
    'sqlite'
)


def sqlite_path_from_url(url: str) -> Path:
    """Extract the sqlite database file path from a configured sqlite URL."""
    for prefix in ('sqlite+aiosqlite:///', 'sqlite:///'):
        if url.startswith(prefix):
            raw_path = url[len(prefix):]
            path = Path(raw_path)
            if not path.is_absolute():
                path = (PROJECT_ROOT / path).resolve()
            return path
    return _default_sqlite_path().resolve()


DATABASE_PATH = sqlite_path_from_url(DATABASE_URL)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

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
