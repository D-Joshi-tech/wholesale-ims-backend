import os
from typing import AsyncGenerator, Optional, Any, Dict
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker[AsyncSession]] = None

def get_engine() -> AsyncEngine:
    """Lazy-initializes asyncpg engine inside the active event loop."""
    global _engine
    if _engine is None:
        raw_database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://ims_user:ImsSecurePass2026!@43.204.110.14:5432/ims_db",
        )
        if raw_database_url.startswith("postgres://"):
            raw_database_url = raw_database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif raw_database_url.startswith("postgresql://") and not raw_database_url.startswith("postgresql+asyncpg://"):
            raw_database_url = raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        engine_kwargs: Dict[str, Any] = {"echo": False}
        if os.getenv("VERCEL"):
            from sqlalchemy.pool import NullPool
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_pre_ping"] = True
            engine_kwargs["pool_size"] = 10
            engine_kwargs["max_overflow"] = 20

        _engine = create_async_engine(raw_database_url, **engine_kwargs)
    return _engine

def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _session_maker

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_maker()
    async with session_factory() as session:
        yield session

def __getattr__(name: str) -> Any:
    if name == "engine":
        return get_engine()
    if name == "AsyncSessionLocal":
        return get_session_maker()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
