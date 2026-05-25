from fastapi import FastAPI
from app.database.db import Database
from app.utils.config import Settings
from contextlib import asynccontextmanager
import logging
from app.tg_bot.bot import TelegramBot
import asyncio
from app.utils.service import setup_services



class Application:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database()
        self.telegram_bot = TelegramBot(
            app=self,
            token=self.settings.tg_bot_token,
            chat_id=self.settings.tg_chat_id,
            throttle_sec=self.settings.throttle_seconds,
            rate_limit_per_sec=self.settings.tg_rate_limit_per_sec,
            max_retries=self.settings.tg_max_retries,
            retry_backoff_max_sec=self.settings.tg_retry_backoff_max_sec,
            parse_mode=self.settings.tg_parse_mode,
            queue_maxsize=self.settings.tg_queue_maxsize,
        )
        self.app = FastAPI(
            title="Monitoring service",
            version='1.0.0',
            lifespan=self.lifespan
        )
        self.services = None
        self._setup_routes()


    def _setup_routes(self) -> None:
        from app.api.errors import router

        self.app.include_router(router)


    async def on_startup(self) -> None:
        setup_services(self)
        logger = logging.getLogger(__name__)
        logger.info('Starting application...')
        await self.database.on_startup(self.settings.db_path)
        asyncio.create_task(self.telegram_bot.start())
        logger.info('Application started')

        self.app.state.services = self.services
        self.app.state.database = self.database


    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        await self.on_startup()
        yield
        await self.on_shutdown()


    async def on_shutdown(self) -> None:
        await self.database.on_shutdown()
        await self.telegram_bot.stop()
