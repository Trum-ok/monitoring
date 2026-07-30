import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Database:
    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.session_factory = None
        self.base = Base
        self.logger = logging.getLogger(__name__)

    async def on_startup(self, db_path: str) -> None:
        self.logger.info("Stating db connection")

        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

        async with self.session() as session:
            await session.execute(text("PRAGMA journal_mode=WAL"))
            await session.commit()
            self.logger.info("DB connection established")

    async def on_shutdown(self) -> None:
        self.logger.info("Closing db connection")
        if self.engine is not None:
            await self.engine.dispose()

    def session(self):
        if not self.session_factory:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self.session_factory()
