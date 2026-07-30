import logging
from contextlib import asynccontextmanager

from app.database.db import Database
from app.tg_bot.bot import TelegramBot
from app.utils.config import Settings
from app.utils.service import Service
from fastapi import FastAPI


class Application:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database()
        self.telegram_bot = TelegramBot(
            token=self.settings.tg_bot_token,
            chat_id=self.settings.tg_chat_id,
            throttle_sec=self.settings.throttle_seconds,
            rate_limit_per_sec=self.settings.tg_rate_limit_per_sec,
            max_retries=self.settings.tg_max_retries,
            retry_backoff_max_sec=self.settings.tg_retry_backoff_max_sec,
            parse_mode=self.settings.tg_parse_mode,
            queue_maxsize=self.settings.tg_queue_maxsize,
            max_traceback_chars=self.settings.tg_max_traceback_chars,
        )
        self.services = Service(
            telegram_bot=self.telegram_bot,
            database=self.database,
            alert_cooldown_minutes=self.settings.alert_cooldown_minutes,
        )
        self.telegram_bot.on_delivered = self.services.errors_service.mark_notified
        self.app = FastAPI(title="Monitoring service", version="1.0.0", lifespan=self.lifespan)
        self._setup_routes()

    def _setup_routes(self) -> None:
        from app.api.errors import router
        from app.api.health import router as health_router

        self.app.include_router(router)
        self.app.include_router(health_router)

    async def on_startup(self) -> None:
        logger = logging.getLogger(__name__)
        logger.info("Starting application...")
        await self.database.on_startup(self.settings.db_path)
        await self.telegram_bot.start()
        logger.info("Application started")

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
