from app.database.db import Database
from app.services.errors_service import ErrorsService
from app.tg_bot.bot import TelegramBot


class Service:
    def __init__(self, telegram_bot: TelegramBot, database: Database, alert_cooldown_minutes: int):
        self.telegram_notifier = telegram_bot
        self.errors_service = ErrorsService(
            database=database,
            alert_cooldown_minutes=alert_cooldown_minutes,
        )
