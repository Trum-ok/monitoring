import typing

if typing.TYPE_CHECKING:
    from app.application import Application


class Service:
    def __init__(self, app: "Application"):
        from app.services.errors_service import ErrorsService

        # Reuse single runtime Telegram bot instance from Application.
        self.telegram_notifier = app.telegram_bot
        self.errors_service = ErrorsService(app)


def setup_services(app: "Application") -> Service:
    app.services = Service(app)
    return app.services
