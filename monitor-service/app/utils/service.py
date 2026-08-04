from app.database.db import Database
from app.services.errors_query_service import ErrorsQueryService
from app.services.errors_service import ErrorsService
from app.tg_bot.bot import TelegramBot


class Service:
    def __init__(
        self,
        telegram_bot: TelegramBot,
        database: Database,
        alert_cooldown_minutes: int,
        event_retention_days: int,
        max_events_per_error: int,
        web_page_size: int,
    ):
        self.telegram_notifier = telegram_bot
        self.errors_service = ErrorsService(
            database=database,
            alert_cooldown_minutes=alert_cooldown_minutes,
            event_retention_days=event_retention_days,
            max_events_per_error=max_events_per_error,
        )
        self.errors_query_service = ErrorsQueryService(
            database=database,
            page_size=web_page_size,
        )
