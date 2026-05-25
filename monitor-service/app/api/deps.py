from fastapi import Request
from app.tg_bot.bot import TelegramBot
from app.services.errors_service import ErrorsService



def get_telegram_notifier(request: Request) -> TelegramBot:
    return request.app.state.services.telegram_notifier


def get_errors_service(request: Request) -> ErrorsService:
    return request.app.state.services.errors_service
